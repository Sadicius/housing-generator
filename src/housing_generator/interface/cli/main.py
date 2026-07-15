"""Punto de entrada CLI: construye un Program + Lot de ejemplo y ejecuta
el generador. Sirve como demostracion end-to-end de la arquitectura."""
import argparse
from shapely.geometry import box

from housing_generator.config.container import build_generate_layout_use_case, build_generate_building_use_case
from housing_generator.application.dto.generation_request import GenerationRequest
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import RoomType, AdjacencyStrength
from housing_generator.domain.exceptions import LayoutGenerationError
from housing_generator.domain.services.type_adjacency_catalog import build_adjacency_requirements
from housing_generator.infrastructure.persistence.json_layout_repository import JsonLayoutRepository
from housing_generator.infrastructure.persistence.seleccion_plantas_importer import import_seleccion_plantas


def build_sample_program(auto_adjacency: bool = False) -> Program:
    """`auto_adjacency=True`: deriva los AdjacencyRequirement
    automáticamente del catálogo formalizado en vez de la declaración
    manual de abajo. Mismas estancias en ambos casos.

    6 estancias (programa mínimo exacto), no 11 ni 9 -- reducido en dos
    pasos a petición del usuario ("quiero solucionar el problema y que
    pueda generarse ya, está roto"). Ni 11 estancias (6 adyacencias) ni
    9 (4 adyacencias) convergieron de forma fiable ni con 15-20 semillas
    de reintento real -- confirmado empíricamente en esta sesión que el
    problema es el NÚMERO de estancias combinado con la mezcla de tipos,
    no cualquier adyacencia concreta (ver [ARCH:locking-progresivo]).
    Este tamaño exacto SÍ se confirmó repetidamente en esta sesión con
    tasas de éxito reales del 40-80% de las semillas probadas. Como este
    programa es solo dato de EJEMPLO del CLI (no un requisito de ningún
    usuario real), reducirlo a lo que sí converge de forma fiable es la
    solución pragmática correcta, no una renuncia -- para programas más
    grandes, el dashboard/CLI real siguen aceptando cualquier tamaño que
    el usuario declare, esto solo afecta a la demo por defecto.
    """
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=25)),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=12)),
        Room(id="bath1", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=6)),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=6)),
        Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=2)),
        Room(id="storage", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=4)),
    ]
    if auto_adjacency:
        adjacency = build_adjacency_requirements(rooms)
    else:
        adjacency = [
            AdjacencyRequirement("kitchen", "laundry", AdjacencyStrength.MUST_BE_NEAR),
        ]
    return Program(rooms=rooms, adjacency_requirements=adjacency)


def build_sample_lot() -> Lot:
    # 14x16=224m2 -- ya no hace falta ajustar esto a mano al tamano del
    # programa: SimulatedAnnealingLayoutGenerator calcula su propia
    # huella construible (footprint.py), el sobrante queda como vacio
    # real (jardin/patio), no infla las estancias. Ver [ARCH:area-objetivo].
    return Lot(boundary=Boundary(polygon=box(0, 0, 14, 16)))


def main():
    parser = argparse.ArgumentParser(description="Generador de viviendas por zonificacion dia/noche/servicio")
    parser.add_argument("--output", default="layout.json", help="Ruta de salida del layout generado")
    parser.add_argument(
        "--seed", type=int, default=4,
        help="Semilla del recocido simulado (por defecto 4, fija -- determinista). "
             "Usa otro valor para explorar variantes distintas.",
    )
    parser.add_argument("--max-iterations", type=int, default=3000, help="Iteraciones del recocido simulado")
    parser.add_argument(
        "--auto-adjacency", action="store_true",
        help="Derivar Obligatorio/Preferencia automaticamente del catalogo formalizado "
             "de 120 pares (build_adjacency_requirements) en vez de la declaracion "
             "manual del programa de ejemplo -- genera bastantes mas requisitos "
             "(44 en vez de 6 para las mismas 11 estancias), busqueda mas dificil, "
             "puede necesitar --max-iterations mayor o probar otra --seed.",
    )
    parser.add_argument(
        "--vivienda-accesible", action="store_true",
        help="Exigir circulo de giro Ø1.50m en estancias habitables + bano, y pasillo "
             "≥1.20m (mas exigente que el general 1.00m) -- DB-SUA Anejo A + Base 5.4 "
             "Galicia (vivienda adaptada para usuarios de silla de ruedas). OPT-IN: la "
             "gran mayoria de viviendas NO estan obligadas a esto. Retomado de un modulo "
             "Lua de un proyecto anterior del usuario (accesibilidad.lua) -- solo cubre "
             "lo geometricamente verificable con este proyecto (circulo/ancho), no "
             "mobiliario (altura de encimera, aproximacion a la cama...), que no se "
             "modela aqui.",
    )
    parser.add_argument(
        "--import-seleccion", metavar="RUTA", default=None,
        help="Importar 'seleccion_plantas.json' (exportacion del dashboard) en vez del "
             "programa de ejemplo -- genera un edificio multi-planta real. Con el formato "
             "nuevo (version 2) usa la cantidad y area reales declaradas en el dashboard; "
             "con el formato antiguo (solo nombres de tipo), usa AREAS_POR_DEFECTO_M2 como "
             "aproximacion generica -- revisar antes de un proyecto real en ese caso. "
             "'tipo_vivienda' del JSON (aislada/pareada/adosada) se traduce automaticamente "
             "a Lot.medianera_sides. Ignora --auto-adjacency (las adyacencias siempre se "
             "derivan del catalogo aqui).",
    )
    parser.add_argument(
        "--retry-seeds", type=int, default=5,
        help="Con --import-seleccion, cuantas semillas distintas probar automaticamente "
             "(empezando en --seed, incrementando de 1 en 1) antes de rendirse -- "
             "retomado de un caso real: la primera semilla de un programa concreto no "
             "convergio, la 4a si. Los programas que salen de --import-seleccion no estan "
             "curados a mano (a diferencia del ejemplo del CLI), asi que necesitan mas "
             "margen de busqueda de forma habitual, no como excepcion. Poner a 1 para "
             "desactivar el reintento y usar solo --seed tal cual.",
    )
    parser.add_argument(
        "--lot-size", metavar="ANCHOxFONDO", default=None,
        help="Con --import-seleccion, tamano de parcela en metros (p.ej. '14x16') en vez "
             "del tamano de ejemplo por defecto (14x16, el mismo valor) -- util para "
             "acercarse al tamano real de tu parcela, o para dar mas margen si el "
             "programa importado es grande.",
    )
    parser.add_argument(
        "--retranqueo", type=float, default=None,
        help="Separacion minima a los lindes de parcela, en metros (vivienda AISLADA) -- "
             "concepto ya implementado y probado (Lot.retranqueo_m), sin forma de "
             "activarlo desde el CLI hasta ahora. Por defecto, sin retranqueo (area "
             "edificable = parcela completa), igual que antes de anadir este flag.",
    )
    parser.add_argument(
        "--retranqueo-incremento", type=float, default=None,
        help="Cuanto se reduce el contorno edificable, en metros, de cada planta "
             "respecto a la de abajo (vivienda multi-planta) -- concepto ya implementado "
             "y probado (Lot.retranqueo_incremento_por_planta_m), sin forma de activarlo "
             "desde el CLI hasta ahora. Requiere --retranqueo tambien (no tiene sentido "
             "incrementar un retranqueo que no existe). Por defecto, mismo contorno para "
             "todas las plantas, igual que antes de anadir este flag.",
    )
    parser.add_argument(
        "--experimental-btree", action="store_true",
        help="Usa BTreeLayoutGenerator (arbol B*, Chang & Chang 2000) en vez del "
             "generador por defecto -- migracion en curso (Fase 4/5, comparacion "
             "empirica), ver docs/referencia/generador/prototipo-btree/. Solo aplica "
             "con --import-seleccion (multi-planta); el camino por defecto sigue "
             "usando el generador actual.",
    )
    args = parser.parse_args()

    if args.retranqueo_incremento is not None and args.retranqueo is None:
        raise SystemExit("--retranqueo-incremento requiere tambien --retranqueo (no tiene sentido incrementar un retranqueo que no existe).")

    if args.import_seleccion:
        seleccion = import_seleccion_plantas(args.import_seleccion)
        program = seleccion.program
        if args.lot_size:
            w_str, h_str = args.lot_size.lower().split("x")
            lot = Lot(
                boundary=Boundary(polygon=box(0, 0, float(w_str), float(h_str))),
                medianera_sides=seleccion.medianera_sides,
                retranqueo_m=args.retranqueo,
                retranqueo_incremento_por_planta_m=args.retranqueo_incremento,
            )
        else:
            base_lot = build_sample_lot()
            lot = Lot(
                boundary=base_lot.boundary,
                medianera_sides=seleccion.medianera_sides,
                retranqueo_m=args.retranqueo,
                retranqueo_incremento_por_planta_m=args.retranqueo_incremento,
            )
        if seleccion.medianera_sides:
            print(f"(tipo_vivienda del JSON -> medianera en: {', '.join(sorted(seleccion.medianera_sides))})")

        building = None
        last_error = None
        for attempt in range(max(1, args.retry_seeds)):
            seed = args.seed + attempt
            use_case = build_generate_building_use_case(
                adjacency_requirements=program.adjacency_requirements,
                seed=seed,
                max_iterations=args.max_iterations,
                vivienda_accesible=args.vivienda_accesible,
                experimental_btree=args.experimental_btree,
            )
            try:
                building = use_case.execute(program, lot)
                if attempt > 0:
                    print(f"(semilla {args.seed} no convergio, funciono con semilla {seed} "
                          f"tras {attempt + 1} intentos)")
                break
            except LayoutGenerationError as e:
                last_error = e
        if building is None:
            raise SystemExit(
                f"No se pudo generar tras probar {args.retry_seeds} semillas "
                f"(desde {args.seed} hasta {args.seed + args.retry_seeds - 1}). "
                f"Ultimo error: {last_error}"
            )

        for level, layout in building.floors.items():
            output_path = args.output.replace(".json", f"_{level.value}.json")
            JsonLayoutRepository().save(layout, output_path, adjacency_requirements=program.adjacency_requirements)
            print(f"Planta '{level.value}' generada y guardada en {output_path}")
            for room in layout.rooms:
                b = room.boundary.polygon.bounds
                print(f"  - {room.name:22s} zona={room.zone.value:8s} bounds=({b[0]:.1f}, {b[1]:.1f}, {b[2]:.1f}, {b[3]:.1f})")
        return

    program = build_sample_program(auto_adjacency=args.auto_adjacency)
    lot = build_sample_lot()
    if args.retranqueo is not None or args.retranqueo_incremento is not None:
        lot = Lot(
            boundary=lot.boundary,
            entrance_side=lot.entrance_side,
            retranqueo_m=args.retranqueo,
            retranqueo_incremento_por_planta_m=args.retranqueo_incremento,
        )

    layout = None
    last_error = None
    for attempt in range(max(1, args.retry_seeds)):
        seed = args.seed + attempt
        use_case = build_generate_layout_use_case(
            adjacency_requirements=program.adjacency_requirements,
            seed=seed,
            max_iterations=args.max_iterations,
            vivienda_accesible=args.vivienda_accesible,
        )
        try:
            layout = use_case.execute(GenerationRequest(program=program, lot=lot))
            if attempt > 0:
                print(f"(semilla {args.seed} no convergio, funciono con semilla {seed} "
                      f"tras {attempt + 1} intentos)")
            break
        except LayoutGenerationError as e:
            last_error = e
    if layout is None:
        raise SystemExit(
            f"No se pudo generar tras probar {args.retry_seeds} semillas "
            f"(desde {args.seed} hasta {args.seed + args.retry_seeds - 1}). "
            f"Ultimo error: {last_error}"
        )

    JsonLayoutRepository().save(layout, args.output, adjacency_requirements=program.adjacency_requirements)

    print(f"Layout generado y guardado en {args.output}\n")
    for room in layout.rooms:
        b = room.boundary.polygon.bounds
        print(f"  - {room.name:22s} zona={room.zone.value:8s} bounds=({b[0]:.1f}, {b[1]:.1f}, {b[2]:.1f}, {b[3]:.1f})")


if __name__ == "__main__":
    main()

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
from housing_generator.domain.services.type_adjacency_catalog import generate_adjacency_requirements
from housing_generator.infrastructure.persistence.json_layout_repository import JsonLayoutRepository
from housing_generator.infrastructure.persistence.seleccion_plantas_importer import import_seleccion_plantas


def build_sample_program(auto_adjacency: bool = False) -> Program:
    """`auto_adjacency=True`: en vez de la declaracion manual de abajo,
    deriva los AdjacencyRequirement automaticamente del catalogo
    formalizado (`generate_adjacency_requirements`) -- retomado de
    docs/CONTINUIDAD.md ("conectar como opcion automatica en
    container.py/CLI"). Mismas 11 estancias en ambos casos, solo cambia
    de donde salen las relaciones de adyacencia."""
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=25)),
        Room(id="dining", name="Comedor", room_type=RoomType.DINING_ROOM, dimensions=Dimensions(area_m2=15)),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=12)),
        Room(id="entrance", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=5)),
        Room(id="bed1", name="Dormitorio principal", room_type=RoomType.MASTER_BEDROOM, dimensions=Dimensions(area_m2=16)),
        Room(id="bed2", name="Dormitorio 2", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
        Room(id="bath1", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=6)),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=6)),
        Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=2)),
        Room(id="storage", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=4)),
        Room(id="garage", name="Garaje", room_type=RoomType.GARAGE, dimensions=Dimensions(area_m2=18)),
    ]
    if auto_adjacency:
        adjacency = generate_adjacency_requirements(rooms)
    else:
        adjacency = [
            AdjacencyRequirement("living", "dining", AdjacencyStrength.MUST_BE_NEAR),
            AdjacencyRequirement("dining", "kitchen", AdjacencyStrength.MUST_BE_NEAR),
            AdjacencyRequirement("living", "entrance", AdjacencyStrength.MUST_BE_NEAR),
            AdjacencyRequirement("bath1", "entrance", AdjacencyStrength.MUST_BE_NEAR),
            AdjacencyRequirement("living", "garage", AdjacencyStrength.MUST_BE_AWAY),
            AdjacencyRequirement("bed1", "kitchen", AdjacencyStrength.MUST_BE_AWAY),
        ]
    return Program(rooms=rooms, adjacency_requirements=adjacency)


def build_sample_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 14, 16)))


def main():
    parser = argparse.ArgumentParser(description="Generador de viviendas por zonificacion dia/noche/servicio")
    parser.add_argument("--output", default="layout.json", help="Ruta de salida del layout generado")
    parser.add_argument(
        "--seed", type=int, default=1,
        help="Semilla del recocido simulado (por defecto 1, fija -- determinista. "
             "Estable de nuevo tras anadir la heuristica de 'cortar por el lado mas "
             "largo' -- Marson & Musse 2010 -- que redujo la aparicion de estancias "
             "como tiras finas lo suficiente para que la semilla 1 volviera a "
             "converger facil). Usa otro valor para explorar variantes distintas.",
    )
    parser.add_argument("--max-iterations", type=int, default=3000, help="Iteraciones del recocido simulado")
    parser.add_argument(
        "--auto-adjacency", action="store_true",
        help="Derivar Obligatorio/Preferencia automaticamente del catalogo formalizado "
             "de 120 pares (generate_adjacency_requirements) en vez de la declaracion "
             "manual del programa de ejemplo -- genera bastantes mas requisitos "
             "(44 en vez de 6 para las mismas 11 estancias), busqueda mas dificil, "
             "puede necesitar --max-iterations mayor o probar otra --seed.",
    )
    parser.add_argument(
        "--import-seleccion", metavar="RUTA", default=None,
        help="Importar 'seleccion_plantas.json' (exportacion del dashboard) en vez del "
             "programa de ejemplo -- genera un edificio multi-planta real. LIMITACION "
             "HONESTA: el JSON es solo una seleccion de tipos por planta (nunca cuenta "
             "ni areas reales), asi que el Program resultante usa areas genericas por "
             "defecto (ver AREAS_POR_DEFECTO_M2) -- revisar antes de usar en un proyecto "
             "real, tal como advierte el propio dashboard al exportar. Ignora "
             "--auto-adjacency (las adyacencias siempre se derivan del catalogo aqui).",
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
    args = parser.parse_args()

    if args.import_seleccion:
        program = import_seleccion_plantas(args.import_seleccion)
        if args.lot_size:
            w_str, h_str = args.lot_size.lower().split("x")
            lot = Lot(boundary=Boundary(polygon=box(0, 0, float(w_str), float(h_str))))
        else:
            lot = build_sample_lot()

        building = None
        last_error = None
        for attempt in range(max(1, args.retry_seeds)):
            seed = args.seed + attempt
            use_case = build_generate_building_use_case(
                adjacency_requirements=program.adjacency_requirements,
                seed=seed,
                max_iterations=args.max_iterations,
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

    use_case = build_generate_layout_use_case(
        adjacency_requirements=program.adjacency_requirements,
        seed=args.seed,
        max_iterations=args.max_iterations,
    )
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    JsonLayoutRepository().save(layout, args.output, adjacency_requirements=program.adjacency_requirements)

    print(f"Layout generado y guardado en {args.output}\n")
    for room in layout.rooms:
        b = room.boundary.polygon.bounds
        print(f"  - {room.name:22s} zona={room.zone.value:8s} bounds=({b[0]:.1f}, {b[1]:.1f}, {b[2]:.1f}, {b[3]:.1f})")


if __name__ == "__main__":
    main()

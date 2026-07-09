"""Punto de entrada CLI: construye un Program + Lot de ejemplo y ejecuta
el generador. Sirve como demostracion end-to-end de la arquitectura."""
import argparse
from shapely.geometry import box

from housing_generator.config.container import build_generate_layout_use_case
from housing_generator.application.dto.generation_request import GenerationRequest
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import RoomType, AdjacencyStrength
from housing_generator.domain.services.type_adjacency_catalog import generate_adjacency_requirements
from housing_generator.infrastructure.persistence.json_layout_repository import JsonLayoutRepository


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
        help="Semilla del recocido simulado (por defecto 1, fija -- determinista; "
             "confirmada estable con el movimiento 'slide_wall' anadido tras "
             "investigar Merrell et al. 2010). Usa otro valor para explorar "
             "variantes distintas.",
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
    args = parser.parse_args()

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

from housing_generator.application.use_cases.build_adjacency_graph import (
    BuildAdjacencyGraphUseCase,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.program import Program
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import RoomType, AdjacencyStrength


def test_adjacency_graph_has_expected_nodes_and_edges():
    rooms = [
        Room(
            id="living",
            name="Estar",
            room_type=RoomType.LIVING_ROOM,
            dimensions=Dimensions(area_m2=20),
        ),
        Room(
            id="dining",
            name="Comedor",
            room_type=RoomType.DINING_ROOM,
            dimensions=Dimensions(area_m2=15),
        ),
    ]
    req = [AdjacencyRequirement("living", "dining", AdjacencyStrength.MUST_BE_NEAR)]
    program = Program(rooms=rooms, adjacency_requirements=req)

    graph = BuildAdjacencyGraphUseCase().execute(program)

    assert set(graph.nodes) == {"living", "dining"}
    assert graph.has_edge("living", "dining")
    assert graph["living"]["dining"]["weight"] == 3

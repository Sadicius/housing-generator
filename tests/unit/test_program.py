import pytest
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import RoomType, AdjacencyStrength
from housing_generator.domain.exceptions import InvalidProgramError


def _room(room_id, area) -> Room:
    return Room(
        id=room_id,
        name=room_id,
        room_type=RoomType.BEDROOM,
        dimensions=Dimensions(area_m2=area),
    )


def test_total_area_m2_sums_all_rooms():
    program = Program(rooms=[_room("a", 10), _room("b", 15.5), _room("c", 4.5)])
    assert program.total_area_m2 == 30.0


def test_total_area_m2_of_empty_program_is_zero():
    program = Program(rooms=[])
    assert program.total_area_m2 == 0.0


def test_room_by_id_returns_the_matching_room():
    room_b = _room("b", 15)
    program = Program(rooms=[_room("a", 10), room_b])
    assert program.room_by_id("b") is room_b


def test_room_by_id_raises_key_error_for_unknown_id():
    program = Program(rooms=[_room("a", 10)])
    with pytest.raises(KeyError):
        program.room_by_id("no_existe")


def test_duplicate_room_ids_are_rejected():
    with pytest.raises(InvalidProgramError):
        Program(rooms=[_room("a", 10), _room("a", 12)])


def test_adjacency_requirement_referencing_unknown_room_is_rejected():
    with pytest.raises(InvalidProgramError):
        Program(
            rooms=[_room("a", 10)],
            adjacency_requirements=[
                AdjacencyRequirement("a", "no_existe", AdjacencyStrength.MUST_BE_NEAR)
            ],
        )

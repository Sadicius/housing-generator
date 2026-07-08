import pytest
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import AdjacencyStrength


def test_involves_returns_true_for_either_room():
    req = AdjacencyRequirement("a", "b", AdjacencyStrength.MUST_BE_NEAR)
    assert req.involves("a") is True
    assert req.involves("b") is True


def test_involves_returns_false_for_unrelated_room():
    req = AdjacencyRequirement("a", "b", AdjacencyStrength.MUST_BE_NEAR)
    assert req.involves("c") is False


def test_other_returns_the_opposite_room():
    req = AdjacencyRequirement("a", "b", AdjacencyStrength.MUST_BE_NEAR)
    assert req.other("a") == "b"
    assert req.other("b") == "a"


def test_other_raises_for_a_room_not_in_the_requirement():
    req = AdjacencyRequirement("a", "b", AdjacencyStrength.MUST_BE_NEAR)
    with pytest.raises(ValueError):
        req.other("c")

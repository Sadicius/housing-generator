import random
from shapely.geometry import box
from housing_generator.infrastructure.algorithms.layout_generation.partition_tree import (
    PartitionNode,
    build_random_tree,
    place_tree,
    random_neighbor,
)


def test_build_random_tree_contains_every_room_exactly_once():
    room_ids = ["a", "b", "c", "d", "e"]
    tree = build_random_tree(room_ids, random.Random(42))

    leaf_ids = sorted(leaf.room_id for leaf in tree.leaves())
    assert leaf_ids == sorted(room_ids)


def test_build_random_tree_single_room_is_a_leaf():
    tree = build_random_tree(["only"], random.Random(1))
    assert tree.is_leaf
    assert tree.room_id == "only"


def test_place_tree_covers_full_rectangle_area_without_overlap():
    room_ids = ["a", "b", "c", "d"]
    areas = {"a": 10, "b": 20, "c": 5, "d": 15}
    tree = build_random_tree(room_ids, random.Random(7))
    rectangle = box(0, 0, 10, 10)

    placements = place_tree(tree, rectangle, areas)

    assert set(placements.keys()) == set(room_ids)
    total_placed_area = sum(p.area for p in placements.values())
    assert abs(total_placed_area - rectangle.area) < 1e-6

    # sin solapes: la suma de areas individuales debe igualar el area de
    # la union de todos los rectangulos
    from shapely.ops import unary_union
    union_area = unary_union(list(placements.values())).area
    assert abs(union_area - rectangle.area) < 1e-6


def test_place_tree_proportional_to_area():
    # dos hojas, un solo corte: la proporcion debe reflejar las areas
    tree = PartitionNode(
        direction="v",
        first=PartitionNode(room_id="big"),
        second=PartitionNode(room_id="small"),
    )
    areas = {"big": 75, "small": 25}
    rectangle = box(0, 0, 100, 10)

    placements = place_tree(tree, rectangle, areas)

    assert placements["big"].area == 750  # 75% de 1000
    assert placements["small"].area == 250  # 25% de 1000


def test_place_tree_proportional_with_horizontal_cut():
    # regresion: el corte horizontal ("h") invertia la proporcion
    # (first se quedaba con 1-ratio en vez de ratio) -- este test cubre
    # especificamente esa direccion, que el test anterior (solo "v") no
    # detectaba.
    tree = PartitionNode(
        direction="h",
        first=PartitionNode(room_id="big"),
        second=PartitionNode(room_id="small"),
    )
    areas = {"big": 75, "small": 25}
    rectangle = box(0, 0, 10, 100)

    placements = place_tree(tree, rectangle, areas)

    assert placements["big"].area == 750
    assert placements["small"].area == 250


def test_place_tree_preserves_proportions_through_mixed_deep_tree():
    # arbol de 4 niveles mezclando "h" y "v", para detectar cualquier
    # asimetria entre direcciones que un arbol de 1 solo corte no revela.
    tree = PartitionNode(
        direction="v",
        first=PartitionNode(
            direction="h",
            first=PartitionNode(room_id="a"),
            second=PartitionNode(room_id="b"),
        ),
        second=PartitionNode(
            direction="h",
            first=PartitionNode(room_id="c"),
            second=PartitionNode(room_id="d"),
        ),
    )
    areas = {"a": 10, "b": 20, "c": 30, "d": 40}
    rectangle = box(0, 0, 20, 10)  # area total = 200

    placements = place_tree(tree, rectangle, areas)
    total_area = sum(areas.values())

    for room_id, declared_area in areas.items():
        expected = declared_area / total_area * rectangle.area
        assert abs(placements[room_id].area - expected) < 1e-6, room_id


def test_random_neighbor_preserves_all_room_ids():
    room_ids = ["a", "b", "c", "d", "e", "f"]
    tree = build_random_tree(room_ids, random.Random(3))

    for i in range(20):
        tree = random_neighbor(tree, random.Random(i))
        assert sorted(leaf.room_id for leaf in tree.leaves()) == sorted(room_ids)


def test_random_neighbor_does_not_mutate_original_tree():
    room_ids = ["a", "b", "c"]
    tree = build_random_tree(room_ids, random.Random(5))
    original_leaf_ids = [leaf.room_id for leaf in tree.leaves()]

    for i in range(10):
        random_neighbor(tree, random.Random(i))

    assert [leaf.room_id for leaf in tree.leaves()] == original_leaf_ids

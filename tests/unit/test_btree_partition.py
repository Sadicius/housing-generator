import random
import pytest
from shapely.geometry import box
from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
    BStarNode,
    build_random_tree,
    compute_positions,
)


def test_compute_positions_matches_hand_calculation():
    # caso de prueba verificado a mano en el prototipo aislado antes de
    # escribir este modulo de produccion -- misma verificacion, ahora
    # contra el codigo real. A(4x2) raiz, B hijo izquierdo (pegado a la derecha),
    # C hijo derecho (misma X, encima).
    A = BStarNode(room_id="A", aspect_ratio=2.0)  # area 8, ratio 2 -> w=4,h=2
    B = BStarNode(room_id="B", aspect_ratio=1.0)  # area 9, ratio 1 -> w=3,h=3
    C = BStarNode(room_id="C", aspect_ratio=0.5)  # area 8, ratio 0.5 -> w=2,h=4
    A.left = B
    A.right = C
    areas = {"A": 8.0, "B": 9.0, "C": 8.0}

    positions = compute_positions(A, areas)

    assert positions["A"].bounds == pytest.approx((0, 0, 4, 2))
    assert positions["B"].bounds == pytest.approx((4, 0, 7, 3))
    assert positions["C"].bounds == pytest.approx((0, 2, 2, 6))


def test_compute_positions_preserves_declared_area_regardless_of_aspect_ratio():
    for ratio in [0.2, 0.5, 1.0, 2.0, 5.0]:
        node = BStarNode(room_id="a", aspect_ratio=ratio)
        positions = compute_positions(node, {"a": 12.0})
        assert positions["a"].area == pytest.approx(12.0)


def test_compute_positions_produces_a_non_rectangular_silhouette():
    # el mismo caso de 5 estancias verificado en el prototipo -- silueta
    # con 0 solapes, NO rectangular, con vacio real emergiendo del
    # propio empaquetado.
    from shapely.ops import unary_union

    A = BStarNode("salon", aspect_ratio=5 / 3)  # area 15 -> 5x3
    B = BStarNode("cocina", aspect_ratio=1.0)  # area 9 -> 3x3
    C = BStarNode("dormitorio", aspect_ratio=3 / 2.5)  # area 7.5 -> 3x2.5
    D = BStarNode("bano", aspect_ratio=1.0)  # area 4 -> 2x2
    E = BStarNode("lavadero", aspect_ratio=1.0)  # area 4 -> 2x2
    A.left = B
    A.right = C
    B.left = D
    C.left = E
    areas = {
        "salon": 15.0,
        "cocina": 9.0,
        "dormitorio": 7.5,
        "bano": 4.0,
        "lavadero": 4.0,
    }

    positions = compute_positions(A, areas)
    rects = list(positions.values())
    union = unary_union(rects)

    assert union.area == pytest.approx(sum(r.area for r in rects))  # sin solapes
    minx, miny, maxx, maxy = union.bounds
    assert not union.equals(box(minx, miny, maxx, maxy))  # NO es un rectangulo simple


def test_compute_positions_no_overlaps_for_random_trees():
    # propiedad general, no solo el caso de mano -- para muchas semillas
    # distintas, el empaquetado nunca debe solapar estancias entre si.
    from shapely.ops import unary_union

    room_ids = ["a", "b", "c", "d", "e", "f", "g"]
    areas = {rid: 10.0 + i for i, rid in enumerate(room_ids)}
    for seed in range(30):
        tree = build_random_tree(room_ids, random.Random(seed))
        positions = compute_positions(tree, areas)
        rects = list(positions.values())
        union = unary_union(rects)
        assert union.area == pytest.approx(
            sum(r.area for r in rects)
        ), f"solape en seed {seed}"


def test_build_random_tree_contains_every_room_exactly_once():
    room_ids = ["a", "b", "c", "d", "e"]
    tree = build_random_tree(room_ids, random.Random(42))
    node_ids = sorted(n.room_id for n in tree.nodes())
    assert node_ids == sorted(room_ids)


def test_build_random_tree_single_room_is_the_root_with_no_children():
    tree = build_random_tree(["only"], random.Random(1))
    assert tree.room_id == "only"
    assert tree.left is None and tree.right is None


def test_build_random_tree_rejects_empty_room_list():
    with pytest.raises(ValueError):
        build_random_tree([], random.Random(1))


def test_build_random_tree_produces_varied_topologies_across_seeds():
    # confirma que "aleatoria" es real, no siempre la misma forma --
    # mismo tipo de test que ya existe para partition_tree.build_random_tree.
    room_ids = ["a", "b", "c", "d", "e", "f"]
    formas = set()
    for seed in range(20):
        tree = build_random_tree(room_ids, random.Random(seed))
        # "forma" simplificada: para cada nodo, que lados tiene ocupados
        forma = tuple(
            sorted(
                (n.room_id, n.left is not None, n.right is not None)
                for n in tree.nodes()
            )
        )
        formas.add(forma)
    assert (
        len(formas) > 1
    ), "todas las semillas dieron la misma topologia -- no es aleatorio de verdad"


def _arbol_simple():
    """salon(raiz) -> cocina(hijo izq, pegada a la derecha) -> trastero(hijo der de cocina, encima)"""
    salon = BStarNode("salon")
    cocina = BStarNode("cocina")
    trastero = BStarNode("trastero")
    salon.left = cocina
    cocina.right = trastero
    return salon


def test_swap_modules_exchanges_identity_not_shape():
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        swap_modules,
    )

    tree = _arbol_simple()
    nuevo = swap_modules(tree, "salon", "cocina")
    ids_antes = {n.room_id for n in tree.nodes()}
    ids_despues = {n.room_id for n in nuevo.nodes()}
    assert ids_antes == ids_despues  # mismos ids, solo cambia quien esta donde
    assert nuevo.room_id == "cocina"  # la raiz ahora es 'cocina' (antes 'salon')


def test_move_module_restructures_the_tree():
    # el mismo caso verificado en el prototipo: mover 'trastero' de
    # colgar de 'cocina' a colgar de 'dormitorio' cambia su posicion real.
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        move_module,
        compute_positions,
    )

    salon = BStarNode("salon")
    cocina = BStarNode("cocina")
    dormitorio = BStarNode("dormitorio")
    trastero = BStarNode("trastero")
    salon.left = cocina
    salon.right = dormitorio
    cocina.left = trastero
    areas = {"salon": 15.0, "cocina": 9.0, "dormitorio": 7.5, "trastero": 4.0}

    antes = compute_positions(salon, areas)
    nuevo = move_module(salon, "trastero", random.Random(1))
    despues = compute_positions(nuevo, areas)

    # con suficientes semillas, deberia encontrar una posicion distinta
    # -- probamos varias semillas para no depender de una concreta
    alguna_vez_cambio = False
    for seed in range(20):
        nuevo = move_module(salon, "trastero", random.Random(seed))
        despues = compute_positions(nuevo, areas)
        if antes["trastero"].bounds != despues["trastero"].bounds:
            alguna_vez_cambio = True
            break
    assert alguna_vez_cambio


def test_move_module_never_loses_or_duplicates_rooms():
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        move_module,
    )

    salon = BStarNode("salon")
    cocina = BStarNode("cocina")
    dormitorio = BStarNode("dormitorio")
    trastero = BStarNode("trastero")
    salon.left = cocina
    salon.right = dormitorio
    cocina.left = trastero
    ids_antes = {"salon", "cocina", "dormitorio", "trastero"}
    for seed in range(30):
        nuevo = move_module(salon, "trastero", random.Random(seed))
        ids_despues = {n.room_id for n in nuevo.nodes()}
        assert (
            ids_despues == ids_antes
        ), f"seed {seed}: se perdio o duplico una estancia"


def test_move_module_is_a_noop_for_nodes_with_children():
    # mover un nodo CON descendientes queda fuera de alcance -- debe
    # devolver el arbol sin cambios, no fallar ni corromper la estructura.
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        move_module,
    )

    tree = _arbol_simple()  # 'cocina' tiene un hijo (trastero)
    nuevo = move_module(tree, "cocina", random.Random(1))
    ids_antes = {n.room_id for n in tree.nodes()}
    ids_despues = {n.room_id for n in nuevo.nodes()}
    assert ids_antes == ids_despues


def test_resize_module_preserves_area():
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        resize_module,
        compute_positions,
    )

    tree = BStarNode("a", aspect_ratio=1.0)
    areas = {"a": 20.0}
    for seed in range(20):
        nuevo = resize_module(tree, "a", random.Random(seed))
        pos = compute_positions(nuevo, areas)
        assert pos["a"].area == pytest.approx(20.0)


def test_resize_module_stays_within_safety_bounds():
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        resize_module,
    )

    tree = BStarNode("a", aspect_ratio=1.0)
    for _ in range(300):
        tree = resize_module(tree, "a", random.Random())
        assert 0.05 <= tree.aspect_ratio <= 20.0


def test_reset_aspect_ratio_returns_to_square():
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        resize_module,
        reset_aspect_ratio,
    )

    tree = BStarNode("a", aspect_ratio=1.0)
    for seed in range(10):
        tree = resize_module(tree, "a", random.Random(seed))
    assert tree.aspect_ratio != 1.0  # confirma que si se desvio
    restablecido = reset_aspect_ratio(tree, "a")
    assert restablecido.aspect_ratio == 1.0


def test_force_aspect_ratio_sets_an_exact_value():
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        force_aspect_ratio,
    )

    tree = BStarNode("a", aspect_ratio=1.0)
    forzado = force_aspect_ratio(tree, "a", 3.5)
    assert forzado.aspect_ratio == 3.5
    assert (
        tree.aspect_ratio == 1.0
    )  # no muta el original, mismo convenio que el resto de movimientos


def test_force_aspect_ratio_survives_being_reapplied_after_any_mutation():
    # mismo patron que usa BTreeLayoutGenerator: tras CUALQUIER mutacion
    # (incluido un swap, que puede mover la identidad de la estancia
    # anclada a un nodo con otra proporcion), reaplicar force_aspect_ratio
    # debe devolver siempre la proporcion objetivo, sin importar que
    # movimiento ocurrio ni que nodo represente ahora esa estancia.
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        force_aspect_ratio,
        random_neighbor,
    )

    tree = BStarNode("stair", aspect_ratio=2.0)
    tree.left = BStarNode("bed", aspect_ratio=1.0)
    tree.right = BStarNode("bath", aspect_ratio=1.0)
    areas = {"stair": 4.0, "bed": 10.0, "bath": 5.0}
    rng = random.Random(0)

    for _ in range(50):
        tree = random_neighbor(tree, rng, areas)
        tree = force_aspect_ratio(tree, "stair", 2.0)
        nodo_escalera = next(n for n in tree.nodes() if n.room_id == "stair")
        assert nodo_escalera.aspect_ratio == 2.0


def test_swap_children_exchanges_left_and_right():
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        swap_children,
    )

    salon = BStarNode("salon")
    cocina = BStarNode("cocina")
    dormitorio = BStarNode("dormitorio")
    salon.left = cocina
    salon.right = dormitorio
    nuevo = swap_children(salon, "salon")
    assert nuevo.left.room_id == "dormitorio"
    assert nuevo.right.room_id == "cocina"


def test_random_neighbor_never_loses_or_duplicates_rooms():
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        random_neighbor,
    )

    room_ids = ["a", "b", "c", "d", "e"]
    areas = {rid: 10.0 for rid in room_ids}
    tree = build_random_tree(room_ids, random.Random(1))
    for seed in range(100):
        tree = random_neighbor(tree, random.Random(seed), areas)
        assert sorted(n.room_id for n in tree.nodes()) == sorted(room_ids)


def test_random_neighbor_locking_rejects_real_collateral_displacement():
    # mismo caso verificado en el prototipo: bloquear 'trastero' y
    # forzar un cambio que SI la desplazaria (cambiar 'cocina', de la
    # que 'trastero' cuelga como hijo derecho, apoyada en su contorno)
    # -- el movimiento debe rechazarse, no aplicarse.
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        random_neighbor,
        compute_positions,
    )

    salon = BStarNode("salon")
    cocina = BStarNode("cocina")
    trastero = BStarNode("trastero")
    salon.left = cocina
    cocina.right = trastero
    areas = {"salon": 15.0, "cocina": 12.0, "trastero": 4.0}
    bloqueadas = {"trastero"}

    pos_antes = compute_positions(salon, areas)
    cambios_reales = 0
    for seed in range(200):
        nuevo = random_neighbor(
            salon, random.Random(seed), areas, locked_room_ids=bloqueadas
        )
        pos_despues = compute_positions(nuevo, areas)
        if pos_antes["trastero"].bounds != pos_despues["trastero"].bounds:
            cambios_reales += 1
    # con ESCAPE_PROBABILITY=0.15, se esperan algunos cambios (~15% de
    # 200 = ~30), pero NO la mayoria -- confirma que el bloqueo protege
    # de verdad la mayor parte del tiempo, no que la valvula de escape
    # nunca se activa (lo cual seria sospechoso, no bloqueo real).
    assert 0 < cambios_reales < 100


def test_random_neighbor_locking_none_preserves_previous_behavior():
    from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
        random_neighbor,
    )

    room_ids = ["a", "b", "c"]
    areas = {rid: 10.0 for rid in room_ids}
    tree = build_random_tree(room_ids, random.Random(1))
    for seed in range(20):
        nuevo = random_neighbor(tree, random.Random(seed), areas, locked_room_ids=None)
        assert sorted(n.room_id for n in nuevo.nodes()) == sorted(room_ids)

"""Tests para la fábrica de casos de uso en `container.py` -- el árbol
B* es el ÚNICO generador desde [ARCH:btree-generador-por-defecto]: el
generador clásico (`SimulatedAnnealingLayoutGenerator`, árbol de
partición/guillotina) se eliminó por completo del proyecto a petición
explícita del usuario, tras confirmar en la práctica que el árbol B*
converge mejor en todos los casos difíciles probados a lo largo de
la sesión.
"""
from housing_generator.config.container import (
    build_generate_building_use_case,
    build_generate_layout_use_case,
)
from housing_generator.infrastructure.algorithms.layout_generation.btree_layout_generator import (
    BTreeLayoutGenerator,
)
from housing_generator.infrastructure.algorithms.constraints.composite_constraint_validator import (
    CompositeConstraintValidator,
)


def test_btree_is_the_only_generator_for_building_use_case():
    use_case = build_generate_building_use_case(seed=1, max_iterations=1000)
    composite = CompositeConstraintValidator([])
    generator = use_case._layout_generator_factory(composite, [], None)
    assert isinstance(generator, BTreeLayoutGenerator)


def test_btree_is_the_only_generator_for_layout_use_case():
    use_case = build_generate_layout_use_case(seed=1, max_iterations=1000)
    assert isinstance(use_case._layout_generator, BTreeLayoutGenerator)

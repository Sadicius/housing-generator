"""Tests para la fábrica de casos de uso en `container.py` -- en
particular, la selección de generador (árbol B* por defecto desde
[ARCH:btree-generador-por-defecto], confirmado con el usuario tras la
Fase 5 de la migración; `SimulatedAnnealingLayoutGenerator` disponible
como opt-in vía `usar_generador_clasico`).
"""
from housing_generator.config.container import build_generate_building_use_case
from housing_generator.infrastructure.algorithms.layout_generation.btree_layout_generator import (
    BTreeLayoutGenerator,
)
from housing_generator.infrastructure.algorithms.layout_generation.simulated_annealing_generator import (
    SimulatedAnnealingLayoutGenerator,
)
from housing_generator.infrastructure.algorithms.constraints.composite_constraint_validator import (
    CompositeConstraintValidator,
)


def test_btree_is_the_generator_used_by_default():
    use_case = build_generate_building_use_case(seed=1, max_iterations=1000)
    composite = CompositeConstraintValidator([])
    generator = use_case._layout_generator_factory(composite, [])
    assert isinstance(generator, BTreeLayoutGenerator)


def test_generador_clasico_true_selects_the_classic_generator():
    use_case = build_generate_building_use_case(seed=1, max_iterations=1000, usar_generador_clasico=True)
    composite = CompositeConstraintValidator([])
    generator = use_case._layout_generator_factory(composite, [])
    assert isinstance(generator, SimulatedAnnealingLayoutGenerator)


def test_generador_clasico_false_explicit_still_selects_btree():
    use_case = build_generate_building_use_case(seed=1, max_iterations=1000, usar_generador_clasico=False)
    composite = CompositeConstraintValidator([])
    generator = use_case._layout_generator_factory(composite, [])
    assert isinstance(generator, BTreeLayoutGenerator)

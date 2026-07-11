"""Composition root: conecta las implementaciones concretas de
infraestructura con los casos de uso de aplicacion a traves de sus
puertos. Este es el UNICO lugar del codebase que puede conocer a la vez
las clases concretas y los puertos; el resto del sistema solo conoce
interfaces (ports).
"""
from typing import Optional, List
from housing_generator.application.use_cases.generate_layout import GenerateLayoutUseCase
from housing_generator.infrastructure.algorithms.zoning.treemap_zoning import TreemapZoningStrategy
from housing_generator.infrastructure.algorithms.layout_generation.simulated_annealing_generator import (
    SimulatedAnnealingLayoutGenerator,
)
from housing_generator.infrastructure.algorithms.constraints.adjacency_validator import (
    AdjacencyConstraintValidator,
)
from housing_generator.infrastructure.algorithms.constraints.composite_constraint_validator import (
    CompositeConstraintValidator,
)
from housing_generator.infrastructure.algorithms.constraints.wet_core_validator import (
    build_wet_core_validator,
)
from housing_generator.infrastructure.algorithms.constraints.day_night_zoning_validator import (
    build_day_zone_grouping_validator,
    build_night_zone_grouping_validator,
    build_service_zone_grouping_validator,
)
from housing_generator.infrastructure.algorithms.constraints.estancia_minimum_area_validator import (
    EstanciaMinimumAreaValidator,
)
from housing_generator.infrastructure.algorithms.constraints.servicio_minimum_area_validator import (
    ServicioMinimumAreaValidator,
)
from housing_generator.infrastructure.algorithms.constraints.dormitorio_armario_validator import (
    DormitorioArmarioValidator,
)
from housing_generator.infrastructure.algorithms.constraints.trastero_minimum_area_validator import (
    TrasteroMinimumAreaValidator,
)
from housing_generator.infrastructure.algorithms.constraints.ancho_libre_estancia_validator import (
    AnchoLibreEstanciaValidator,
)
from housing_generator.infrastructure.algorithms.constraints.ancho_libre_practico_validator import (
    AnchoLibrePracticoValidator,
)
from housing_generator.infrastructure.algorithms.constraints.ancho_libre_pasillo_validator import (
    AnchoLibrePasilloValidator,
)
from housing_generator.infrastructure.algorithms.constraints.altura_libre_validator import (
    AlturaLibreValidator,
)
from housing_generator.infrastructure.algorithms.constraints.exterior_contact_validator import (
    ExteriorContactValidator,
)
from housing_generator.infrastructure.algorithms.constraints.cocina_integrada_validator import (
    CocinaIntegradaValidator,
)
from housing_generator.infrastructure.algorithms.constraints.vivienda_minima_validator import (
    ViviendaMinimaValidator,
)
from housing_generator.infrastructure.algorithms.constraints.espacio_acceso_validator import (
    EspacioAccesoValidator,
)
from housing_generator.infrastructure.algorithms.constraints.bano_acceso_validator import (
    BanoAccesoGeneralValidator,
)
from housing_generator.infrastructure.algorithms.constraints.escalera_ancho_libre_validator import (
    EscaleraAnchoLibreValidator,
)
from housing_generator.infrastructure.algorithms.constraints.pasillo_topologia_validator import (
    PasilloTopologiaValidator,
)
from housing_generator.infrastructure.algorithms.constraints.escalera_alineacion_validator import (
    EscaleraAlineacionValidator,
)
from housing_generator.infrastructure.algorithms.constraints.nucleo_humedo_vertical_validator import (
    NucleoHumedoVerticalValidator,
)
from housing_generator.infrastructure.algorithms.layout_generation.soft_constraint_scorer import (
    SoftConstraintScorer,
)
from housing_generator.application.use_cases.generate_building import GenerateBuildingUseCase
from housing_generator.infrastructure.algorithms.adjacency.geometry_adjacency_graph_builder import (
    GeometryAdjacencyGraphBuilder,
)

# Umbral de adyacencia interior (pared compartida entre estancias),
# confirmado por el usuario para el grafo de adyacencia real.
ADJACENCY_MIN_SHARED_EDGE_M = 0.1


def build_per_floor_validators(
    adjacency_requirements, graph_builder, total_num_estancias=None, global_rank=None,
) -> List:
    """Validadores que tiene sentido aplicar a UNA SOLA planta (Layout).

    IMPORTANTE (encontrado al construir GenerateBuildingUseCase):
    `ViviendaMinimaValidator` (necesita ver las 6 piezas del programa
    minimo juntas) y `BanoAccesoGeneralValidator` (podria depender de un
    bano en OTRA planta) son de ambito de EDIFICIO, no de planta -- se
    excluyen aqui deliberadamente y se comprueban aparte, a nivel de
    `Building` completo (ver `generate_building.py`).

    `total_num_estancias` / `global_rank`: numero y ranking de estancias
    del EDIFICIO COMPLETO (no solo de esta planta), para que Tabla 1/2
    elijan la fila Y el puesto correctos -- dos bugs reales encontrados
    al generar el primer edificio de 2 plantas de prueba, ambos
    [RESUELTOS] ahora. `None` (por defecto, caso de una sola planta)
    preserva el comportamiento anterior: se calcula localmente, que en
    ese caso coincide exactamente con el total/ranking del edificio.
    """
    return [
        AdjacencyConstraintValidator(adjacency_requirements),
        build_wet_core_validator(graph_builder),
        build_day_zone_grouping_validator(graph_builder),
        build_night_zone_grouping_validator(graph_builder),
        build_service_zone_grouping_validator(graph_builder),
        EstanciaMinimumAreaValidator(
            total_num_estancias_override=total_num_estancias, global_rank_override=global_rank,
        ),
        ServicioMinimumAreaValidator(total_num_estancias_override=total_num_estancias),
        DormitorioArmarioValidator(),
        TrasteroMinimumAreaValidator(),
        AnchoLibreEstanciaValidator(),
        AnchoLibrePracticoValidator(),
        AnchoLibrePasilloValidator(),
        AlturaLibreValidator(),
        ExteriorContactValidator(),
        CocinaIntegradaValidator(total_num_estancias_override=total_num_estancias),
        EspacioAccesoValidator(),
        EscaleraAnchoLibreValidator(),
        PasilloTopologiaValidator(graph_builder),
    ]


def build_generate_layout_use_case(
    adjacency_requirements: Optional[List] = None,
    max_iterations: int = 2000,
    seed: Optional[int] = None,
) -> GenerateLayoutUseCase:
    """Fabrica el caso de uso GenerateLayout con TODAS las reglas
    construidas hasta ahora, combinadas via CompositeConstraintValidator:
    geometria/must_be_away, nucleo humedo, zonificacion dia/noche/
    servicio, Tabla 1 (+ cuadrado inscribible de estancia mayor), Tabla 2,
    armario empotrado por dormitorio, trastero (B.2.5), ancho libre por
    estancia (A.3.2.1), ancho libre de pasillo (A.3.2.3) y altura libre
    (A.3.1.1).

    Para vivienda de UNA sola planta (caso de uso original, sin cambios
    de comportamiento): usa `build_per_floor_validators` + los dos que
    son de ambito de edificio (`ViviendaMinimaValidator`,
    `BanoAccesoGeneralValidator`) -- con una unica planta, "edificio" y
    "planta" son lo mismo, asi que aplicarlos aqui sigue siendo correcto.

    El generador es SimulatedAnnealingLayoutGenerator: construye un unico
    arbol de particion sobre TODAS las estancias (sin fase previa de
    zonificacion geometrica) y busca la mejor topologia minimizando el
    numero de violaciones del mismo composite -- ver docs/architecture.md
    seccion de limitaciones conocidas para el porque de este cambio.
    """
    graph_builder = GeometryAdjacencyGraphBuilder(min_shared_edge_m=ADJACENCY_MIN_SHARED_EDGE_M)

    validators = build_per_floor_validators(adjacency_requirements, graph_builder) + [
        ViviendaMinimaValidator(),
        BanoAccesoGeneralValidator(graph_builder),
    ]
    composite = CompositeConstraintValidator(validators)
    soft_scorer = SoftConstraintScorer(adjacency_requirements or [], graph_builder)

    layout_generator = SimulatedAnnealingLayoutGenerator(
        constraint_validator=composite,
        max_iterations=max_iterations,
        seed=seed,
        soft_constraint_scorer=soft_scorer,
    )

    return GenerateLayoutUseCase(
        zoning_strategy=TreemapZoningStrategy(),
        layout_generator=layout_generator,
        constraint_validator=composite,
    )


def build_generate_building_use_case(
    adjacency_requirements: Optional[List] = None,
    max_iterations: int = 2000,
    seed: Optional[int] = None,
) -> GenerateBuildingUseCase:
    """Fabrica GenerateBuildingUseCase con las fabricas concretas
    (per_floor_validators_factory, layout_generator_factory) ya
    resueltas -- unico punto del sistema que conecta el caso de uso
    multi-planta con las clases de infraestructura reales, siguiendo el
    mismo patron que build_generate_layout_use_case."""
    graph_builder = GeometryAdjacencyGraphBuilder(min_shared_edge_m=ADJACENCY_MIN_SHARED_EDGE_M)

    def per_floor_validators_factory(
        level_adjacency, reference_stair, reference_wet, total_num_estancias, global_rank, floor_below_exists,
    ):
        validators = build_per_floor_validators(
            level_adjacency, graph_builder, total_num_estancias, global_rank,
        ) + [
            EscaleraAlineacionValidator(
                reference_boundary=reference_stair, floor_below_exists=floor_below_exists,
            ),
            NucleoHumedoVerticalValidator(reference_wet_boundaries=reference_wet),
        ]
        return CompositeConstraintValidator(validators)

    def layout_generator_factory(composite, level_adjacency):
        soft_scorer = SoftConstraintScorer(level_adjacency, graph_builder)
        return SimulatedAnnealingLayoutGenerator(
            constraint_validator=composite,
            max_iterations=max_iterations,
            seed=seed,
            soft_constraint_scorer=soft_scorer,
        )

    return GenerateBuildingUseCase(
        per_floor_validators_factory=per_floor_validators_factory,
        layout_generator_factory=layout_generator_factory,
        zoning_strategy=TreemapZoningStrategy(),
        programa_minimo_validator=ViviendaMinimaValidator(),
        bano_acceso_validator=BanoAccesoGeneralValidator(graph_builder),
        adjacency_requirements=adjacency_requirements,
    )

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
from housing_generator.infrastructure.algorithms.adjacency.geometry_adjacency_graph_builder import (
    GeometryAdjacencyGraphBuilder,
)

# Umbral de adyacencia interior (pared compartida entre estancias),
# confirmado por el usuario para el grafo de adyacencia real.
ADJACENCY_MIN_SHARED_EDGE_M = 0.1


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

    El generador es SimulatedAnnealingLayoutGenerator: construye un unico
    arbol de particion sobre TODAS las estancias (sin fase previa de
    zonificacion geometrica) y busca la mejor topologia minimizando el
    numero de violaciones del mismo composite -- ver docs/architecture.md
    seccion de limitaciones conocidas para el porque de este cambio.
    """
    graph_builder = GeometryAdjacencyGraphBuilder(min_shared_edge_m=ADJACENCY_MIN_SHARED_EDGE_M)

    validators = [
        AdjacencyConstraintValidator(adjacency_requirements),
        build_wet_core_validator(graph_builder),
        build_day_zone_grouping_validator(graph_builder),
        build_night_zone_grouping_validator(graph_builder),
        build_service_zone_grouping_validator(graph_builder),
        EstanciaMinimumAreaValidator(),
        ServicioMinimumAreaValidator(),
        DormitorioArmarioValidator(),
        TrasteroMinimumAreaValidator(),
        AnchoLibreEstanciaValidator(),
        AnchoLibrePasilloValidator(),
        AlturaLibreValidator(),
        ExteriorContactValidator(),
        CocinaIntegradaValidator(),
        ViviendaMinimaValidator(),
    ]
    composite = CompositeConstraintValidator(validators)

    layout_generator = SimulatedAnnealingLayoutGenerator(
        constraint_validator=composite,
        max_iterations=max_iterations,
        seed=seed,
    )

    return GenerateLayoutUseCase(
        zoning_strategy=TreemapZoningStrategy(),
        layout_generator=layout_generator,
        constraint_validator=composite,
    )

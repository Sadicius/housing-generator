from abc import ABC, abstractmethod
import networkx as nx
from housing_generator.domain.entities.layout import Layout


class AdjacencyGraphBuilderPort(ABC):
    """Construye el grafo de adyacencia REAL a partir de la geometria ya
    generada de un Layout (quien toca a quien de verdad).

    Distinto de BuildAdjacencyGraphUseCase: aquel construye un grafo a
    partir de AdjacencyRequirement (intencion declarada antes de generar);
    este se construye a partir del resultado geometrico ya colocado.
    """

    @abstractmethod
    def build(self, layout: Layout) -> nx.Graph:
        ...

from abc import ABC, abstractmethod
from typing import List, Optional
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement


class LayoutRepositoryPort(ABC):
    """Persistencia de layouts generados (JSON, base de datos, etc.)."""

    @abstractmethod
    def save(
        self, layout: Layout, path: str,
        adjacency_requirements: Optional[List[AdjacencyRequirement]] = None,
    ) -> None:
        ...

    @abstractmethod
    def load(self, path: str) -> Layout:
        ...

from abc import ABC, abstractmethod
from housing_generator.domain.entities.layout import Layout


class LayoutRepositoryPort(ABC):
    """Persistencia de layouts generados (JSON, base de datos, etc.)."""

    @abstractmethod
    def save(self, layout: Layout, path: str) -> None:
        ...

    @abstractmethod
    def load(self, path: str) -> Layout:
        ...

from abc import ABC, abstractmethod
from typing import List
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.zone import Zone


class ZoningStrategyPort(ABC):
    """Agrupa las estancias de un programa en macro-zonas (dia/noche/servicio).

    Puerto (interfaz) segun arquitectura hexagonal: la capa de aplicacion
    depende de esta abstraccion, nunca de una implementacion concreta.
    """

    @abstractmethod
    def build_zones(self, program: Program) -> List[Zone]: ...

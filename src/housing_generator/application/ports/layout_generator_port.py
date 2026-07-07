from abc import ABC, abstractmethod
from typing import List
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.zone import Zone
from housing_generator.domain.entities.layout import Layout


class LayoutGeneratorPort(ABC):
    """Coloca las estancias de un programa dentro de un solar, respetando
    las zonas dadas. Distintas estrategias (slicing, grafos, geneticos,
    CSP...) implementan este mismo puerto y son intercambiables."""

    @abstractmethod
    def generate(self, program: Program, lot: Lot, zones: List[Zone]) -> Layout:
        ...

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import NivelPlanta, NIVEL_PLANTA_ORDEN


@dataclass
class Building:
    """Vivienda de varias plantas: una `Layout` completa por cada
    `NivelPlanta` presente, generada de forma independiente pero
    coordinada entre plantas verticalmente adyacentes (huella de
    escalera alineada, nucleo humedo solapado -- ver validadores
    entre plantas en `infrastructure/algorithms/constraints`).

    Deliberadamente NO reemplaza a `Layout` para el caso de una sola
    planta: `Layout` sigue siendo el resultado de una vivienda simple,
    `Building` es la composicion de varias cuando hace falta.
    """
    floors: Dict[NivelPlanta, Layout] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return bool(self.floors) and all(layout.is_complete for layout in self.floors.values())

    def ordered_levels(self) -> List[NivelPlanta]:
        """Los niveles realmente presentes en este Building, de abajo a
        arriba -- subconjunto de NIVEL_PLANTA_ORDEN, no todos los 5
        tienen por que existir."""
        return [level for level in NIVEL_PLANTA_ORDEN if level in self.floors]

    def level_below(self, level: NivelPlanta) -> Optional[NivelPlanta]:
        """El nivel inmediatamente inferior YA PRESENTE en este Building
        (no necesariamente el anterior en NIVEL_PLANTA_ORDEN si ese nivel
        intermedio no existe en esta vivienda concreta)."""
        present = self.ordered_levels()
        idx = present.index(level) if level in present else -1
        if idx <= 0:
            return None
        return present[idx - 1]

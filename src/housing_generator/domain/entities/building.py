from dataclasses import dataclass, field
from typing import Dict, List, Optional
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import NivelPlanta, NIVEL_PLANTA_ORDEN


@dataclass
class Building:
    """Vivienda de varias plantas: una `Layout` completa por cada
    `NivelPlanta` presente, coordinada verticalmente (huella de
    escalera alineada, núcleo húmedo solapado). No reemplaza a
    `Layout` para una sola planta -- `Building` es la composición de
    varias.
    """
    floors: Dict[NivelPlanta, Layout] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return bool(self.floors) and all(layout.is_complete for layout in self.floors.values())

    def ordered_levels(self) -> List[NivelPlanta]:
        """Niveles presentes, de abajo a arriba (subconjunto de
        NIVEL_PLANTA_ORDEN)."""
        return [level for level in NIVEL_PLANTA_ORDEN if level in self.floors]

    def level_below(self, level: NivelPlanta) -> Optional[NivelPlanta]:
        """Nivel inmediatamente inferior ya presente en este Building
        (no necesariamente el anterior en NIVEL_PLANTA_ORDEN)."""
        present = self.ordered_levels()
        idx = present.index(level) if level in present else -1
        if idx <= 0:
            return None
        return present[idx - 1]

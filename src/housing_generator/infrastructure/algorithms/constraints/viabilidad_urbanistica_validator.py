"""Comprobación de viabilidad urbanística -- se ejecuta ANTES de
intentar generar nada, no después de que la búsqueda falle sola.
Mismo espíritu que un "informe de viabilidad" real (ver
docs/referencia/generador/ para el contexto completo de por qué se
añadió esto) -- y el mismo patrón que usan herramientas reales de
diseño generativo (Finch: "como un corrector ortográfico para
plantas", avisa al instante contra reglas de área/ratios).

A diferencia del resto de validadores (`ConstraintValidatorPort`,
operan sobre un `Layout` ya colocado con geometría real), este
comprueba SUPERFICIES DECLARADAS contra los parámetros urbanísticos
de la parcela -- no necesita esperar a que nada se coloque.

Cada parámetro es opcional (`None` = sin esa restricción, mismo
convenio que `Lot.retranqueo_m`) -- los valores concretos vienen
siempre del usuario (de su PGOU/ficha urbanística real), nunca
inventados aquí. Ver [ARCH:viabilidad-urbanistica].
"""
from typing import List
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.application.ports.viabilidad_urbanistica_validator_port import (
    ViabilidadUrbanisticaValidatorPort,
)
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.program import Program


class ViabilidadUrbanisticaValidator(ViabilidadUrbanisticaValidatorPort):
    """Comprueba edificabilidad, ocupación, altura y frente de fachada
    -- los cuatro parámetros estándar de una ficha urbanística real
    (confirmado contra varios PGOU municipales, no solo teoría).
    Ver [ARCH:viabilidad-urbanistica]."""

    def validate(self, program: Program, lot: Lot, num_plantas: int) -> ValidationResult:
        violations: List[str] = []
        # hallazgo real, confirmado por el usuario con captura del
        # navegador: si hay poligono_real (importado de Catastro), la
        # superficie de parcela debe ser la REAL, no la del rectangulo
        # de trabajo (que puede sobrestimarla hasta un 12-22%,
        # confirmado con 2 parcelas reales de Galicia). Ver [ARCH:parcela-real].
        superficie_parcela = lot.poligono_real.area if lot.poligono_real is not None else lot.boundary.polygon.area

        if lot.coeficiente_edificabilidad is not None:
            techo_declarado = sum(r.dimensions.area_m2 for r in program.rooms)
            techo_maximo = lot.coeficiente_edificabilidad * superficie_parcela
            if techo_declarado > techo_maximo:
                violations.append(
                    f"Edificabilidad superada: el programa declara {techo_declarado:.1f}m² de "
                    f"techo (todas las plantas), pero el coeficiente de edificabilidad "
                    f"({lot.coeficiente_edificabilidad:.2f} m²t/m²s) sobre {superficie_parcela:.1f}m² "
                    f"de parcela solo permite {techo_maximo:.1f}m²"
                )

        if lot.ocupacion_maxima_pct is not None:
            # estimacion de la huella: la planta con MAS superficie
            # declarada de todas, no siempre la baja -- mas
            # conservador si alguna planta superior resulta mayor
            # (voladizos, por ejemplo). Chequeo "a mano" deliberado
            # (FAR/ocupacion x superficie), no un solver de envolvente
            # preciso -- mismo nivel de sofisticacion que un chequeo
            # rapido de viabilidad, no un estudio tecnico completo.
            superficie_por_planta: dict = {}
            for room in program.rooms:
                nivel = room.level.value if room.level else "sin_nivel"
                superficie_por_planta[nivel] = superficie_por_planta.get(nivel, 0.0) + room.dimensions.area_m2
            huella_estimada = max(superficie_por_planta.values()) if superficie_por_planta else 0.0
            huella_maxima = (lot.ocupacion_maxima_pct / 100.0) * superficie_parcela
            if huella_estimada > huella_maxima:
                violations.append(
                    f"Ocupación superada: la planta más grande declara {huella_estimada:.1f}m² "
                    f"(estimación de la huella), pero la ocupación máxima "
                    f"({lot.ocupacion_maxima_pct:.0f}%) sobre {superficie_parcela:.1f}m² de "
                    f"parcela solo permite {huella_maxima:.1f}m²"
                )

        if lot.altura_maxima_plantas is not None and num_plantas > lot.altura_maxima_plantas:
            violations.append(
                f"Altura superada: el programa declara {num_plantas} plantas, pero la altura "
                f"máxima permitida es de {lot.altura_maxima_plantas} plantas"
            )

        if lot.frente_minimo_m is not None and lot.frente_actual_m < lot.frente_minimo_m:
            violations.append(
                f"Frente de fachada insuficiente: la parcela mide {lot.frente_actual_m:.1f}m "
                f"en el lado de calle ('{lot.street_side}'), pero el frente mínimo exigido es "
                f"de {lot.frente_minimo_m:.1f}m"
            )

        return ValidationResult(violations=violations)

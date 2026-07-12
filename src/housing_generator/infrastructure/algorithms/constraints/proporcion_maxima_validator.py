from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout

# NO NORMATIVO -- criterio de diseno arquitectonico, confirmado
# explicitamente con el usuario, no un valor del Decreto 29/2010 ni de
# ningun otro documento basico. Investigado antes de fijar el valor:
# no existe un limite normativo de proporcion (ancho:alto) en ninguna
# fuente consultada -- solo guia de diseno de interiores (proporcion
# "agradable" entre 1:1.5 y 1:2.5, con la razon aurea ~1.6:1 como
# referencia clasica) y la propia literatura de generacion procedural
# de plantas (Bruls/Huizing/van Wijk 2000, Marson & Musse 2010), que
# busca acercarse a 1:1 pero sin fijar un maximo absoluto como regla
# dura. 2.5 elegido como el extremo mas permisivo de la guia
# encontrada, no el mas estricto.
#
# Retomado de una bateria de 5 casos REALES (generados con el propio
# panel automatico del dashboard, no sinteticos) que el usuario pidio
# probar explicitamente: una vivienda de 5 dormitorios produjo un
# dormitorio de 2.11m x 20.00m (9.5:1) y un pasillo de 3.96m x 20.00m
# (5.1:1) -- ambos NORMATIVAMENTE validos (superan el ancho minimo
# exigido) pero arquitectonicamente absurdos. Investigada la causa
# antes de anadir esto a ciegas: confirmado matematicamente (200000
# pruebas aleatorias, cero discrepancias) que la heuristica de "cortar
# por el lado mas largo" en place_tree YA es la eleccion optima para
# minimizar la proporcion resultante en un corte binario -- el
# problema no es la direccion de corte, es que dos hojas de area muy
# distinta como hermanas en el arbol fuerzan un reparto desigual que
# NINGUNA direccion de corte puede evitar. Por eso hace falta esta red
# de seguridad explicita, no solo una heuristica de generacion mejor.
PROPORCION_MAXIMA = 2.5


class ProporcionMaximaValidator(ConstraintValidatorPort):
    """Proporcion ancho:alto maxima NO NORMATIVA (2.5:1, confirmada
    explicitamente, no del Decreto 29/2010) para CUALQUIER estancia --
    a diferencia de los validadores de ancho minimo (que solo cubren
    tipos concretos), esta es una comprobacion geometrica general:
    evita tiras finas que cumplen el ancho minimo exigido pero son
    arquitectonicamente absurdas (p.ej. un dormitorio de 20m de largo)."""

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        for room in layout.rooms:
            if not room.is_placed:
                continue
            bounds = room.boundary.polygon.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            if width <= 0 or height <= 0:
                continue
            ratio = max(width, height) / min(width, height)
            if ratio > PROPORCION_MAXIMA:
                violations.append(
                    f"'{room.id}': proporcion {ratio:.1f}:1 ({width:.2f}m x {height:.2f}m) por encima "
                    f"del maximo practico de {PROPORCION_MAXIMA:.1f}:1 (NO normativo -- criterio de "
                    f"ingenieria confirmado, evita formas alargadas absurdas)"
                )

        return ValidationResult(violations=violations, warnings=warnings)

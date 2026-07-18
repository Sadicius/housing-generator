# Validadores -- geometría general (proporción, exterior, altura)

## ProporcionMaximaValidator [ARCH:proporcion-maxima]

Proporción máxima **2.5:1, explícitamente NO normativa** (no existe
límite normativo de proporción en el Decreto 29/2010 ni el CTE --
motivo y valor exacto: ver docstring de `proporcion_maxima_validator.py`),
siempre activa, para CUALQUIER estancia -- red de seguridad general
frente a los validadores de ancho mínimo, que solo cubren tipos
concretos. Origen: una batería de 5 escenarios reales generados por el
panel automático del dashboard reveló estancias de hasta 9.5:1,
normativamente válidas pero absurdas -- historial completo en
`docs/historico/architecture.md`, `[ARCH:proporcion-maxima]`.

## [ARCH:exterior-contact] ExteriorContactValidator

Comprueba contra el borde del ÁREA EDIFICABLE, no de la parcela legal
completa -- con retranqueo declarado, la construcción nunca toca la
línea de parcela real, así que comprobar contra ella nunca daría
contacto exterior válido. Sin retranqueo, ambas coinciden.

Vivienda pareada/adosada: los lados de medianera sí forman parte del
área edificable, pero una pared de medianera no tiene luz ni
ventilación propia -- no cuenta como contacto exterior real aunque
geométricamente toque el borde.

## [ARCH:altura-libre] AlturaLibreValidator

A.3.1.1: altura libre mínima (2.50m mayoría de piezas, 2.20m
directamente permitida en vestíbulo/pasillo/escaleras/baño/aseo/
lavadero/tendedero/garajes de vivienda unifamiliar). En el resto de
piezas, 2.20-2.50m es AVISO (no violación) -- podría cumplir vía la
excepción del 30% de superficie que este proyecto no calcula
(geometría parcial fuera de alcance, igual que la propia fuente
admite no calcular). Solo cuarto técnico queda fuera de alcance.

Bug real corregido: GARAGE estaba antes en fuera-de-alcance (sin
comprobar) y STAIRCASE en ninguna lista (caía en el caso general más
estricto) -- ambos explícitamente nombrados en A.3.1.1.b.

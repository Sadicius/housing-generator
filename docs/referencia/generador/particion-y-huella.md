# Generador -- partición y huella construible

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:partition-node] PartitionNode y place_tree

`direction=None` (automático) minimiza la peor proporción ancho:alto
resultante del corte -- regla real de squarified treemap (Bruls/
Huizing/van Wijk 2000, aplicada a plantas por Marson & Musse 2010).
La simplificación anterior ("cortar por el lado más largo") resultó
insuficiente: no mira el reparto de área real del corte, y un
contenedor casi cuadrado partido 90/10 sigue dando una tira fina en
cualquier dirección -- confirmado con un caso real (vivienda de 5
dormitorios, dormitorios de hasta 9.5:1). Investigado después con
200.000 pruebas aleatorias: la heurística "lado más largo" y la regla
completa (`_worst_aspect_ratio`, evalúa ambas orientaciones) dan
siempre el mismo resultado en un corte binario -- son equivalentes,
la dirección de corte nunca fue el problema real; ver
`[ARCH:proporcion-maxima]` para la causa raíz real y su arreglo.

`ratio_override`: proporción de corte forzada manualmente (0-1,
fracción de `first`), independiente del área declarada de las
estancias. Inspirado en Merrell/Schkufza/Koltun 2010 ("Sliding a
wall" como proposal move propio, distinto de "swapping rooms") --
investigación externa confirmada. Sin esto, la proporción de cada
corte quedaba siempre atada al área declarada, sin ningún grado de
libertad para ajustar forma/ancho libre sin cambiar topología.

`random_neighbor` -- 4 movimientos: intercambiar hojas, invertir
dirección (ciclo None→"h"→"v"→None, no un toggle binario, porque la
dirección "automática" depende del rectángulo real en el momento de
colocar, no se puede saber solo mirando el nodo), intercambiar
subárboles, y "deslizar pared" (`slide_wall`, el movimiento inspirado
en Merrell et al. arriba).

## [ARCH:simulated-annealing] SimulatedAnnealingLayoutGenerator

Árbol de partición sobre todas las estancias a la vez (sin fase previa
de macro-zona), recocido simulado sobre la topología. Función objetivo:
comparación LEXICOGRÁFICA real, tupla `(duro, blando)`, no suma
ponderada -- una versión anterior sumaba `duro*peso + blando`, que
garantiza el orden final pero rompe la dinámica de aceptación del
recocido (`exp(-delta/temperatura)` reacciona a la magnitud absoluta
del delta, no solo al orden relativo; confirmado que rompía tests que
no tocaban restricciones blandas). Con la tupla, si lo duro cambia, la
aceptación se decide solo por ese delta; lo blando solo entra cuando
lo duro empata.

Recibe `ConstraintValidatorPort` como dependencia propia (no solo
`GenerateLayoutUseCase`) porque lo invoca miles de veces durante la
búsqueda -- generación y validación acopladas en esta implementación
concreta, aunque ambas siguen siendo ports intercambiables en el
resto del sistema. `zones` del puerto se ignora deliberadamente.

`self._rng` se recrea en CADA llamada a `generate()` (bug real
corregido: antes se creaba una sola vez en `__init__`, así que `seed`
solo era reproducible en la primera llamada sobre el mismo generador).

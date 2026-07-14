# Validadores -- geometría general (proporción, exterior, altura)

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## ProporcionMaximaValidator -- cierre del hallazgo de la bateria de casos reales [ARCH:proporcion-maxima]

El usuario insistió en probar con casos reales de forma sistemática en
vez de confiar en tests sintéticos aislados -- confirmado que tenía
razón: una batería de 5 escenarios generados con el propio panel
automático del dashboard (no inventados a mano) reveló estancias de
hasta 9.5:1 (un dormitorio de 2.11m × 20.00m), normativamente válidas
pero absurdas.

- **[RESUELTO] Investigación antes de tocar código, a petición
  explícita del usuario**: comprobado que NO existe límite normativo
  de proporción en ninguna fuente (ni el Decreto 29/2010 ni el CTE) --
  solo guía de diseño de interiores (proporción "agradable" 1:1.5 a
  1:2.5, razón áurea ~1.6:1 como referencia). También investigada la
  regla REAL de squarified treemap (Bruls/Huizing/van Wijk 2000): no
  es solo "cortar por el lado más largo" (simplificación que ya
  teníamos) sino "elegir la orientación que minimiza la peor
  proporción resultante, dado el reparto de área real del corte".
- **Hallazgo matemático real, no asumido**: implementada la regla
  completa (`_worst_aspect_ratio` en `partition_tree.py`, evalúa ambas
  orientaciones) y confirmado con 200.000 pruebas aleatorias que
  produce EXACTAMENTE el mismo resultado que la heurística anterior
  ("cortar por el lado más largo") en el 100% de los casos -- son
  matemáticamente equivalentes para un corte binario. La heurística
  anterior YA era óptima; el problema nunca fue la dirección de corte.
  Se mantuvo la versión explícita (evalúa ambas, no asume) por ser más
  robusta de razonar y demostrar, aunque el resultado sea idéntico.
- **[RESUELTO] `ProporcionMaximaValidator`** (21º validador, siempre
  activo, no opt-in -- red de seguridad general): proporción máxima
  2.5:1 NO NORMATIVA (confirmada explícitamente con el usuario, el
  extremo más permisivo de la guía encontrada) para CUALQUIER
  estancia, a diferencia de los validadores de ancho mínimo que solo
  cubren tipos concretos. Causa raíz real: dos hojas de área muy
  distinta como hermanas en el árbol de partición fuerzan un reparto
  desigual que NINGUNA dirección de corte puede evitar -- por eso hace
  falta una red de seguridad explícita sobre el resultado final, no
  solo una heurística de generación mejor (que ya era óptima).
- **Confirmado con el mismo caso real que lo encontró**: la vivienda de
  5 dormitorios que producía 9.5:1 ahora converge en 15.2s (semilla 1
  directa, antes necesitaba varias) con una proporción máxima de
  2.32:1 en toda la vivienda.
- Semillas actualizadas tras el cambio (mismo patrón de siempre):
  CLI por defecto ahora `--seed 4`; `--lot-size` de referencia en
  tests cambiado de 11x10 a 12x10 (el caso ajustado anterior dejó de
  fallar con la semilla 1, necesitaba uno nuevo para seguir
  demostrando el reintento automático).
- Suite final: pyflakes y mypy limpios (82 archivos). Ver commit para
  el recuento total de tests.

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

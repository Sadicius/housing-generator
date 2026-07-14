# Validadores -- superficies mínimas (Tabla 1/2 y afines)

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:estancia-minimum-area] EstanciaMinimumAreaValidator

Tabla 1 (A.3.2.1): superficie mínima por puesto de tamaño entre las
estancias (space_category ESTANCIA). La "estancia mayor" para el
cuadrado inscribible (A.3.2.1.a) es SIEMPRE el salón -- regla de
proyecto, no derivación automática por área; el ranking de Tabla 1 es
un concepto independiente. Si no hay salón: usa la de mayor área como
alternativa, marcado como AVISO, nunca aprobación silenciosa.

`total_num_estancias_override`/`global_rank_override`: número y
ranking del EDIFICIO completo, no solo de esta planta -- dos bugs
reales corregidos al construir el primer edificio de 2 plantas de
prueba (una planta con 1 estancia aplicaba la fila de "vivienda de 1
estancia" en vez de la fila real del edificio).

En multi-planta, "no hay salón en esta planta" es el caso NORMAL para
plantas superiores (el salón está en otra planta) -- sustituir por la
mayor estancia local generaba violaciones falsas; corregido para no
sustituir en ese caso, la planta con el salón real ya lo comprueba
por su cuenta.

## [ARCH:servicio-minimum-area] ServicioMinimumAreaValidator

Tabla 2 (A.3.2.2): superficie mínima por tipo de servicio, según
número de estancias de la vivienda. "aseo" no aparece como clave
hasta 4 estancias -- fiel al original, no un olvido (con menos, la
norma no exige aseo independiente).

Alcance: "cocina integrada" y "trastero" (B.2.5, regla fija) NO se
comprueban aquí -- tienen sus propios validadores dedicados
(`CocinaIntegradaValidator`, `TrasteroMinimumAreaValidator`).
`total_num_estancias_override`: mismo motivo que
`EstanciaMinimumAreaValidator`, edificio completo en multi-planta.

## [ARCH:cocina-integrada] CocinaIntegradaValidator

Cocina abierta en un único espacio con la estancia mayor: la
superficie mínima del conjunto es la SUMA de los mínimos de cada
pieza por separado (Tabla 1 + Tabla 2), no un número fijo propio. Tres
casos: sin cocina integrada declarada = no aplica (lista vacía, no es
"no verificable"); con cocina pero sin salón = aviso; con ambos = se
comprueba superficie combinada + apertura vertical mínima.

`total_num_estancias_override`: bug real corregido -- este validador
nunca recibió el mismo arreglo multi-planta que sus dos primos
(`EstanciaMinimumAreaValidator`, `ServicioMinimumAreaValidator`). Sin
esto, en un edificio de 2 plantas podía aprobar silenciosamente una
superficie combinada insuficiente para el edificio completo.

## [ARCH:trastero-minimum-area] TrasteroMinimumAreaValidator

B.2.5: superficie mínima FIJA (4.00m², no escala con estancias, a
diferencia de "almacenamiento" en Tabla 2). Confirmado en `nhv.lua`
(NHV.trastero.area = 4.00), con la propia fuente admitiendo que nunca
estuvo realmente implementada pese a estar declarada. Ancho de puerta
(0.80m, también en B.2.5) pendiente -- requiere modelar puertas.

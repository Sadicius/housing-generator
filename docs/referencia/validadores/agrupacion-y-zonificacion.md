# Validadores -- agrupación y zonificación (núcleo húmedo, día/noche/servicio)

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:nucleo-humedo-vertical] NucleoHumedoVerticalValidator

`docs/fuentes/niveles_plantas.md`: cualquier estancia húmeda debe solapar en
(x,y) con ALGUNA húmeda de la planta inmediatamente inferior --
cualquier tipo húmedo coincide, no específico por tipo. A diferencia
de la escalera (near-alineación exacta), aquí basta con solape real
(intersección de área > 0): las bajantes necesitan discurrir por la
zona húmeda, no que las piezas coincidan pieza a pieza.

## [ARCH:nucleo-humedo-distancia] Distancia graduada de núcleo húmedo según número de piezas

A petición del usuario, continuando el diagnóstico sistemático por
aislamiento de variables: con 2 estancias húmedas simultáneas
(cocina+baño), 12/15 semillas convergían (80%); con 3 (el caso real
de programa mínimo: cocina+baño+lavadero), solo 1-3/15 (7-20%).
Causa: `NucleoHumedoValidator` exigía que TODAS las parejas de
húmedas quedaran a distancia ≤1 -- con 3 piezas, eso obliga a las
tres a tocarse mutuamente entre sí (configuración tipo "molinillo"),
mucho más restrictiva geométricamente que un simple contacto entre
dos.

- **Investigado contra la fuente normativa real** (CTE DB-HS 5,
  evacuación de aguas) antes de tocar nada: da distancias MÉTRICAS de
  tubería dentro de un mismo cuarto húmedo (p.ej. 60cm válvula-sifón),
  nunca una distancia entre estancias distintas, y en ningún sitio un
  umbral que varíe según el número de piezas húmedas. Sin fuente que
  respalde ningún valor concreto.
- **Relajado a distancia 2 a partir de 3+ húmedas** -- criterio de
  ingeniería confirmado EXPLÍCITAMENTE (mismo tipo de decisión que
  `AnchoLibrePractico`/`ProporcionMaxima`, no normativo), tras el
  diagnóstico empírico de arriba. Con 2 húmedas, sigue exigiendo
  distancia 1 sin cambios.
- **`GroupingConstraintValidator` (mecanismo genérico, compartido con
  zonificación día/noche/servicio) ampliado**: `max_distance` acepta
  ahora un entero fijo (comportamiento anterior, sin cambios para
  zonificación) O una función del número de miembros del grupo --
  cambio retrocompatible, verificado con test dedicado.
- **3 tests existentes corregidos**: dependían, sin saberlo, del
  comportamiento antiguo (distancia 1 fija) -- uno de ellos probaba
  exactamente el caso que ahora es válido por diseño (3 húmedas en
  cadena, distancia 2 entre los extremos). Corregidos para reflejar
  la nueva lógica graduada, más un test nuevo confirmando que 3+
  húmedas siguen fallando más allá de distancia 2.
- **Impacto confirmado empíricamente**: en el escenario de programa
  mínimo, núcleo húmedo desapareció POR COMPLETO de los motivos de
  fallo tras este cambio -- las violaciones restantes son ya solo de
  desviación de área en una estancia aislada (el problema de
  compensación acumulada en árboles profundos, ya documentado en
  [ARCH:area-objetivo], distinto y ya identificado).
- Suite final: 377 unitarios, pyflakes y mypy limpios.

## [ARCH:day-night-zoning] day_night_zoning_validator.py

Zonificación día/noche: estancias de una misma zona deben quedar
agrupadas, sin necesitar compartir pared (a diferencia de núcleo
húmedo). Umbral según `nhv.lua` (evaluarZonificacionDiaNoche): 2 para
ambas zonas.

Bug real corregido: CORRIDOR y ENTRANCE_HALL son SpaceCategory.
CIRCULACION pero tienen zone=DAY por defecto -- sin excluirlos, un
pasillo junto a los dormitorios generaba una violación falsa de
zonificación día, aunque cumpliera perfectamente su función de
circulación hacia zona noche.

Zonificación de servicio: NO existe en `nhv.lua` (solo cubre día/
noche) -- extensión propia de este proyecto, marcada como tal.

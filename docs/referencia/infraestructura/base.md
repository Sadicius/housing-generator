# Infraestructura base (composition root, enums, geometría, entidades)

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:container] config/container.py -- composition root

`build_per_floor_validators`: `ViviendaMinimaValidator` y
`BanoAccesoGeneralValidator` quedan fuera deliberadamente -- son de
ámbito EDIFICIO, no de planta, se comprueban aparte en
`GenerateBuildingUseCase`. `total_num_estancias`/`global_rank`: del
edificio completo, no solo de esta planta (dos bugs reales corregidos
en el primer edificio de 2 plantas de prueba). `vivienda_accesible`:
opt-in, por defecto False.

`build_generate_building_use_case`: si la vivienda tiene más de una
planta, el requisito de vivienda accesible se aplica en todas las
plantas por igual (la fuente Lua original distinguía "duplex" como
caso aparte, aquí no).

## [ARCH:enums] domain/enums.py -- decisiones de clasificación

**`ZoneType.CIRCULATION`**: distinta de DAY/NIGHT/SERVICE -- no es una
macro-zona de uso, es la clasificación honesta para estancias que
sirven a varias zonas a la vez (CORRIDOR, ENTRANCE_HALL, STAIRCASE).
Forzarlas a DAY por defecto generaba violaciones falsas de
zonificación cuando un pasillo servía correctamente a la zona noche
(bug real encontrado en auditoría).

**`AdjacencyStrength`**: SHOULD_BE_NEAR/SHOULD_BE_AWAY usan una
métrica distinta (saltos en el grafo, cerca ≤2/alejar ≥3) que
MUST_BE_NEAR/MUST_BE_AWAY (contacto geométrico directo, ancho de
puerta 1.0m) -- decisión deliberada de no unificar métricas para no
perder esa precisión. Ver `SoftConstraintScorer`.

**`DEFAULT_WET_ROOMS`**: confirmado por normativa (CTE DB-HS) y
práctica de fontanería (cada local húmedo con su propia llave de
corte). `tendedero` queda fuera -- normalmente prolongación del
lavadero sin desagüe propio.

**`SpaceCategory`**: Tabla 1 (ESTANCIA) vs Tabla 2 (SERVICIO) vs
CIRCULACION (reglas de anchura, no superficie). Cocina es "pieza
vividera" pero NO "estancia" a efectos de Tabla 1 -- dos
clasificaciones normativas distintas, confirmado contra el decreto.

**`DEFAULT_MIN_EXTERIOR_SIDES`**: confirmado caso por caso con el
usuario, no derivado automáticamente. `GARAGE=0` -- corregido tras
investigación (antes era 1): sin respaldo normativo real (B.2.6 es de
garajes colectivos, no unifamiliares; ni siquiera `nhv.lua` lo exigía).
Ancho de exterior es asunto de urbanismo (A.2.1), no de habitabilidad
por estancia. Override disponible por proyecto si hace falta.

**`DISPLAY_NAMES`**: debe coincidir EXACTAMENTE con el mapeo `DISPLAY`
del dashboard (`docs/visualizador/js/00-shared.js`) -- si uno cambia,
cambiar el otro. Bug real encontrado en su momento: el nombre técnico
del tipo se usaba como `Room.name`, visible en el plano final.

## [ARCH:shapely-utils] geometry/shapely_utils.py

`count_exterior_sides`: umbral de contacto exterior (0.3m) distinto y
mayor que el de adyacencia interior (0.1m), confirmado con el usuario.
`excluded_segments` excluye lados de medianera (vivienda pareada/
adosada) -- una pared de medianera no tiene luz ni ventilación propia
aunque geométricamente sea un borde de parcela.

`evaluate_minimum_width`: helper compartido, extraído tras encontrar
duplicación real (detección sistemática de bloques repetidos): tres
validadores distintos (pasillo, escalera, trastero) repetían
exactamente el manejo de los 3 estados de `meets_minimum_width`, solo
cambiaba el umbral y el texto del mensaje.

## [ARCH:lot] domain/entities/lot.py

`retranqueo_m`: NO es un valor fijo de la normativa de habitabilidad
-- el propio Decreto 29/2010 remite esto a la legislación urbanística
(Ley 2/2016 do solo de Galicia + PXOM municipal), así que es un
parámetro que declara quien usa el proyecto, no una constante asumida.

`retranqueo_incremento_por_planta_m`: técnica de "subtractive
generation" (investigación externa confirmada, Devans "Procedural
Generation For Dummies: Building Footprints") -- encoge
progresivamente cada planta respecto a la de abajo, con red de
seguridad (`MinArea{Action:Shrink, Fallback:...}`): si el área
resultante no alcanza para las estancias declaradas, usa la misma
huella que la planta inferior en vez de encoger a un tamaño inválido.

`medianera_sides`: vivienda pareada/adosada (1-2 lados sin retranqueo
ni contacto exterior real -- una pared de medianera no tiene luz ni
ventilación propia). Requiere parcela rectangular ortogonal, misma
simplificación geométrica que el resto del proyecto.

## [ARCH:validation-result] ValidationResult -- el patrón de 3 estados

Separa dos cosas que una simple `List[str]` de violaciones no puede
expresar: `violations` (la restricción NO se cumple, con los datos
disponibles) y `warnings` (no se puede confirmar NI descartar el
cumplimiento -- "no verificable"). Nunca se trata como aprobado por
defecto, pero tampoco bloquea la generación como una violación real --
es una tercera categoría, no un término medio. Mismo patrón que
`nhv.lua` ya distinguía en varios sitios (`esEspacioExteriorDeCalidad`).
Usado consistentemente en todos los validadores geométricos del
proyecto.

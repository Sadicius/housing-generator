# Preferencia de nivel/planta por tipo de estancia

Catálogo de la planta preferente/obligatoria por cada `RoomType`,
construido tipo a tipo con el mismo método que
`relaciones_espaciales.md`. **No implementado en código todavía** — el
generador actual (`SimulatedAnnealingLayoutGenerator`) y las entidades
`Lot`/`Layout` asumen un único plano 2D; no existe generación
multi-planta real. Este documento es la base para cuando se aborde esa
extensión.

## Estructura del modelo

Cada tipo se describe como una secuencia de *(nivel, fuerza)*, en orden
de preferencia (el primero es el ideal; los siguientes son respaldo si
el primero no es viable):

**Niveles**: `SOTANO` (-2) · `SEMISOTANO` (-1) · `PLANTA_BAJA` (0) ·
`PLANTA_SUPERIOR` (1+, sin distinguir cuál) · `BAJO_CUBIERTA`

**Fuerza**: `Obligatorio` · `Preferente` · `Indiferente`

## Catálogo

| RoomType | Nivel(es) preferente(s), en orden | Fuerza | Notas |
|---|---|---|---|
| LIVING_ROOM | PLANTA_BAJA | Preferente | Espacio social principal |
| DINING_ROOM | PLANTA_BAJA | Preferente | Junto al salón |
| KITCHEN | PLANTA_BAJA | Preferente | Núcleo social de planta baja |
| BEDROOM | PLANTA_BAJA → PLANTA_SUPERIOR | Preferente | **Condicional a espacio**: planta baja si hay superficie suficiente, si no sube |
| MASTER_BEDROOM | PLANTA_BAJA → PLANTA_SUPERIOR | Preferente | Mismo condicional que BEDROOM |
| BATHROOM | PLANTA_BAJA → PLANTA_SUPERIOR | Preferente | Sigue a los dormitorios a los que sirve |
| TOILET | PLANTA_BAJA | Preferente | Fijo, sirve a zona social/visitas, no depende de dormitorios |
| ENTRANCE_HALL | PLANTA_BAJA | **Obligatorio** | Es la puerta de calle real |
| STUDY | PLANTA_BAJA → PLANTA_SUPERIOR | Preferente | Mismo condicional que BEDROOM (modelo de vida) |
| LAUNDRY | PLANTA_BAJA → SEMISOTANO → SOTANO | Preferente | Nunca en planta superior |
| DRYING_AREA | PLANTA_BAJA → SEMISOTANO (opcional) | Preferente | Condicionado también por la cocina; sin sótano (ventilación natural) |
| STORAGE | PLANTA_BAJA → PLANTA_SUPERIOR | Preferente | Acompaña a la estancia a la que sirve |
| STORAGE_ROOM | SOTANO / SEMISOTANO / PLANTA_SUPERIOR / BAJO_CUBIERTA | Preferente | Indiferente entre estos 4, nunca planta baja |
| GARAGE | SOTANO / SEMISOTANO / PLANTA_BAJA | **Obligatorio** | Indiferente entre estos 3, nunca planta superior/bajo cubierta |
| TECHNICAL_ROOM | SOTANO / SEMISOTANO / PLANTA_BAJA | **Obligatorio** | Mismo patrón que GARAGE |
| CORRIDOR | *(todas)* | — | Caso especial: no tiene planta propia, existe en cada planta que tenga la vivienda |

## Notas de diseño importantes

1. **Preferencias condicionadas a superficie disponible**: BEDROOM,
   MASTER_BEDROOM, STUDY y BATHROOM no tienen una planta fija — dependen
   de si la planta baja tiene espacio suficiente para todo el programa.
   Esto es distinto de una simple cadena de respaldo fija (como
   LAUNDRY) y requeriría, en la implementación real, evaluar la
   superficie total antes de fijar preferencia por planta.
2. **CORRIDOR no encaja en el modelo *(nivel, fuerza)***: un programa
   multi-planta necesitaría potencialmente una instancia de `CORRIDOR`
   por planta, no una única preferencia de nivel.
3. **`BAJO_CUBIERTA`** se añadió como nivel propio, distinto de
   `PLANTA_SUPERIOR`, a petición explícita — no se asumió como caso
   particular de planta superior.

## Relación vertical: continuidad de instalaciones (bajantes)

Extensión directa de `núcleo húmedo` (horizontal, ya implementado) al
eje vertical, para cuando exista generación multi-planta real:

**Regla**: el mismo conjunto de tipos que hoy cuenta como `is_wet`
(`KITCHEN`, `BATHROOM`, `TOILET`, `LAUNDRY` — ver `DEFAULT_WET_ROOMS`
en `enums.py`) debe, además de agruparse horizontalmente en su propia
planta (ya implementado), **alinearse verticalmente** con al menos una
estancia húmeda de la planta inmediatamente inferior — para que la
bajante de saneamiento sea una columna vertical continua, no un
recorrido en zigzag por la vivienda.

- **No hace falta que el tipo coincida** (un baño en planta superior
  puede caer sobre una cocina en planta baja, no necesariamente sobre
  otro baño) — vale con caer sobre CUALQUIER estancia húmeda de la
  planta de abajo.
- `DRYING_AREA` queda fuera (no es `is_wet`, mismo criterio que el
  núcleo húmedo horizontal).
- Mecanismo de medición análogo al horizontal: en vez de "distancia en
  el grafo de adyacencia de la misma planta", sería "solape en (x, y)
  entre la huella de la estancia húmeda de una planta y la de la planta
  inmediatamente inferior" -- requiere que ambas plantas compartan
  sistema de coordenadas (mismo `Lot` en planta, o una transformación
  conocida entre plantas).

**No implementado en código de generación.** Depende por completo de la
extensión de `Lot`/`Layout` a multi-planta ya señalada como pendiente
arriba; no hay generador que produzca varias plantas sobre las que
aplicar esta regla como restricción real.

**Sí explorable visualmente**: el "grafo de burbujas" del dashboard
(`docs/visualizador/relaciones_espaciales.html`) tiene una referencia
fantasma que muestra, al cambiar de planta, dónde quedaron las
estancias húmedas de la planta inmediatamente inferior, con una línea
de alineación verde/ámbar según lo cerca que quede la húmeda de la
planta actual — una forma manual e ilustrativa de razonar esta
continuidad mientras no exista la restricción real en el generador.

## Elemento pendiente: escalera (conexión entre plantas)

A diferencia de todos los `RoomType` existentes, la escalera **no vive
en una sola planta** — conecta dos plantas contiguas a la vez (un tramo
entre planta baja y planta superior, por ejemplo). Es un elemento
distinto incluso de `CORRIDOR` (que se multiplica por planta, pero cada
instancia vive en una sola).

**Dimensiones — CONFIRMADO por CTE DB-SUA 1** (investigación
independiente, no solo `nhv.lua`): una escalera privada interior de una
vivienda unifamiliar se clasifica como **"uso restringido"**, no "uso
general" -- el propio DB-SUA lo dice explícitamente: *"la escalera
interior de un alojamiento (dúplex, etc.) se puede considerar de uso
restringido... se considera que toda la vivienda es la unidad de
alojamiento, los usuarios son 'habituales', y por tanto la escalera es
de uso restringido cualquiera que sea el número de usuarios."* Esto
confirma la sospecha inicial: las cifras de `nhv.lua` (B.2.2, que
mencionaba "ascensor"/"edificio") eran para escalera de zonas comunes
de bloque, un caso distinto al nuestro.

| | Uso restringido (nuestro caso) | Uso general (edificio, NO aplica) |
|---|---|---|
| Ancho libre mínimo | **0.80 m** | 1.00–1.20 m (según evacuación) |
| Huella mínima | **22 cm** | 28 cm |
| Contrahuella máxima | **20 cm** | 13–18.5 cm |
| Fórmula 2C+H (60-64cm) | No exigida | Exigida |

Altura libre de paso: 2.20 m (cifra citada de forma consistente en
varias fuentes secundarias para ambos usos, no encontrada desglosada
por tipo de uso en el texto oficial revisado -- tratarla con algo más
de cautela que el resto de esta tabla).

**Pendiente de resolver** (antes de añadir `RoomType` real):
- La escalera necesita **alineación exacta de huella (x, y)** entre las
  dos plantas que conecta -- más estricto que la continuidad de
  bajantes húmedas (que solo exige solape parcial con cualquier
  húmeda): el hueco de escalera debe coincidir en la misma posición en
  ambas plantas, o el tramo no tiene sentido físico.
- Decidir cómo se referencia en el `Program`: ¿una única entidad que
  declara "conecta planta X con planta Y", o dos `Room` (uno por planta)
  con una relación de igualdad de huella entre ambos?
- Ancho de escalón (huella/contrahuella) requiere modelar geometría de
  peldaños, no solo un rectángulo en planta -- más detallado que
  cualquier otra pieza modelada hasta ahora.

**No implementado en código**, alcance decidido explícitamente: solo
documentación por ahora, igual que el resto de lo multi-planta.

## Auditoría de coherencia entre documentos (encontrado, sin resolver)

Al auditar `niveles_plantas.md` contra `relaciones_espaciales.md` y
`ExteriorContactValidator`, aparecen tres tensiones que no están
resueltas (no son errores de dato, son interacciones no formalizadas
entre reglas que hoy viven en documentos/validadores separados):

1. **GARAGE: sótano vs. contacto exterior**. `GARAGE` puede estar en
   `SOTANO` (esta tabla) pero también exige mínimo 1 lado de contacto
   exterior (`ExteriorContactValidator`, por acceso vehicular). Un
   garaje en sótano solo puede satisfacer ambas cosas a la vez con una
   rampa que corte el nivel de rasante -- un caso particular de
   "contacto exterior" más específico que una simple fachada, que
   `count_exterior_sides()` no distingue. No es una contradicción
   imposible, pero el modelo actual no representa la diferencia entre
   "fachada plana" y "rampa que baja a sótano".
2. **KITCHEN↔GARAGE "muy cerca" asume misma planta**. La relación
   `Preferencia (muy cerca, con barrera)` de `relaciones_espaciales.md`
   solo tiene sentido si ambas estancias acaban en la misma planta --
   pero nada en el modelo obliga a eso: `KITCHEN` prefiere
   `PLANTA_BAJA` fija, `GARAGE` es indiferente entre sótano/semisótano/
   planta baja. Si el generador (multi-planta, futuro) eligiera GARAGE
   en sótano por otros motivos, esta preferencia de adyacencia quedaría
   automáticamente inviable, sin que ningún validador lo señale como tal
   -- los dos documentos no están enlazados formalmente.
3. **BEDROOM/STUDY "alejar" de LIVING_ROOM se vuelve irrelevante entre
   plantas distintas**: la preferencia de separación horizontal
   (adyacencia) solo importa de verdad cuando ambas estancias comparten
   planta (condicional a espacio, ver arriba). No es una contradicción,
   solo una observación de diseño: cuando el dormitorio sube de planta,
   la separación ya la proporciona el propio nivel, y la preferencia de
   adyacencia horizontal pasa a ser irrelevante para ese caso.

Ninguna de las tres se resuelve aquí -- todas dependen de tener
generación multi-planta real, momento en el que habrá que decidir cómo
el generador consulta varios documentos/reglas a la vez (o formalizarlos
en una sola estructura de datos que los prevea desde el principio).

## Pendiente para cuando se aborde generación multi-planta real


- Extender `Lot` para representar múltiples plantas (¿un solar por
  planta con la misma huella, o huellas distintas por planta?).
- Extender `Layout` para agrupar resultados por planta.
- Decidir cómo el generador (recocido simulado u otro) coordina
  colocación entre plantas — incluyendo circulación vertical (escaleras,
  no modeladas todavía, nivel edificio B.2.2, fuera de alcance actual).
- Formalizar el condicional "según espacio disponible" en código (no es
  una simple constante por tipo, depende del programa completo).
- Decidir cómo `CORRIDOR` se multiplica por planta en el `Program`.
- Implementar la continuidad vertical de instalaciones (bajantes) una
  vez exista generación multi-planta -- ver sección anterior.
- Añadir `RoomType` de escalera con las dimensiones ya confirmadas
  (CTE DB-SUA 1, uso restringido) -- ver sección anterior. Pendiente:
  resolver la geometría de peldaños y la alineación exacta entre
  plantas antes de implementar.

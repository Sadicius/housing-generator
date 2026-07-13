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

**[RESUELTO, primer incremento multi-planta]** `NucleoHumedoVerticalValidator`,
conectado a `GenerateBuildingUseCase`. Comprueba solape en planta con
alguna húmeda de la planta inmediatamente inferior YA RESUELTA (pasada
como referencia fija a la búsqueda de la planta actual). Ver
`docs/architecture.md`, sección "Multi-planta: primer incremento real".

## Escalera (conexión entre plantas)

**[RESUELTO, primer incremento multi-planta]** `RoomType.STAIRCASE`
añadido al dominio + `EscaleraAlineacionValidator` (huella con >=90% de
solape entre plantas consecutivas, referencia fija a la planta inferior
ya resuelta) + `EscaleraAnchoLibreValidator` (0.80m, ancho libre uso
restringido). Ver `docs/architecture.md`, sección "Multi-planta: primer
incremento real".

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
| Ancho libre mínimo | **0.80 m** — implementado | 1.00–1.20 m (según evacuación) |
| Huella mínima | 22 cm — NO implementado | 28 cm |
| Contrahuella máxima | 20 cm — NO implementado | 13–18.5 cm |
| Fórmula 2C+H (60-64cm) | No exigida | Exigida |

Altura libre de paso: 2.20 m (cifra citada de forma consistente en
varias fuentes secundarias para ambos usos, no encontrada desglosada
por tipo de uso en el texto oficial revisado -- tratarla con algo más
de cautela que el resto de esta tabla). **NO implementado** (la
escalera es un `RoomType` con área/ancho declarados, como cualquier
otro -- no se modela como volumen 3D con altura de paso propia).

**Pendiente de resolver, sin implementar todavía**:
- Huella/contrahuella de peldaños: requiere modelar geometría de
  escalones, no solo un rectángulo en planta -- más detallado que
  cualquier otra pieza modelada hasta ahora.
- El sistema no comprueba que el número de peldaños sea físicamente
  coherente con la altura libre entre plantas (altura de planta a
  planta ÷ contrahuella máxima).

## Auditoría de coherencia entre documentos (encontrado, sin resolver)

**Actualizado tras implementar multi-planta real (ver `docs/architecture.md`,
secciones "Multi-planta: primer incremento real" y "Catálogo de 120
pares formalizado")**: las tres tensiones de abajo ya NO "dependen de
tener multi-planta" -- multi-planta existe. La 1 y la 3 siguen sin
resolver de verdad. La 2 está **verificada como neutralizada, aunque
de forma silenciosa**: `build_adjacency_requirements` (el catálogo
formalizado) no conoce `Room.level` en absoluto -- genera el requisito
KITCHEN↔GARAGE igual sin importar la planta de cada una. Pero
`GenerateBuildingUseCase.execute()` ya filtra por planta antes de
generar cada una (`level_adjacency = [req for req in ... if
req.room_a_id in level_room_ids and req.room_b_id in level_room_ids]`)
-- un requisito entre dos estancias de plantas distintas se descarta
automáticamente, nunca llega a aplicarse mal. Confirmado con una
comprobación directa, no solo argumentado. No está pulido (no hay
ningún aviso de que se descartó, simplemente desaparece), pero no es
peligroso como se temía originalmente.

Al auditar `niveles_plantas.md` contra `relaciones_espaciales.md` y
`ExteriorContactValidator`, aparecen tres tensiones que no están
resueltas (no son errores de dato, son interacciones no formalizadas
entre reglas que hoy viven en documentos/validadores separados):

1. **[RESUELTO] GARAGE: sótano vs. contacto exterior**. Investigado a
   fondo (Decreto 29/2010 + `nhv.lua` + discusión real de arquitectos en
   foro): la exigencia de contacto exterior de `GARAGE` nunca estuvo
   respaldada por normativa de habitabilidad para vivienda unifamiliar
   -- "garajes colectivos" (B.2.6) es de edificio con varios vecinos,
   confirmado explícitamente que NO aplica a unifamiliar ("no disponen
   de ninguno de ellos por tipología"), y `nhv.lua` declara
   explícitamente no modelar "garajes de viviendas unifamiliares". La
   tensión con `SOTANO` desaparece porque la premisa (GARAGE exige
   contacto exterior) era incorrecta, no porque se haya resuelto la
   geometría de la rampa. `DEFAULT_MIN_EXTERIOR_SIDES[GARAGE]` pasó de
   1 a 0 -- sigue siendo opcional por proyecto (`Room.min_exterior_sides`
   admite override explícito) para quien quiera exigirlo por motivos
   prácticos propios.
2. **KITCHEN↔GARAGE "muy cerca" asume misma planta** -- ver nota de
   arriba: verificado que el filtrado por planta de
   `GenerateBuildingUseCase` neutraliza el riesgo real, aunque de forma
   silenciosa (sin aviso de que el requisito se descartó).
3. **BEDROOM/STUDY "alejar" de LIVING_ROOM se vuelve irrelevante entre
   plantas distintas**: la preferencia de separación horizontal
   (adyacencia) solo importa de verdad cuando ambas estancias comparten
   planta (condicional a espacio, ver arriba). No es una contradicción,
   solo una observación de diseño: cuando el dormitorio sube de planta,
   la separación ya la proporciona el propio nivel, y la preferencia de
   adyacencia horizontal pasa a ser irrelevante para ese caso. **Mismo
   mecanismo de filtrado por planta que en el punto 2 -- neutralizado,
   no peligroso, aunque tampoco "resuelto" con intención (es un efecto
   colateral correcto, no una regla explícita para este caso).**

## Multi-planta real — RESUELTO, primer incremento

> Para saber qué queda pendiente de verdad ahora mismo, ver
> `docs/CONTINUIDAD.md` -- es la única fuente de verdad sobre eso. Esta
> sección era antes una lista de "pendiente cuando se aborde
> multi-planta"; se reescribe aquí como registro de qué se resolvió,
> porque casi todo lo que decía quedó obsoleto sin que se corrigiera a
> tiempo (mismo problema encontrado en `architecture.md` y
> `relaciones_espaciales.md` -- ver la convención en `CONTINUIDAD.md`).

Todo lo siguiente está **[RESUELTO]**, ver `docs/architecture.md`
sección "Multi-planta: primer incremento real" para el detalle:
- `Building` (nueva entidad) agrupa varias `Layout`, una por planta.
- `Room.level` (`NivelPlanta`) formaliza el nivel de cada estancia.
- `GenerateBuildingUseCase` coordina la generación planta a planta,
  encadenando referencias fijas entre plantas consecutivas.
- `RoomType.STAIRCASE` + `EscaleraAlineacionValidator` (huella
  alineada ≥90% entre plantas) + `EscaleraAnchoLibreValidator` (0.80m).
- Continuidad vertical de instalaciones (bajantes) →
  `NucleoHumedoVerticalValidator`.
- `CORRIDOR` se declara igual que cualquier otro tipo, con su propio
  `Room.level` -- no hay multiplicación automática, cada instancia por
  planta se declara explícitamente en el `Program`.
- **[RESUELTO]** Contorno edificable reducido progresivamente planta a
  planta (`Lot.retranqueo_incremento_por_planta_m`, opcional -- `None`
  por defecto preserva el comportamiento anterior de mismo contorno
  para todas). Ver `docs/architecture.md`, sección "Dos pendientes
  resueltos: catálogo automático conectado + contorno progresivo".

**Lo único que sigue sin implementar de verdad**: geometría de
peldaños (huella/contrahuella) -- la escalera es un `RoomType` con
área/ancho declarados, como cualquier otro, sin modelar volumen 3D ni
número de escalones.

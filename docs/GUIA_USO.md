# Guía de uso — housing_generator

> Documento de referencia sobre **cómo usar** el proyecto. Para entender
> cómo funciona por dentro, ver `docs/COMO_FUNCIONA.md`. Para el estado
> de pendientes y decisiones históricas, ver `docs/CONTINUIDAD.md` y
> `docs/architecture.md`.

## Instalación

```bash
cd housing_generator
pip install -e .
```

Dependencias: `shapely>=2.0`, `networkx>=3.0`, `scipy>=1.10`, `pytest` (desarrollo).

Comprobar que todo funciona:
```bash
pytest -q            # deberia dar 295 passed
python -m housing_generator.interface.cli.main --output /tmp/prueba.json
```

## Uso rápido: el CLI

El CLI genera una vivienda de ejemplo (11 estancias) y guarda el resultado en JSON.

```bash
python -m housing_generator.interface.cli.main --output layout.json
```

### Opciones

| Flag | Por defecto | Qué hace |
|---|---|---|
| `--output` | `layout.json` | Ruta del JSON de salida |
| `--seed` | `1` | Semilla del recocido simulado. Misma semilla → mismo resultado siempre (determinista). Cambiarla explora variantes distintas |
| `--max-iterations` | `3000` | Iteraciones del recocido simulado. Más iteraciones = más tiempo, más probabilidad de converger en casos difíciles |
| `--auto-adjacency` | desactivado | Deriva las relaciones de adyacencia automáticamente del catálogo de 120 pares en vez de la declaración manual del ejemplo (ver más abajo) |
| `--vivienda-accesible` | desactivado | Exige círculo de giro Ø1.50m en estancias habitables + baño, y pasillo ≥1.20m (DB-SUA + Base 5.4 Galicia) — ver más abajo |

```bash
# variante con mas busqueda y catalogo completo (busqueda mas dificil, ver mas abajo)
python -m housing_generator.interface.cli.main --output layout.json --auto-adjacency --max-iterations 5000 --seed 10
```

### Salida por consola

```
Layout generado y guardado en layout.json

  - Estar                  zona=day      bounds=(3.9, 3.1, 14.0, 6.6)
  - Comedor                zona=day      bounds=(...)
  ...
```

### Formato del JSON de salida

```json
{
  "rooms": [
    {"id": "living", "name": "Estar", "type": "living_room", "zone": "day", "area_m2": 25, "bounds": [x0, y0, x1, y1]},
    ...
  ],
  "doors": [
    {"room_a": "living", "room_b": "dining"},
    ...
  ],
  "metadata": {
    "hard_violations": 0,
    "soft_penalty": 0.0,
    "warnings": 11
  }
}
```

- `bounds`: `[x_min, y_min, x_max, y_max]` del rectángulo de la estancia, en metros.
- `doors`: pares de estancias con adyacencia `Obligatorio cerca` satisfecha geométricamente (≥1.0m de pared compartida) — una capa dispersa sobre el grafo de adyacencia real, no un modelo completo de puertas (posición exacta, ancho, sentido de apertura).
- `metadata.hard_violations`: siempre 0 si el CLI terminó sin error (si hubiera alguna, se lanza `LayoutGenerationError` antes de llegar a guardar nada).
- `metadata.soft_penalty`: preferencias de diseño no satisfechas (0 = todas satisfechas).
- `metadata.warnings`: avisos que no bloquean la generación (formas no rectangulares que no se pudieron verificar del todo, alturas no declaradas, etc.) — **conviene revisarlos siempre**, no son errores pero señalan huecos de verificación.

## Uso como librería Python

### Construir una vivienda de una planta, a mano

```python
from shapely.geometry import box
from housing_generator.config.container import build_generate_layout_use_case
from housing_generator.application.dto.generation_request import GenerationRequest
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import RoomType, AdjacencyStrength

rooms = [
    Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=25)),
    Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=10)),
    Room(id="entrance", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=4)),
    Room(id="bed1", name="Dormitorio", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
    Room(id="bath", name="Baño", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)),
    Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=3)),
    Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=2)),
    Room(id="storage", name="Almacén", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=3)),
]
adjacency = [
    AdjacencyRequirement("living", "entrance", AdjacencyStrength.MUST_BE_NEAR),
    AdjacencyRequirement("bath", "entrance", AdjacencyStrength.MUST_BE_NEAR),
]
program = Program(rooms=rooms, adjacency_requirements=adjacency)
lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 14)))

use_case = build_generate_layout_use_case(adjacency_requirements=adjacency, seed=1, max_iterations=3000)
layout = use_case.execute(GenerationRequest(program=program, lot=lot))

for room in layout.rooms:
    print(room.id, room.boundary.polygon.bounds)
```

Nota sobre el **programa mínimo**: toda vivienda debe declarar al menos
salón (`LIVING_ROOM`), cocina, baño, lavadero, tendedero y
almacenamiento (Decreto 29/2010, I.A.2.3) — si falta alguno, la
generación falla con `LayoutGenerationError` señalando cuál.

### Derivar las relaciones de adyacencia automáticamente (catálogo formalizado)

En vez de declarar `AdjacencyRequirement` a mano, se pueden derivar
automáticamente de un catálogo de 120 pares por tipo de estancia:

```python
from housing_generator.domain.services.type_adjacency_catalog import build_program_with_auto_adjacency

program = build_program_with_auto_adjacency(rooms)  # mismo `rooms` de arriba
use_case = build_generate_layout_use_case(adjacency_requirements=program.adjacency_requirements, seed=1, max_iterations=5000)
layout = use_case.execute(GenerationRequest(program=program, lot=lot))
```

**Aviso real**: el catálogo completo genera bastantes más requisitos
que una declaración manual curada (típicamente 4-6 a mano, decenas con
el catálogo completo) — es una búsqueda notablemente más difícil.
Conviene usar más iteraciones (`max_iterations=5000` o más) y probar
más de una semilla si la primera no converge.

### Restricciones blandas (preferencias de diseño)

Además de `MUST_BE_NEAR`/`MUST_BE_AWAY` (obligatorias), existen
`SHOULD_BE_NEAR`/`SHOULD_BE_AWAY` (preferencias): el generador intenta
satisfacerlas, pero nunca a costa de una restricción obligatoria.

```python
AdjacencyRequirement("study", "living", AdjacencyStrength.SHOULD_BE_NEAR)
```

`layout.metadata["soft_penalty"]` indica cuántas preferencias quedaron
sin satisfacer (0 = todas).

### Vivienda de varias plantas

```python
from housing_generator.config.container import build_generate_building_use_case
from housing_generator.domain.enums import NivelPlanta

rooms = [
    # planta baja
    Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM,
         dimensions=Dimensions(area_m2=25), level=NivelPlanta.PLANTA_BAJA),
    Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN,
         dimensions=Dimensions(area_m2=10), level=NivelPlanta.PLANTA_BAJA),
    Room(id="entrance", name="Recibidor", room_type=RoomType.ENTRANCE_HALL,
         dimensions=Dimensions(area_m2=4), level=NivelPlanta.PLANTA_BAJA),
    Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY,
         dimensions=Dimensions(area_m2=3), level=NivelPlanta.PLANTA_BAJA),
    Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA,
         dimensions=Dimensions(area_m2=2), level=NivelPlanta.PLANTA_BAJA),
    Room(id="storage", name="Almacén", room_type=RoomType.STORAGE,
         dimensions=Dimensions(area_m2=3), level=NivelPlanta.PLANTA_BAJA),
    Room(id="stair_pb", name="Escalera", room_type=RoomType.STAIRCASE,
         dimensions=Dimensions(area_m2=4), level=NivelPlanta.PLANTA_BAJA),
    # planta superior
    Room(id="bed1", name="Dormitorio", room_type=RoomType.BEDROOM,
         dimensions=Dimensions(area_m2=12), level=NivelPlanta.PLANTA_SUPERIOR),
    Room(id="bath", name="Baño", room_type=RoomType.BATHROOM,
         dimensions=Dimensions(area_m2=5), level=NivelPlanta.PLANTA_SUPERIOR),
    Room(id="stair_ps", name="Escalera", room_type=RoomType.STAIRCASE,
         dimensions=Dimensions(area_m2=4), level=NivelPlanta.PLANTA_SUPERIOR),
]
program = Program(rooms=rooms, adjacency_requirements=[])
lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 16)))

use_case = build_generate_building_use_case(seed=1, max_iterations=3000)
building = use_case.execute(program, lot)

for level, layout in building.floors.items():
    print(level.value, [r.id for r in layout.rooms])
```

Cada `Room` necesita `level` (`NivelPlanta.SOTANO`, `SEMISOTANO`,
`PLANTA_BAJA`, `PLANTA_SUPERIOR`, `BAJO_CUBIERTA` — no hace falta usar
los 5, solo los que existan en la vivienda). `RoomType.STAIRCASE` marca
la escalera en cada planta que conecta con la de abajo/arriba; el
sistema alinea automáticamente su huella entre plantas (≥90% de
solape) y comprueba continuidad de instalaciones húmedas.

**Contorno reducido planta a planta** (opcional, por defecto todas las
plantas comparten el mismo contorno edificable):

```python
lot = Lot(
    boundary=Boundary(polygon=box(0, 0, 18, 18)),
    retranqueo_incremento_por_planta_m=1.5,  # cada planta hacia arriba, 1.5m menos por lado
)
```

### Vivienda aislada con retranqueo

```python
lot = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), retranqueo_m=3.0)
```

`retranqueo_m` es la separación mínima a los lindes de parcela — **no**
es un valor fijo de la normativa de habitabilidad (el propio decreto
remite esto al planeamiento urbanístico de cada ayuntamiento), así que
hay que declararlo según el caso real, no asumir un valor por defecto.

### Vivienda pareada/adosada (con medianera)

```python
lot = Lot(
    boundary=Boundary(polygon=box(0, 0, 8, 20)),
    retranqueo_m=3.0,
    medianera_sides=frozenset({"east", "west"}),  # adosada: dos medianeras
    # medianera_sides=frozenset({"east"})          # pareada: una sola
)
```

Los lados declarados en `medianera_sides` (`"north"|"south"|"east"|"west"`)
no llevan retranqueo (la edificación llega hasta el linde, compartido
con la parcela vecina) y no cuentan como contacto exterior real para
habitabilidad (una pared de medianera no tiene luz ni ventilación
propia). El resto de lados se comportan igual que en vivienda aislada.
Requiere parcela rectangular de lados ortogonales (norte=+y, sur=−y,
este=+x, oeste=−x), misma simplificación geométrica que el resto del
proyecto.

## Ver el resultado como un plano real

Pestaña "Visor de plano" de `docs/visualizador/relaciones_espaciales.html`
(el mismo dashboard de siempre, no un archivo aparte) — carga el JSON
que genera el CLI (`--output layout.json`, o los varios
`edificio_planta_*.json` de `--import-seleccion`) y dibuja la planta
real: rectángulos por estancia, color por zona
(día/noche/servicio/circulación), nombre y superficie de cada una, y
marcas de puerta en las paredes compartidas que de verdad tienen
`Obligatorio cerca` satisfecho geométricamente. Todo se procesa en el
propio navegador, ningún archivo se sube a ningún sitio.

Para un edificio de varias plantas, selecciona a la vez todos los
`edificio_planta_*.json` generados — el visor detecta la planta de cada
uno por su nombre de archivo y las muestra como pestañas.

## El dashboard interactivo

`docs/visualizador/relaciones_espaciales.html` — se abre directamente
en un navegador, sin instalar nada. Permite explorar:
- La matriz de 120 pares de relaciones espaciales entre tipos de estancia
- Qué tipos de estancia son habituales en cada planta
- Fichas descriptivas por tipo de estancia

La pestaña de sección vertical incluye un panel de **generación
automática**: indicando tipo de vivienda, número de dormitorios y
número de plantas, selecciona las estancias necesarias (programa
mínimo + dormitorios + baños según reglas fijas) y calcula el área
mínima EXACTA de cada una según Tabla 1/2 real -- los campos quedan
bloqueados a ese mínimo, con un checkbox para desbloquear si se quiere
declarar más superficie a propósito. Sigue existiendo la selección
manual, chip a chip, para quien prefiera partir de cero.

## Generar el plano directamente (sin terminal)

**Esta es la forma principal de trabajar.** El botón **"generar plano
ahora"**, junto a la selección de estancias, ejecuta el generador real
-- el mismo motor Python de siempre, corriendo dentro del propio
navegador (via Pyodide, Python compilado a WebAssembly) -- sin salir a
una terminal, sin exportar ni volver a cargar ningún archivo. Debajo
del botón se puede ajustar la parcela (ancho×fondo), la semilla, las
iteraciones, y activar vivienda accesible, todo en el mismo sitio.

Al pulsar, cambia automáticamente a la pestaña "Visor de plano" con el
resultado real. Si la primera semilla no converge, reintenta solas
(igual que `--retry-seeds` del CLI) e informa cuál funcionó. Si quieres
otra variante, basta con cambiar la semilla y volver a pulsar -- sin
repetir la selección de estancias.

La primera vez que se pulsa, Pyodide descarga el intérprete de Python
y los paquetes necesarios (shapely, numpy, scipy, networkx) -- tarda
unos segundos, con el progreso visible en pantalla. Las veces
siguientes es inmediato, ya está todo cargado en la pestaña.

**Mantenimiento**: el código Python que corre en el navegador es una
copia embebida (`PY_BUNDLE` en el propio HTML) -- tras editar cualquier
`.py` del generador, hay que regenerarla con:
```bash
python scripts/regenerar_bundle_pyodide.py
```
Un test (`test_pyodide_bundle_is_not_stale_against_the_real_source`)
detecta si esto se olvida para `bridge.py`, pero conviene regenerar
tras CUALQUIER cambio, no solo ese archivo.

## Exportar JSON y usar el CLI (alternativa, para quien lo prefiera)

Exporta `seleccion_plantas.json` (tipos, cantidades, áreas y tipo de
vivienda por planta) — importable directamente:

```python
from housing_generator.infrastructure.persistence.seleccion_plantas_importer import import_seleccion_plantas
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.boundary import Boundary
from shapely.geometry import box

seleccion = import_seleccion_plantas("seleccion_plantas.json")
program = seleccion.program
lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 16)), medianera_sides=seleccion.medianera_sides)
```

`seleccion.medianera_sides` viene resuelto del `tipo_vivienda` elegido
en el panel automático (aislada → sin medianera; pareada → 1 lado;
adosada → 2 lados opuestos) — listo para pasárselo directamente a
`Lot`, sin tener que traducirlo a mano.

O desde el CLI, donde esta traducción ya ocurre automáticamente:
```bash
python -m housing_generator.interface.cli.main --import-seleccion seleccion_plantas.json --output edificio.json
```

Por defecto usa una parcela de ejemplo (14x16m) — `--lot-size ANCHOxFONDO`
(p.ej. `--lot-size 12x18`) permite ajustarla a una parcela real. Si la
primera semilla no converge, el CLI reintenta solas hasta 5 semillas
consecutivas antes de rendirse (`--retry-seeds`, ver más abajo).

## Estructura del dashboard (10 archivos, no 1)

`docs/visualizador/` tiene: `relaciones_espaciales.html` (estructura),
`.css` (estilos), `py_bundle.js` (código Python embebido para
Pyodide), y `js/` con 8 archivos, uno por pestaña/concepto
(`00-shared.js` con los datos y utilidades comunes, `01-matriz.js`...
`07-init.js`, que arranca todo al final). Separados a petición del
usuario -- **sigue abriéndose igual, con doble clic sobre el
`.html`, sin servidor**: todos se cargan con `<link>`/`<script
src="">` clásicos, en el orden correcto (`00-shared` primero,
`07-init` al final), que sí funcionan desde `file://` (a diferencia de
`fetch()` o los módulos ES, que sí necesitarían un servidor -- se
comprobó esto explícitamente antes de separar, no se asumió). Si
mueves el `.html`, mueve `.css`, `py_bundle.js` y la carpeta `js/`
enteros con él.

## Cronograma de obra (pestaña 06)

Herramienta de visualización pura, no de estimación: introduces las
fases de ejecución (nombre, categoría, duración en días) y una fecha
de inicio de obra -- cada fase se encadena a la siguiente (empieza
donde termina la anterior) y se dibuja como diagrama de Gantt. No hay,
que hayamos podido confirmar, una fuente pública con rendimientos
reales por fase para vivienda unifamiliar en Galicia, así que esta
pestaña nunca sugiere duraciones por su cuenta -- las declaras tú, con
tu propio criterio o el de la constructora. Reordenar fases (↑/↓) o
eliminarlas recalcula el cronograma completo al momento.

## Modo espejo (Visor de plano)

Si el plano generado es funcionalmente bueno pero la orientación no
conviene (p.ej. la zona de día queda mirando al lado equivocado para
el sol), el Visor de plano tiene botones de espejo horizontal,
espejo vertical y rotar 90° -- transforman el dibujo sin volver a
generar nada, conservando exactamente las relaciones de adyacencia
(las puertas se recalculan solas). "Restablecer" vuelve al plano
original en cualquier momento.

## Vivienda accesible (opcional)

`--vivienda-accesible` exige círculo de giro Ø1.50m inscribible en
salón, comedor, dormitorios, cocina y baño, y pasillo ≥1.20m (más
exigente que el mínimo general de 1.00m) — DB-SUA (Anejo A) + Base 5.4
del Código de Accesibilidad de Galicia. **Desactivado por defecto**:
la gran mayoría de viviendas no están obligadas a esto (DB-SUA 9.1:
"las condiciones de accesibilidad únicamente son exigibles en aquellas
[viviendas] que deban ser accesibles").

Retomado de un módulo Lua de un proyecto anterior del usuario
(`accesibilidad.lua`), que investigaba esto con más detalle
(mobiliario: altura de encimera, aproximación lateral a la cama, hueco
bajo fregadero, barras de apoyo del aseo...). Aquí solo se modela lo
**geométricamente verificable** con nuestras estancias (rectángulos con
área, sin mobiliario) — el resto exigiría modelar fixtures como piezas
propias dentro de cada estancia, fuera del alcance actual.

```bash
python -m housing_generator.interface.cli.main --output layout.json --vivienda-accesible --max-iterations 5000
```

**[RESUELTO]** Las dos limitaciones originales del formato exportado (una
sola estancia por tipo/planta, áreas genéricas) se eliminaron en el
propio dashboard: cada chip seleccionado ahora muestra un campo de
**cantidad** (para declarar, por ejemplo, dos dormitorios en la misma
planta) y un campo de **área en m²** (con un valor de partida sensato
que se puede ajustar). El importador usa esos valores reales
directamente. Compatibilidad conservada con JSON exportados antes de
este cambio (formato antiguo: una estancia por tipo, área genérica).
Si la selección no incluye `CORRIDOR`/`ENTRANCE_HALL` en una planta con
baño, la generación sigue fallando con un mensaje claro (no genera algo
incorrecto en silencio) — añadir la circulación que falte y reintentar.

## Errores más comunes

**`LayoutGenerationError: No se pudo generar un layout valido... programa minimo incompleto`**
→ Falta alguna de las 6 piezas obligatorias (salón, cocina, baño,
lavadero, tendedero, almacenamiento). Añadir la que falte.

**`LayoutGenerationError: ...ultimas violaciones: [...]`** (con
violaciones de superficie/ancho/etc.)
→ Alguna estancia no cumple un mínimo normativo. Revisar el mensaje
concreto — suele indicar el valor real y el mínimo exigido.

**`LayoutGenerationError` sin violaciones claras, o que aparece solo
a veces con la misma configuración**
→ Probablemente dificultad de búsqueda, no un problema de datos —
aumentar `max_iterations` o probar otra `seed`. Esto es especialmente
común con `--auto-adjacency` (ver aviso más arriba) o con parcelas muy
ajustadas de tamaño. Con `--import-seleccion` esto ya se maneja solo
(`--retry-seeds`, 5 intentos por defecto, informa qué semilla funcionó)
-- confirmado con un caso real donde la semilla 1 no convergía y la 4
sí, sin que hiciera falta buscarla a mano.

**Cambié algo del generador (movimientos, restricciones) y una
semilla que antes funcionaba ya no converge**
→ Comportamiento esperado, no un bug: cambiar qué restricciones o
movimientos usa el recocido simulado cambia la secuencia de números
aleatorios consumida en cada punto, así que la misma semilla puede
llevar a un resultado distinto. Buscar una semilla nueva que funcione
para el caso de prueba en cuestión.

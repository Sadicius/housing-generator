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

## El dashboard interactivo

`docs/visualizador/relaciones_espaciales.html` — se abre directamente
en un navegador, sin instalar nada. Permite explorar:
- La matriz de 120 pares de relaciones espaciales entre tipos de estancia
- Qué tipos de estancia son habituales en cada planta
- Fichas descriptivas por tipo de estancia

Es una herramienta de exploración del catálogo, no está conectada al
generador Python — para usar las mismas relaciones en una generación
real, usar `build_program_with_auto_adjacency` (ver arriba).

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
ajustadas de tamaño.

**Cambié algo del generador (movimientos, restricciones) y una
semilla que antes funcionaba ya no converge**
→ Comportamiento esperado, no un bug: cambiar qué restricciones o
movimientos usa el recocido simulado cambia la secuencia de números
aleatorios consumida en cada punto, así que la misma semilla puede
llevar a un resultado distinto. Buscar una semilla nueva que funcione
para el caso de prueba en cuestión.

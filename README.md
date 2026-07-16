# Housing Generator

Generador de plantas de vivienda unifamiliar. 
A partir de un programa de estancias y una parcela -- real,
importada desde el **Catastro** (GML), o declarada a mano -- genera la
distribución mediante un **árbol B*** (Chang & Chang 2000) optimizado por
recocido simulado, y comprueba automáticamente más de 20 reglas normativas:
superficies mínimas, anchos libres, adyacencias obligatorias, núcleo húmedo,
zonificación día/noche/servicio, edificabilidad, ocupación y accesibilidad,
entre otras. Construido con **arquitectura hexagonal (ports & adapters)**
para poder intercambiar piezas (algoritmo de generación, validadores, origen
de la parcela) sin tocar la lógica de dominio.

## Empezar aquí

Abre **[`INICIO.html`](INICIO.html)** con doble clic -- es el punto de
entrada del proyecto, con acceso al dashboard interactivo (generación real
en el propio navegador, sin instalar nada) y a toda la documentación.

El dashboard (`html/relaciones_espaciales.html`) es la forma
principal de usar el proyecto: interfaz completa con generación real vía
Pyodide (Python compilado a WebAssembly, corriendo en el navegador), sin
necesitar Python instalado localmente ni servidor. El CLI de abajo es útil
para automatización o desarrollo, no hace falta para uso normal.

## Instalación (solo para desarrollo o uso por CLI)

Automática (recomendado): ejecuta **`instalar.sh`** (Mac/Linux) o
**`instalar.bat`** (Windows, doble clic) desde la raíz del proyecto --
crea el entorno virtual e instala todo. Es idempotente, puedes
ejecutarlo de nuevo sin problema si algo cambia.

Manual, si prefieres hacerlo tú mismo:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Uso rápido (CLI de demostración)

```bash
python -m housing_generator.interface.cli.main --output layout.json
```

Esto construye un programa de ejemplo (6 estancias: estar, cocina, baño,
lavadero, tendedero, almacén), genera un layout con el árbol B* --
recocido simulado sobre una representación de empaquetado, no de
particionado de rectángulo -- respetando núcleo húmedo, zonificación
día/noche/servicio, Tabla 1 y Tabla 2 a la vez, y lo guarda en `layout.json`.

El CLI también admite, entre otras opciones (`--help` para el listado
completo): `--import-seleccion` (importar la exportación real del
dashboard y construir un `Program`/`Lot` real, con reintento automático
de semillas), `--retranqueo`/`--retranqueo-incremento` (separación a
lindero, vivienda aislada), `--edificabilidad`/`--ocupacion-maxima`/
`--altura-maxima-plantas`/`--frente-minimo` (comprobación de viabilidad
urbanística contra la ficha real del solar) y `--vivienda-accesible`
(círculo de giro Ø1.50m + pasillo ≥1.20m, DB-SUA + Base 5.4 Galicia,
opt-in).

## Tests

```bash
pytest -v
```

## Estructura del proyecto

```
src/housing_generator/
├── domain/            # Entidades y value objects puros (sin dependencias externas)
│   ├── entities/       # Room, Zone, Lot, Program, Layout, Building
│   ├── value_objects/  # Dimensions, Boundary, AdjacencyRequirement
│   ├── services/        # type_adjacency_catalog (catálogo de 120 pares)
│   ├── enums.py        # RoomType, NivelPlanta, tablas de valores por defecto
│   └── exceptions.py
├── application/        # Casos de uso + puertos (interfaces)
│   ├── ports/           # LayoutGeneratorPort, ZoningStrategyPort, ConstraintValidatorPort...
│   ├── use_cases/        # GenerateLayoutUseCase, GenerateBuildingUseCase, ValidateLayoutUseCase...
│   └── dto/
├── infrastructure/      # Implementaciones concretas de los puertos
│   ├── algorithms/
│   │   ├── zoning/             # TreemapZoningStrategy
│   │   ├── layout_generation/  # BTreeLayoutGenerator (árbol B*), SoftConstraintScorer
│   │   ├── adjacency/          # GeometryAdjacencyGraphBuilder, door_graph
│   │   └── constraints/        # 20+ validadores normativos/prácticos + 1 combinador
│   ├── geometry/         # Utilidades shapely compartidas
│   └── persistence/      # JsonLayoutRepository, seleccion_plantas_importer, catastro_gml_importer
├── interface/
│   ├── cli/              # Punto de entrada de línea de comandos
│   └── browser/          # Puente Pyodide para el dashboard (bridge.py)
└── config/
    └── container.py      # Composition root: aquí se conecta todo

tests/
├── unit/          # Dominio y algoritmos aislados
└── integration/   # Caso de uso completo (composition root real)

docs/                                # Ver docs/README.md como índice completo
├── GUIA_USO.md                       # Cómo usar cada zona del dashboard, el CLI y la instalación
├── COMO_FUNCIONA.md                  # Arquitectura interna de un vistazo
├── CONTINUIDAD.md                    # Pendientes reales y decisiones, para retomar el proyecto
├── historico/architecture.md         # Registro cronológico, append-only, de cada decisión
├── referencia/                       # Referencia técnica consolidada por tema
└── fuentes/relaciones_espaciales.md  # Catálogo de 120 relaciones entre tipos de estancia

html/relaciones_espaciales.html  # Dashboard interactivo (3 zonas: Diseño, Consulta, Planificación)
INICIO.html                      # Punto de entrada único del proyecto
examples/sample_program.json     # Programa de ejemplo en formato de datos
```

## Por qué esta arquitectura

- **Dominio aislado**: `domain/` no importa nada de `application/` ni
  `infrastructure/`. Las reglas de negocio (qué es una zona, cómo se calcula
  el área total, qué hace inválido un programa) se pueden testear sin
  levantar ningún algoritmo de generación.
- **Puertos como contratos**: `LayoutGeneratorPort`, `ZoningStrategyPort` y
  `ConstraintValidatorPort` son las piezas pensadas para sustituirse a medida
  que el proyecto evolucione (por ejemplo, pasar del árbol B* actual a un
  solver por restricciones o a un modelo de ML). El caso de uso
  `GenerateLayoutUseCase` no cambia cuando eso ocurra -- de hecho, el propio
  generador ya pasó por una migración así: el árbol de partición/guillotina
  original (`SimulatedAnnealingLayoutGenerator`) se sustituyó por completo
  por el árbol B* (`BTreeLayoutGenerator`) tras confirmar empíricamente que
  convergía mejor en todos los casos difíciles probados, sin tocar el caso
  de uso ni los validadores.
- **Composition root único**: `config/container.py` es el único módulo que
  conoce simultáneamente las abstracciones y las implementaciones concretas,
  evitando que ese acoplamiento se disperse por el resto del código.

## Pendiente real, si se retoma

Lista honesta, no exhaustiva -- el detalle completo con contexto y
decisiones vive en `docs/CONTINUIDAD.md`:

- **Sección vertical automática solo cubre 1-2 plantas** (planta baja/
  superior); sótano, semisótano y bajo cubierta no se generan
  automáticamente (sí son editables a mano en el dashboard).
- **Las puertas del visor son una marca genérica** (0.9m en la pared
  compartida), no una posición/ancho/sentido de apertura real.
- **`CocinaIntegradaValidator`** (cocina abierta al salón) no tiene forma
  de activarse ni explicarse todavía desde el dashboard.
- **Modo espejo no transforma la zona de vacío exterior** al reflejar o
  rotar el plano -- se omite en vez de dibujarse en el sitio equivocado.
- **`SolarExposureValidator`** (asoleamiento/orientación de fachada):
  aparcado deliberadamente, con una referencia externa concreta si se
  retoma (ver `docs/CONTINUIDAD.md`), no una extensión trivial del modelo
  actual de habitaciones.
- **Cytoscape.js para la pestaña "Sinergias"**: investigado, viable, pero
  pospuesto -- sustituiría la red SVG dibujada a mano por una red
  interactiva real; coste real de integración (canvas, no SVG, e
  inicialización con pestañas ocultas), no un simple añadido de librería.
- Un escenario de prueba concreto (parcela 12×10, 9 estancias con
  adyacencia obligatoria `DINING_ROOM`-`KITCHEN`) sigue sin converger con
  ninguno de los generadores probados hasta la fecha -- documentado como
  `xfail`, no oculto.

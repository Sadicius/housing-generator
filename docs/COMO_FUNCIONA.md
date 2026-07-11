# Cómo funciona — housing_generator

> Documento de referencia sobre el funcionamiento interno del sistema,
> tal como está **hoy**. Para instrucciones de uso, ver
> `docs/GUIA_USO.md`. Para el porqué de cada decisión y su historial,
> ver `docs/architecture.md` (log cronológico) — este documento no
> repite ese razonamiento, solo describe el resultado actual.

## Qué hace el sistema

Genera distribuciones de planta de vivienda unifamiliar que cumplen el
**Decreto 29/2010 de Galicia** (normas de habitabilidad, modificado por
Decreto 128/2023): a partir de una lista de estancias con su superficie
y un solar, produce la posición y forma de cada estancia dentro del
solar, verificando ~18 reglas normativas (superficies mínimas, anchos
libres, alturas, adyacencias obligatorias, programa mínimo...).

## Arquitectura: hexagonal / clean architecture

```
domain/           entidades y reglas puras, sin dependencias externas
  entities/        Room, Program, Lot, Layout, Building, Zone
  value_objects/    Dimensions, Boundary, AdjacencyRequirement
  services/         type_adjacency_catalog (catálogo de 120 pares)
  enums.py          RoomType, NivelPlanta, tablas de valores por defecto

application/       casos de uso, coordinan dominio + infraestructura via ports
  use_cases/        GenerateLayoutUseCase, GenerateBuildingUseCase
  ports/            interfaces (ConstraintValidatorPort, LayoutGeneratorPort...)
  dto/              GenerationRequest, ValidationResult

infrastructure/    implementaciones concretas de los ports
  algorithms/
    layout_generation/   SimulatedAnnealingLayoutGenerator, partition_tree
    constraints/          20 validadores normativos/practicos (1 opt-in)
    adjacency/             GeometryAdjacencyGraphBuilder, door_graph
    zoning/                TreemapZoningStrategy
  geometry/          shapely_utils (funciones geométricas compartidas)
  persistence/        JsonLayoutRepository

config/            container.py — ÚNICO sitio que conecta piezas concretas
interface/cli/      punto de entrada de línea de comandos
```

**Regla de dependencia**: `domain` no importa de nada más;
`application` no importa de `infrastructure` ni `config` (solo de
`domain` y de sus propios `ports`); `infrastructure` implementa esos
`ports`; `config/container.py` es el único lugar que conoce clases
concretas de todas las capas a la vez y las conecta.

## El algoritmo de generación

### Árbol de partición + recocido simulado

Cada estancia es una **hoja** de un árbol binario; cada nodo interno
representa un **corte** (horizontal o vertical) que reparte un
rectángulo entre sus dos subárboles, proporcionalmente al área total
de estancias de cada lado (`partition_tree.place_tree`).

1. Se construye un árbol inicial con topología aleatoria
   (`build_random_tree`) -- cada corte empieza en modo automático
   (`direction=None`).
2. En cada iteración, se genera un "vecino" mutando el árbol actual con
   uno de 4 movimientos aleatorios (`random_neighbor`):
   - `swap_leaves`: intercambia dos estancias de sitio
   - `flip_direction`: cicla la dirección de un corte por 3 estados
     (automático → horizontal forzado → vertical forzado → automático)
   - `swap_children`: espeja un subárbol
   - `slide_wall`: desliza un corte existente ±8% desde su proporción
     actual (técnica de Merrell et al. 2010)
3. Se acepta o rechaza el vecino según el criterio de Metropolis
   (`SimulatedAnnealingLayoutGenerator.generate`), con temperatura que
   decae en cada iteración (`cooling_rate`).

**Dirección automática = cortar por el lado más largo.** Un corte en
modo automático (`direction=None`, el punto de partida por defecto)
no decide horizontal/vertical al construir el árbol -- lo decide
`place_tree`, en el momento de colocar, según cuál sea el lado más
largo del rectángulo real en ese punto (técnica de squarified treemap,
Marson & Musse 2010). Reduce la aparición de estancias como tiras
finas frente a elegir la dirección al azar -- confirmado con un caso
real donde añadir un mínimo de ancho práctico volvió la búsqueda
mucho más difícil hasta aplicar esta técnica.

### Función objetivo: duro + blando, comparación lexicográfica

Cada layout candidato se puntúa como una tupla
`(violaciones_duras, penalización_blanda)`:
- **Duras** (`MUST_BE_NEAR`/`MUST_BE_AWAY` y las 18 reglas normativas):
  cuentan violaciones de `CompositeConstraintValidator`.
- **Blandas** (`SHOULD_BE_NEAR`/`SHOULD_BE_AWAY`): calculadas por
  `SoftConstraintScorer` vía distancia de saltos en el grafo de
  adyacencia real (cerca objetivo ≤2 saltos, alejar objetivo ≥3).

La aceptación compara **solo** el componente que cambió entre
candidato y actual: si lo duro cambia, la decisión se toma únicamente
por ese delta (a su escala natural); lo blando solo entra en juego
cuando lo duro empata. Esto preserva la dinámica de aceptación del
recocido — sumar ambos en un único número con un peso grande rompería
esa dinámica (ver `architecture.md` para el porqué).

### Multi-planta

`GenerateBuildingUseCase` NO hace una búsqueda conjunta de todas las
plantas: genera cada planta de abajo a arriba con el mismo generador de
una sola planta, encadenando referencias fijas de la planta ya resuelta
(huella de escalera, huellas de estancias húmedas) a la siguiente vía
validadores específicos:
- `EscaleraAlineacionValidator`: ≥90% de solape de huella entre plantas
  consecutivas.
- `NucleoHumedoVerticalValidator`: continuidad de bajantes (solape de
  área, no alineación exacta).

El contorno edificable puede reducirse progresivamente planta a planta
(`Lot.retranqueo_incremento_por_planta_m`, opcional): cada planta parte
del contorno de la de abajo, encogido un incremento — con una red de
seguridad que no encoge si el área resultante no alcanzaría para las
estancias declaradas (usa la misma huella que la planta inferior en
ese caso).

Tras generar todas las plantas, dos comprobaciones de ámbito EDIFICIO
(no por planta): `ViviendaMinimaValidator` (las 6 piezas del programa
mínimo, unión de todas las plantas) y `BanoAccesoGeneralValidator` (al
menos un baño con acceso general en **alguna** planta).

## Los 20 validadores normativos/prácticos (+ 1 combinador, 1 opt-in)

Implementan `ConstraintValidatorPort.validate(layout) -> ValidationResult`
(listas de `violations` y `warnings` — las violaciones bloquean la
generación, los avisos no). `CompositeConstraintValidator` no es una
regla normativa en sí -- agrupa una lista de validadores y expone la
misma interfaz, para que el generador solo necesite hablar con "un"
validador aunque por dentro sean 16 clases distintas (19 instancias
por planta, contando las 4 de `GroupingConstraintValidator`).

**Por planta** (`build_per_floor_validators` en `container.py`):

| Validador | Qué comprueba |
|---|---|
| `AdjacencyConstraintValidator` | `MUST_BE_NEAR`/`MUST_BE_AWAY` declarados |
| `GroupingConstraintValidator` ×4 | núcleo húmedo, zonificación día/noche/servicio (distancia de saltos) |
| `EstanciaMinimumAreaValidator` | Tabla 1: superficie mínima por puesto de tamaño + cuadrado inscribible del salón |
| `ServicioMinimumAreaValidator` | Tabla 2: superficie mínima por tipo de servicio |
| `DormitorioArmarioValidator` | hueco de armario empotrado por dormitorio |
| `TrasteroMinimumAreaValidator` | superficie fija de trastero (B.2.5) |
| `AnchoLibreEstanciaValidator` | ancho libre mínimo normativo (A.3.2.1) -- salón, dormitorios, cocina, baño |
| `AnchoLibrePracticoValidator` | ancho libre mínimo **NO normativo** (1.20m, decisión de ingeniería confirmada) para los tipos que el decreto deja sin ancho especificado -- evita estancias como tiras finas (p.ej. un almacén de 49cm de fondo, caso real encontrado) |
| `AnchoLibrePasilloValidator` | ancho libre de pasillo (A.3.2.3) |
| `AlturaLibreValidator` | altura libre mínima (A.3.1.1), con reducción directa a 2.20m en las piezas que el decreto nombra explícitamente |
| `ExteriorContactValidator` | lados de contacto exterior mínimos por tipo |
| `CocinaIntegradaValidator` | cocina abierta al salón: superficie combinada + apertura vertical |
| `EspacioAccesoValidator` | cuadrado inscribible de 1.50m en el vestíbulo |
| `EscaleraAnchoLibreValidator` | ancho libre de escalera (CTE DB-SUA 1, uso restringido) |
| `PasilloTopologiaValidator` | ninguna estancia (salvo salón/comedor) es paso obligado hacia otra |
| `ViviendaAccesibleValidator` | **opt-in** (`vivienda_accesible=True`), inactivo por defecto -- círculo de giro Ø1.50m + pasillo 1.20m (DB-SUA/Base 5.4, vivienda adaptada) |

**De ámbito edificio** (tras generar todas las plantas):
`ViviendaMinimaValidator`, `BanoAccesoGeneralValidator`.

**Entre plantas consecutivas**: `EscaleraAlineacionValidator`,
`NucleoHumedoVerticalValidator`.

## El catálogo de relaciones espaciales

`domain/services/type_adjacency_catalog.py`: 120 pares únicos entre los
16 `RoomType` no-circulación, clasificados en 5 categorías
(`docs/relaciones_espaciales.md` tiene el detalle completo con motivo
de cada relación). 82 de esas 120 tienen una entrada ejecutable en
`DEFAULT_TYPE_ADJACENCY`; las 38 restantes son "Neutro" (sin entrada,
ausencia = sin requisito) o se resuelven con lógica propia
(`BanoAccesoGeneralValidator` para el caso "Condicional", el propio
núcleo húmedo para "Ya cubierto").

`generate_adjacency_requirements(rooms)` deriva automáticamente los
`AdjacencyRequirement` (duros y blandos) de un conjunto de estancias
según sus tipos — aplicando la misma relación a cada instancia si hay
varias del mismo tipo, y sin generar nada entre dos estancias del mismo
tipo (el catálogo no tiene entradas tipo-tipo consigo mismo).

## Convenciones que sostienen la arquitectura

- **Toda la geometría es rectangular** (partición guillotina) — no hay
  formas en L, patios interiores, ni estancias no ortogonales.
- **Todos los valores normativos citan su origen** — Decreto 29/2010,
  artículo/apartado exacto, o "asunción documentada" cuando la fuente
  no lo especifica (nunca una cifra sin justificar).
- **Cada estancia sabe verificarse a sí misma con 3 estados**: cumple /
  no cumple (violación) / forma no rectangular, no verificable (aviso)
  — nunca se asume cumplimiento silenciosamente cuando no se puede
  comprobar.
- **Determinismo real**: misma `seed` → mismo resultado, siempre,
  incluso en llamadas repetidas a la misma instancia del generador.

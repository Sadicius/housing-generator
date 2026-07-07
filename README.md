# Housing Generator

Sistema generativo de plantas de vivienda con **zonificación día/noche/servicio**
y organización por adyacencias, construido con **arquitectura hexagonal
(ports & adapters)** para permitir intercambiar algoritmos de generación
(slicing simple, CSP, genético, ML) sin tocar la lógica de dominio.

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Uso rápido (CLI de demostración)

```bash
python -m housing_generator.interface.cli.main --output layout.json
```

Esto construye un programa de ejemplo (vivienda de 2 dormitorios + garaje),
genera un layout mediante recocido simulado sobre un árbol de partición
único (respetando núcleo húmedo, zonificación día/noche/servicio, Tabla 1
y Tabla 2 a la vez) y lo guarda en `layout.json`.

## Tests

```bash
pytest -v
```

## Estructura del proyecto

```
src/housing_generator/
├── domain/            # Entidades y value objects puros (sin dependencias externas)
│   ├── entities/       # Room, Zone, Lot, Program, Layout
│   ├── value_objects/  # Dimensions, Boundary, AdjacencyRequirement
│   ├── enums.py        # ZoneType, RoomType, AdjacencyStrength
│   └── exceptions.py
├── application/        # Casos de uso + puertos (interfaces)
│   ├── ports/           # Contratos que debe cumplir la infraestructura
│   ├── use_cases/        # GenerateLayoutUseCase, ValidateLayoutUseCase...
│   └── dto/
├── infrastructure/      # Implementaciones concretas de los puertos
│   ├── algorithms/
│   │   ├── zoning/            # TreemapZoningStrategy
│   │   ├── layout_generation/ # GraphBasedLayoutGenerator (slicing)
│   │   └── constraints/       # AdjacencyConstraintValidator
│   ├── geometry/         # Utilidades shapely compartidas
│   └── persistence/      # JsonLayoutRepository
├── interface/
│   └── cli/              # Punto de entrada de línea de comandos
└── config/
    └── container.py      # Composition root: aquí se conecta todo

tests/
├── unit/          # Dominio y algoritmos aislados
└── integration/   # Caso de uso completo (composition root real)

docs/architecture.md   # Decisiones de arquitectura y fundamentos de dominio
docs/relaciones_espaciales.md  # Catalogo de 120 relaciones entre tipos de estancia
docs/niveles_plantas.md  # Catalogo de preferencia de planta/nivel por tipo (no implementado)
docs/visualizador/relaciones_espaciales.html  # Dashboard interactivo (matriz, plantas, burbujas arrastrables, sinergias, fichas)
examples/sample_program.json  # Programa de ejemplo en formato de datos
```

## Por qué esta arquitectura

- **Dominio aislado**: `domain/` no importa nada de `application/` ni
  `infrastructure/`. Las reglas de negocio (qué es una zona, cómo se calcula
  el área total, qué hace inválido un programa) se pueden testear sin
  levantar ningún algoritmo de generación.
- **Puertos como contratos**: `LayoutGeneratorPort`, `ZoningStrategyPort` y
  `ConstraintValidatorPort` son las tres piezas que se van a querer sustituir
  a medida que el proyecto evolucione (por ejemplo, pasar de slicing simple
  a un solver por restricciones o a un modelo de ML). El caso de uso
  `GenerateLayoutUseCase` no cambia cuando eso ocurra.
- **Composition root único**: `config/container.py` es el único módulo que
  conoce simultáneamente las abstracciones y las implementaciones concretas,
  evitando que ese acoplamiento se disperse por el resto del código.

## Próximos pasos sugeridos

1. Sustituir `GraphBasedLayoutGenerator` (slicing) por un generador basado
   en resolución de restricciones (p. ej. `constraint` o `ortools`) que use
   el grafo de adyacencia (`BuildAdjacencyGraphUseCase`) como función de
   coste real, en vez de solo geometría proporcional.
2. Añadir un `ConstraintValidatorPort` adicional para luz natural /
   ventilación (orientación del solar vs. `requires_natural_light`).
3. Añadir un adaptador de entrada que lea `examples/sample_program.json`
   y construya un `Program` real (hoy el JSON es solo referencia de formato).
4. Considerar un generador evolutivo (`infrastructure/algorithms/layout_generation/genetic_generator.py`)
   que optimice una función de fitness combinando adyacencias cumplidas,
   compacidad y exposición solar.

# Documentación — housing_generator

Punto de entrada de toda la documentación del proyecto. Para abrir el
generador en sí, no esto, ve a [`../INICIO.html`](../INICIO.html).

## Para empezar a usar el proyecto

- **[guia-uso](GUIA_USO.md)** — cómo usar cada zona del dashboard, el
  CLI, y los scripts de instalación.
- **[como-funciona](COMO_FUNCIONA.md)** — arquitectura interna, de un
  vistazo: capas, puertos, dónde vive cada cosa.
- **[continuidad](CONTINUIDAD.md)** — pendientes reales, si se
  retoma el proyecto en otra sesión.

## Referencia técnica, por tema

`referencia/` — consolidada, organizada por tema (no cronológica).
Cada archivo agrupa varias piezas relacionadas, no una por archivo:

- `generador/` — el motor de generación (partición, huella
  construible, área objetivo, bloqueo progresivo). Incluye
  `prototipo-btree/` -- migración planificada a árbol B* (no
  guillotina), con las 5 fases documentadas, código de producción
  real (`--experimental-btree` en el CLI) y comparación empírica.
- `validadores/` — los 20+ validadores normativos, agrupados por qué
  exigencia comparten (superficies mínimas, anchos libres, geometría
  general, agrupación/zonificación, adyacencias, programa de
  vivienda, multi-planta).
- `infraestructura/` — piezas de soporte (composition root, enums,
  geometría, persistencia, arquitecturas alternativas).
- `dashboard/` — zonas y navegación, cronograma de obra, catálogo
  constructivo, exportar plano, lanzador e instalación.

**Buscar una decisión concreta**: cada decisión documentada lleva una
etiqueta `[ARCH:tag]` (p.ej. `[ARCH:area-objetivo]`), tanto en el
código fuente (`Ver [ARCH:tag]`) como en su sección de referencia
aquí. Para encontrarla, `grep -rn "ARCH:tag" docs/` desde la raíz del
proyecto -- no hace falta saber en qué archivo concreto vive, solo la
etiqueta.

## Histórico

- **[historico/architecture.md](historico/architecture.md)** —
  registro cronológico completo, sesión a sesión: por qué se tomó
  cada decisión, qué se investigó, qué se descartó y por qué. Es
  **solo-añadir** (append-only) -- nunca se reescribe una entrada
  pasada, aunque quede desactualizada; si algo cambia, se documenta
  como una entrada nueva. Para el estado *actual* de algo, mejor
  `referencia/` o `GUIA_USO.md`/`COMO_FUNCIONA.md`.

## Fuentes normativas

- **[fuentes/relaciones_espaciales.md](fuentes/relaciones_espaciales.md)**
  — catálogo de 120 pares de adyacencia entre tipos de estancia
  (fuente de `type_adjacency_catalog.py`).
- **[fuentes/niveles_plantas.md](fuentes/niveles_plantas.md)** —
  niveles de planta, escalera (CTE DB-SUA 1), núcleo húmedo vertical.

## Calidad

- **[calidad/fitness-functions.md](calidad/fitness-functions.md)** —
  comprobaciones automáticas y continuas (p.ej. detección de código
  muerto), no solo documentadas una vez.

---

*Reorganizado en carpetas temáticas a petición del usuario, inspirado
en cómo organizan su documentación otros proyectos reales (revisados
explícitamente: [ox_lib de Overextended](https://overextended.dev/docs/ox_lib),
[rsg-docs](https://github.com/Rexshack-RedM/rsg-docs)) -- ver
`[ARCH:reorganizacion-docs]` para el porqué completo.*

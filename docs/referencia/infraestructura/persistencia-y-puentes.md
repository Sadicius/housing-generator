# Infraestructura -- persistencia y puentes externos

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:seleccion-plantas-importer] persistence/seleccion_plantas_importer.py

Importa `seleccion_plantas.json` (exportación del dashboard) hacia un
`Program` real. Soporta formato nuevo (`version: 2`, cantidad + área
real por entrada) y antiguo (lista plana de nombres, sin cantidad ni
área -- retrocompatible con exportaciones previas al cambio).

`tipo_vivienda` se resuelve a `medianera_sides`: hallazgo real de una
auditoría de flujo completo -- el dashboard exportaba `tipo_vivienda`
desde hacía varias rondas, pero ningún sitio de Python lo leía (elegir
"adosada" no tenía ningún efecto real al generar). "pareada" usa un
lado (convención propia, "east" -- el dashboard no pregunta
orientación real); "adosada" usa dos lados opuestos (este/oeste).

`AREAS_POR_DEFECTO_M2`: solo se usa con el formato antiguo o si una
entrada nueva no trae área -- no derivadas de Tabla 1/2 (dependen del
número total de estancias, no se puede saber de antemano).

## [ARCH:browser-bridge] interface/browser/bridge.py

Puente entre el dashboard (JS, Pyodide) y el generador real -- solo
cruza datos planos (dict/JSON), nunca objetos de dominio (no cruzan
bien el FFI de Pyodide). Comparte toda la lógica de generación con el
CLI, solo difiere en dónde entra el dato (payload en memoria vs.
archivo) y dónde sale (dict vs. archivo). Reintenta semillas
automáticamente, mismo comportamiento que `--retry-seeds` del CLI.
Nunca lanza una excepción hacia JavaScript -- el error se devuelve
como dato.

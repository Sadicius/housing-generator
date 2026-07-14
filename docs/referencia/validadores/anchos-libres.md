# Validadores -- anchos libres

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## AnchoLibrePracticoValidator + heurística de "cortar por el lado más largo" [ARCH:ancho-libre-practico]

A partir de una captura de pantalla real del usuario (proporciones
extrañas en el plano: "Almacén" generado como 2.49m×0.49m, "Comedor"
como 3.69m×11.93m) -- normativamente conforme en área, pero
prácticamente inservible.

- **[RESUELTO] `AnchoLibrePracticoValidator`** (nuevo, 19º validador):
  ancho libre mínimo de **1.20m, explícitamente NO normativo**
  (confirmado con el usuario, no un valor del Decreto 29/2010) para los
  9 tipos que el decreto deja sin ancho libre especificado (comedor,
  despacho, aseo, lavadero, tendedero, almacenamiento, recibidor,
  garaje, cuarto técnico) -- confirmados sistemáticamente contra TODOS
  los validadores existentes, no solo `AnchoLibreEstanciaValidator`.
  `STORAGE_ROOM` (trastero) excluido, ya tiene su propio mínimo
  normativo (B.2.5, 1.60m).
- **Efecto secundario real y serio, no solo "cambia la semilla"**:
  añadir esta restricción hizo que un caso real (9 estancias, mismo
  programa del usuario) dejara de converger incluso con 30.000
  iteraciones y una parcela 6 veces más grande -- confirmado aislando
  la causa (quitando el validador, la misma semilla converge en 22s).
- **[RESUELTO] Investigación aplicada antes de bajar el umbral**:
  en vez de simplemente relajar 1.20m, se investigó la causa
  estructural -- Marson & Musse (2010, ya citados antes en este
  proyecto para el treemap de zonificación) describen cortar
  particiones por el lado MÁS LARGO del rectángulo (técnica de
  "squarified treemap") para que las estancias salgan con proporción
  cercana a 1:1, en vez de tiras finas. `PartitionNode.direction=None`
  ahora significa "automático, lado más largo, decidido en
  `place_tree` en el momento de colocar" (no se puede saber al
  construir el árbol, porque depende de la forma real del rectángulo
  en ese punto) -- valor explícito ("h"/"v") sigue forzando esa
  dirección, usado por `flip_direction` (ahora cicla 3 estados:
  automático→h→v→automático, no un toggle binario).
- **Resultado medido, no solo esperado**: el caso real que fallaba
  hasta con 30.000 iteraciones convergió en 5.000 (semilla 1 directa).
  Cambio de núcleo de generación → cambia dinámica de búsqueda otra
  vez (mismo patrón ya documentado varias veces) -- 8 tests con semilla
  fija necesitaron una semilla nueva, resueltos uno a uno, no en bloque.
- **[RESUELTO] `--lot-size` (CLI, nuevo)**: `--import-seleccion` usaba
  siempre la parcela de ejemplo fija (14x16), sin forma de ajustarla.
  Añadido para acercarse al tamaño real de una parcela, y también
  porque hacía falta para recrear un caso de dificultad real y
  ESTABLE (por espacio, no por una coincidencia de forma que una
  mejora futura del algoritmo pudiera volver a resolver) en los tests
  de reintento de semillas.
- Suite final: 339/339 (309 unitarios + 30 integración), `pyflakes` y
  `mypy` limpios (77 archivos).

## [ARCH:ancho-libre-estancia] AnchoLibreEstanciaValidator

A.3.2.1: declarado en `nhv.lua` (NHV.anchoLibreMin) pero nunca
conectado a ningún validador en la fuente; valores confirmados de
forma independiente (Anexo I, Decreto de Galicia). Solo cubre 5
categorías (estancia mayor, dormitorios, cocina, baño) -- comedor,
despacho, aseo, lavadero, tendedero, trastero, almacenamiento no
tienen ancho libre asignado en ningún sitio de la fuente (cubiertos
en cambio por `AnchoLibrePracticoValidator`, no normativo).

La "estancia mayor" aquí es estrictamente LIVING_ROOM -- a diferencia
de `EstanciaMinimumAreaValidator`, no hace fallback a la de mayor
área (para no duplicar ese aviso).

# Generador -- área objetivo (declarada vs. generada)

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:area-objetivo] AreaObjetivoValidator + causa raíz real + huella construible

A petición del usuario, con una captura de pantalla real: un Pasillo
declarado a 4.0m² se generaba visiblemente más grande que un
Dormitorio declarado a 8.0m². Investigación completa en varias fases.

### Fase 1: el validador que expuso el problema real

`AreaObjetivoValidator` (±15% de tolerancia, confirmado explícitamente
con el usuario, NO normativo): compara el área realmente generada de
cada estancia contra su área declarada. Al conectarlo como restricción
dura, expuso que el problema no era cosmético -- estancias de servicio
pequeñas se generaban hasta 100 VECES su área declarada en varios
escenarios reales probados (lavadero 1.5m²→157m², baño 5m²→81m²).

### Fase 2: dos bugs reales en `partition_tree.py`

Investigado contra la fuente del algoritmo (Bruls et al., squarified
treemap, "área predefinida sin ningún espacio sin usar" -- coincidencia
EXACTA por diseño). La desviación la introducía nuestra propia
extensión:

1. **`slide_wall` con límites absolutos, no relativos**: `[0.15, 0.85]`
   permitía que CUALQUIER corte se deslizara hasta esos extremos sin
   importar su proporción "justa" -- un corte cuya proporción justa es
   3% podía acabar en 85% (28x) tras muchas iteraciones, sin ninguna
   fuerza que lo devolviera. Corregido acotando RELATIVO a la
   proporción derivada del área de cada corte concreto (±20%), no una
   ventana absoluta igual para todos.
2. **`ratio_override` obsoleto tras `swap_leaves`/`swap_children`**:
   un ratio ya fijado por `slide_wall` para una estancia queda
   "congelado" con un número que no tiene relación con la estancia
   NUEVA que ocupa esa posición tras un intercambio -- nada lo
   invalidaba. Corregido limpiando el override de todos los
   antecesores de las hojas intercambiadas.

Verificado empíricamente en varios escenarios: de 0/20 semillas
convergiendo (antes) a que ninguna de las desviaciones sea ya por área
(después) -- las violaciones restantes en escenarios complejos son de
OTRO tipo (adyacencia, contacto exterior, proporción), no de área.

### Fase 3: la huella construible (footprint.py) -- idea del usuario

Incluso con los dos bugs corregidos, una parcela mucho más grande que
la suma de áreas declaradas seguía forzando, por construcción (el
árbol de partición llena el 100% de lo que se le da), que TODAS las
estancias se inflaran proporcionalmente. El usuario propuso la
solución de raíz: la vivienda no tiene por qué ocupar toda la parcela
-- igual que una vivienda unifamiliar real casi nunca ocupa el 100%
de su solar.

- **Nuevo módulo `footprint.py`**: calcula una huella construible
  (suma de áreas declaradas + margen del 15%, NO normativo) DENTRO del
  área edificable, no toda ella. El sobrante es VACÍO real (jardín/
  patio) -- confirmado explícitamente: "es parte exterior siempre".
- **Anclada al lado de entrada** (`Lot.entrance_side`) -- la vivienda
  hacia la calle, el vacío detrás/alrededor, centrada en el eje
  perpendicular. Confirmado explícitamente.
- **La PROPORCIÓN de la huella (ancho:alto) es parte de la búsqueda**,
  no fija -- nuevo movimiento `resize_footprint` en
  `SimulatedAnnealingLayoutGenerator` (20% de las iteraciones), junto
  a los 4 movimientos ya existentes del árbol. Confirmado
  explícitamente ("que la búsqueda del propio generador también
  explore la proporción de la huella").
- **VACÍO no es un `Room` del dominio** -- solo geometría para el
  visor (`Layout.metadata["vacio_rings"]`, lista de anillos de
  coordenadas, no WKT -- evita necesitar un parser de WKT en
  JavaScript). Confirmado explícitamente ("solo como zona sombreada en
  el visor, sin ser un Room del dominio"). Dibujado como capa de fondo
  discontinua en el visor, antes que las estancias.
- **Limitación conocida, documentada, no oculta**: el vacío no se
  transforma todavía con el modo espejo (mirrorH/V/rotación) -- se
  omite su dibujo si el plano está transformado, en vez de dibujarlo
  en el sitio equivocado. Pendiente para una sesión futura.

### Estado real de la suite de integración -- honesto, no maquillado

La suite unitaria (373 tests, incluidos 12 nuevos de `footprint.py`)
está limpia. La suite de INTEGRACIÓN (generación real de extremo a
extremo con semillas fijas) quedó parcialmente pendiente: varios
fixtures existentes (`build_sample_program`/`build_sample_lot` del
CLI, y varios tests en `test_generate_building.py`,
`test_generate_layout_use_case.py`) usan parcelas que, incluso con la
huella construible ya corrigiendo el problema de raíz, siguen siendo
escenarios exigentes (varias estancias con restricciones de adyacencia
estrictas simultáneas) que no convergieron con las semillas por
defecto dentro del tiempo disponible en esta sesión -- confirmado que
las violaciones restantes ya NO son de área (el problema de raíz está
resuelto), son de otro tipo, y encontrar semillas nuevas que
converjan con todas las restricciones a la vez es trabajo pendiente,
no un fallo del arreglo.

## [ARCH:area-objetivo-acumulada] reset_ratio -- deshacer deriva acumulada

A petición del usuario, continuando el diagnóstico sistemático:
confirmado empíricamente que una estancia con varios antecesores en
el árbol, cada uno con su propio `ratio_override` activo de forma
independiente, acumula la deriva de TODOS ellos a la vez -- una
estancia real con 4 antecesores, 2 con override activo, llegaba a
60-70% de desviación final aunque cada corte individual estuviera
dentro del ±20% permitido por corte.

- **Causa raíz**: `slide_wall` solo AÑADE deriva (acotada por corte),
  pero ningún movimiento existente la DESHACE -- no había forma de
  que la búsqueda revirtiera un `ratio_override` que ya no hiciera
  falta.
- **Nuevo movimiento `reset_ratio`** (5º movimiento, junto a
  swap_leaves/flip_direction/swap_children/slide_wall): elige un nodo
  interno CON override activo y lo limpia, volviendo a la proporción
  justa derivada del área. No-op si no hay ningún override que
  deshacer (no falla, no cambia nada).
- **Impacto confirmado empíricamente**: en el escenario de programa
  mínimo, de 2/15 a 6/15 semillas convergiendo. En el escenario
  complejo (11 estancias, 6 adyacencias), las desviaciones de área
  restantes bajaron de 60-90%+ a 15-17% (rozando el umbral) -- el
  problema de área está prácticamente resuelto también para árboles
  profundos; lo que queda ahí ahora es dificultad REAL de adyacencia/
  proporción simultáneas, no un bug escondido.
- Tests nuevos: `reset_ratio` limpia un override existente (verificado
  sobre múltiples semillas), y es no-op verificado cuando no hay nada
  que resetear (RNG de mentira para forzar el movimiento exacto, sin
  depender de que otros movimientos como slide_wall no interfieran).
- Suite final: 378 unitarios, pyflakes limpio.

### Estado del escenario complejo (11 estancias, 6 adyacencias) -- honesto

Tras los tres arreglos de esta ronda de diagnóstico (BanoAcceso,
distancia graduada de núcleo húmedo, reset_ratio), el escenario más
exigente del proyecto (`build_sample_program`) sigue sin converger en
20 semillas probadas -- pero el CARÁCTER del problema cambió por
completo: antes las violaciones eran desviaciones de área masivas
(cientos/miles %) mezcladas con todo lo demás; ahora son
específicamente las 6 restricciones de adyacencia simultáneas
(living-entrance, living-garage MUST_BE_AWAY siendo adyacentes) y
proporciones ajustadas (dining 11.4:1, garage 5:1) -- una dificultad
combinatoria real de satisfacer TODO a la vez, no un bug. Sigue
pendiente en `CONTINUIDAD.md`: o bien una búsqueda de semillas más
extensa, o considerar si 6 restricciones MUST_BE_NEAR/AWAY
simultáneas es razonable para un único recocido simulado con este
conjunto de movimientos, o si necesita su propio movimiento dedicado
(p.ej. "acercar hacia adyacencia pendiente").

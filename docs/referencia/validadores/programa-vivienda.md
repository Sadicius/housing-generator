# Validadores -- programa de vivienda (ámbito edificio)

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:vivienda-minima] ViviendaMinimaValidator

"Programa mínimo": texto exacto del Decreto 29/2010 de Galicia,
I.A.2.3 (confirmado por investigación independiente, cita textual):
salón + cocina + baño + lavadero + tendedero + almacenamiento general.
`nhv.lua` no modela este apartado en absoluto.

Corrección real: una primera versión solo exigía salón+cocina+baño,
basada en el estándar genérico CTE/Orden de 1944 (válido para otras
comunidades) en vez de buscar el texto específico de Galicia primero
-- el usuario detectó que algo no cuadraba, y al revisar la fuente
exacta se confirmó que faltaban tres piezas enteras.

Mapeo "estancia" → LIVING_ROOM: el decreto exige en otro apartado que
exista "al menos una estancia mayor"; este proyecto ya adoptó como
convención que la estancia mayor es siempre el salón.

## [ARCH:bano-acceso] BanoAccesoGeneralValidator

Regla "Condicional" del catálogo (BEDROOM/MASTER_BEDROOM x BATHROOM):
"1 baño → acceso solo vía pasillo; ≥2 baños → uno puede ser en-suite".
NO es un valor estático de tabla -- depende de cuántos BATHROOM tenga
el Program real. Formulación equivalente más simple, sin ramificar por
conteo: al menos un baño debe tener acceso directo a circulación
general; con 1 solo baño, la exigencia recae necesariamente sobre él.

## [ARCH:bano-acceso] Bug real encontrado en diagnóstico sistemático: exigencia imposible

A petición del usuario: en vez de seguir buscando semillas a ciegas,
diagnóstico sistemático aislando variables una a una para el problema
de convergencia. Metodología: probar SIN adyacencia (línea base),
luego con menos estancias, para separar "dificultad por adyacencia"
de otras causas.

- **Hallazgo real**: incluso el programa MÍNIMO absoluto (6 estancias,
  sin ninguna adyacencia declarada) fallaba en 15/15 semillas
  probadas. Investigado el motivo exacto en vez de asumir "es
  difícil": `BanoAccesoGeneralValidator` calcula `circulation_ids`
  filtrando estancias de categoría CIRCULACIÓN presentes en el
  programa -- si el programa no tiene NINGUNA (válido: "programa
  mínimo" no exige recibidor/pasillo), ese conjunto queda vacío y la
  condición `neighbors & circulation_ids` nunca puede cumplirse, sea
  cual sea la geometría. No era "difícil de satisfacer" -- era
  MATEMÁTICAMENTE IMPOSIBLE, sin que nada lo señalara como tal.
- **[RESUELTO]** Corregido con el mismo patrón "no aplica" que ya
  usa `EspacioAccesoValidator`: sin ninguna circulación en el
  programa, la regla no se puede evaluar, no se exige.
- **3 tests existentes corregidos** (`test_bano_acceso_validator.py`,
  `test_generate_building_bano_acceso.py`): probaban "baño capturado
  en dormitorio" pero su propio montaje TAMPOCO tenía circulación en
  absoluto -- sin darse cuenta, estaban probando el bug (siempre
  falla sin circulación), no el caso real que pretendían. Corregidos
  añadiendo un corridor real en la escena, que no toca al baño.
- **Impacto medido, no solo teórico**: en el escenario del programa
  mínimo, este único arreglo mejoró la convergencia de 0/15 a 3/15
  semillas -- confirma que era un bug real con impacto real, no un
  caso extremo sin importancia.
- El escenario más complejo (`build_sample_program`, 11 estancias, 6
  restricciones de adyacencia simultáneas) SÍ tiene recibidor
  declarado, así que este bug concreto no era su bottleneck principal
  -- sigue pendiente de una búsqueda de semillas más extensa,
  documentado en `CONTINUIDAD.md`.
- Suite final: 374 unitarios, pyflakes limpio.

## [ARCH:vivienda-accesible] ViviendaAccesibleValidator

Retomado de un módulo Lua de un proyecto anterior del usuario
(accesibilidad.lua), investigado a fondo contra DB-SUA (Anejo A) +
Código de Accesibilidad de Galicia (Decreto 35/2000, act. Decreto
74/2013) + Base 5.4 gallega. OPT-IN (DB-SUA 9.1: la accesibilidad solo
es exigible en viviendas designadas específicamente, no todas).

Alcance: de todo lo que cubre la fuente Lua (también mobiliario --
altura de encimera, aproximación a la cama, barras de apoyo...), aquí
solo se modela lo GEOMÉTRICAMENTE VERIFICABLE con `Room` (rectángulo
con área, sin mobiliario) -- círculo de giro y ancho de pasillo. El
resto exigiría modelar mobiliario como piezas propias, mismo motivo
que C.10 (luz directa): fingir una comprobación sin datos reales sería
peor que no darla.

`TIPOS_CON_CIRCULO_GIRO`: mismas piezas que la fuente Lua comprueba
(`acc.circuloGiro`) + DINING_ROOM (misma zona de estar). No incluye
servicios pequeños (lavadero, tendedero, almacenamiento).

## [ARCH:dormitorio-armario] DormitorioArmarioValidator

Espacio de armario empotrado -- confirmado por investigación
(condiciones mínimas de habitabilidad, varias fuentes independientes),
NO presente en nhv.lua. Cuenta DENTRO de la superficie del dormitorio
(no es un Room aparte): profundidad 0.60m, largo 1.00m (>6m²) o 1.50m
(>8m²). El umbral para ≤6m² no aparece en las fuentes consultadas; se
usa 1.00m como valor conservador, marcado como asunción, no cifra
normativa confirmada. Altura (2.20m) no se comprueba aquí -- la cubre
`AlturaLibreValidator` sobre la misma habitación.

## [ARCH:espacio-acceso] EspacioAccesoValidator

Numeración exacta incierta tras la renumeración del Decreto 128/2023
(probablemente A.3.3 "Espacios de comunicación" en la versión
vigente): cuadrado inscribible de 1.50m en contacto con la puerta de
entrada. "En contacto con la puerta" NO se comprueba -- este proyecto
no modela puertas/accesos (mismo hueco identificado en
relaciones_espaciales.md). Documentado como alcance pendiente
sistemático, no como aviso repetido caso a caso.

Sin ENTRANCE_HALL en el programa, no aplica (la norma exime este caso
cuando el acceso es directo a través de la estancia mayor -- ya
cubierto por el mínimo de Tabla 1).

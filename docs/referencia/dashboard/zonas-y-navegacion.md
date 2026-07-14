# Dashboard -- zonas y navegación

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:zonas] Reestructuración de navegación por zonas

A petición del usuario, tras un DAFO extremo del HTML/pestañas: la
estructura plana de 7 pestañas mezclaba consulta, trabajo y
visualización sin ninguna distinción, con orden puramente histórico
(el de las sesiones en que se fueron añadiendo), un flujo real de
generación partido en dos pestañas no contiguas (Sección → salto
silencioso a Visor), y dos "islas" (Cronograma, Catálogo) sin ninguna
relación estructural con el resto.

- **3 zonas**: Diseño (Sección vertical + Visor de plano, presentados
  como un flujo explícito de 2 pasos numerados, no un salto de pestaña
  sorpresa), Consulta (Relaciones entre tipos + Fichas + Catálogo
  constructivo), Planificación (Cronograma de obra, presentada
  honestamente como herramienta aparte, no forzada a parecer
  conectada).
- **Matriz de adyacencia + Sinergias fusionadas** en una sola pestaña
  "Relaciones entre tipos" con selector de vista (tabla/red) --
  confirmado explícitamente con el usuario como decisión de contenido
  separada de la reorganización de navegación. Ambos contenidos
  originales conservados intactos, solo re-envueltos.
- Extraído y reensamblado con BeautifulSoup (no regex/string
  splicing a mano) para manipular HTML real de forma fiable.
- **Bug real encontrado y corregido durante la propia reestructuración**:
  los scripts clásicos se quedaron en su posición original (el final
  de la estructura plana anterior) tras reordenar los paneles en
  zonas -- como el reordenamiento dejó contenido real DESPUÉS de los
  scripts en el documento, un navegador real habría fallado al
  ejecutar código de nivel superior (`document.getElementById(...)`
  en `09-init.js`) sobre elementos que todavía no existían en ese
  punto del análisis del HTML. `jsdom` no lo detectó (analiza el
  documento completo antes de ejecutar), así que se verificó también
  con `wkhtmltoimage` (motor más estricto) tras corregirlo. Movidos
  los 11 scripts locales al final real del `<body>`, con un test
  permanente que impide que esto vuelva a pasar en silencio.
- **Bug de estado real encontrado y corregido**: el manejador de clic
  de pestañas anterior quitaba `active` de TODAS las pestañas y
  paneles del documento globalmente, no solo del grupo relevante --
  esto habría dejado zonas ya visitadas sin ningún panel activo al
  volver a ellas. Corregido acotando el manejador al grupo
  (`.flow-indicator` o `.subtabs-row`) más cercano del propio tab
  pulsado. Verificado explícitamente con un test que visita varias
  zonas/pestañas y confirma que el estado se conserva al volver.
- También se limpiaron comentarios HTML huérfanos (marcadores de las
  pestañas antiguas, sin nada a lo que apuntar tras el reordenamiento)
  y se corrigió el orden de atributos de un `<link>` reformateado por
  BeautifulSoup.
- Verificado con `jsdom` (todas las zonas, subpestañas, selector de
  vista, cronograma, modo espejo, salto automático al generar) y
  `wkhtmltoimage` (captura real + confirmación cuantitativa de
  píxeles).
- Tests de sanidad reescritos: estructura de 3 zonas, fusión
  Matriz+Sinergias con contenido conservado, posición correcta de
  scripts respecto al contenido.
- Suite final: 349 unitarios, pyflakes limpio.

## [ARCH:notas-alcance] Notas de alcance movidas a panel dedicado

A petición del usuario: las 3 notas de alcance (Matriz/Sinergias,
Catálogo constructivo, Cronograma de obra) estaban siempre visibles,
ocupando espacio permanente en el área de trabajo -- una de ellas
(Matriz) ni siquiera vivía dentro de una pestaña, estaba fija arriba
de toda la página, visible sin importar en qué zona estuviera el
usuario.

- Movidas (no copiadas) a un panel dedicado "Notas de alcance",
  nueva subpestaña de Zona Consulta -- coherente con la propia
  filosofía de esa zona (contenido de consulta, sin estado).
- En su lugar original: un indicador pequeño (`ⓘ nota de alcance`)
  que, al pulsarlo, cambia a Zona Consulta, abre la subpestaña Notas,
  y resalta + hace scroll hasta el bloque concreto -- "al alcance" en
  un clic, sin ocupar espacio por defecto.
- Extraído/movido con BeautifulSoup (mismo método que la
  reestructuración por zonas), preservando el contenido real de cada
  nota (enlaces, código inline) intacto.
- **Hallazgo real durante la verificación**: `bloque.scrollIntoView`
  no existe en `jsdom` (limitación conocida del propio `jsdom`, no del
  código) -- protegido con una comprobación defensiva para no lanzar
  error en ese entorno de test, sin cambiar el comportamiento en un
  navegador real.
- Verificado con `jsdom`: los 3 indicadores navegan correctamente
  desde cualquier zona, resaltan el bloque correcto, y las pestañas de
  trabajo ya no muestran ningún `.caveat` por defecto. Verificado
  también con `wkhtmltoimage`.
- Test permanente: confirma que las 3 notas viven dentro del panel
  dedicado (no duplicadas en otro sitio -- cuenta exacta de 3
  `.caveat` en todo el documento) y que cada indicador enlaza a su
  ancla real.
- Suite final: 352 unitarios, pyflakes limpio.

# Dashboard -- lanzador e instalación

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:inicio-launcher] INICIO.html -- punto de entrada del proyecto

A petición del usuario: un archivo único para "iniciar todo", dado que
el dashboard real vive en una ruta anidada
(`docs/visualizador/relaciones_espaciales.html`) y el README no
mencionaba el dashboard en absoluto (documentaba solo el CLI).

- `INICIO.html` en la raíz del proyecto -- se abre con doble clic,
  mismo patrón "sin servidor" que el resto (reutiliza
  `docs/visualizador/relaciones_espaciales.css` vía ruta relativa,
  misma estética cianotipo).
- Enlace principal al dashboard real, resumen de las 3 zonas, y
  enlaces a toda la documentación (`GUIA_USO.md`, `COMO_FUNCIONA.md`,
  `architecture.md`, `CONTINUIDAD.md`, `README.md`) con una nota
  honesta: los `.md` pueden descargarse en vez de mostrarse según la
  configuración del navegador, no es un fallo del archivo.
- `README.md` actualizado: el dashboard pasa a presentarse como la
  forma principal de uso (generación real vía Pyodide, sin instalar
  Python), el CLI queda como opción para desarrollo/automatización,
  no como el único camino documentado.
- Verificado con `wkhtmltoimage` desde la raíz real del proyecto
  (confirmación cuantitativa de píxeles: el CSS real cargó
  correctamente por la ruta relativa) y con un test permanente que
  comprueba que TODOS los enlaces locales de `INICIO.html` apuntan a
  archivos que existen de verdad, no rutas rotas.
- Suite final: 350 unitarios, pyflakes limpio.

## [ARCH:instalar-scripts] instalar.sh / instalar.bat -- automatizar el entorno del CLI

A petición del usuario, tras crear INICIO.html: los 3 pasos manuales
de instalación del CLI (venv, activar, pip install) también merecían
un solo paso -- aclarado explícitamente que esto es para el CLI/
desarrollo, no para el dashboard (que no necesita nada de esto).

- `instalar.sh` (Mac/Linux) e `instalar.bat` (Windows): idempotentes
  (si `.venv` ya existe, lo reutilizan en vez de recrearlo), detectan
  si Python está instalado con un mensaje de error claro si no,
  imprimen las dos formas de usar el entorno después (activar vs.
  llamar directamente sin activar).
- **`instalar.sh` verificado de extremo a extremo**, no solo revisado:
  ejecutado en una copia aislada del proyecto, confirmado que crea el
  entorno, instala las dependencias correctas, y que el CLI + la suite
  de tests (350 en ese momento) funcionan de verdad con ese entorno
  recién creado. Confirmada también la idempotencia (segunda ejecución
  reutiliza `.venv` sin recrearlo).
- **`instalar.bat` NO se ha podido ejecutar** en este entorno (sin
  Windows/cmd.exe disponibles) -- revisado a mano con cuidado siguiendo
  convenciones estándar de batch, pero sin verificación de ejecución
  real. Comunicado explícitamente esta limitación al usuario, no
  presentado como "verificado" cuando no lo está.
- `README.md` e `INICIO.html` actualizados mencionando los scripts
  como opción para quien use el CLI, dejando claro que el dashboard no
  los necesita.
- Test permanente: confirma que ambos archivos existen, y verifica de
  verdad la sintaxis de `instalar.sh` (`bash -n`) -- no hay forma de
  verificar la sintaxis de `instalar.bat` en este entorno.
- Suite final: 351 unitarios, pyflakes limpio.

## [ARCH:reorganizacion-docs] Fase 1: mover docs/visualizador a html/

A petición del usuario, tras revisar cómo organizan su documentación
otros proyectos reales (ox_lib de Overextended, rsg-docs) para
inspirar una reorganización propia: separar claramente "la aplicación
en sí" de "documentación sobre el proyecto" -- `docs/visualizador/`
pasa a ser `html/`, en la raíz del proyecto, al mismo nivel que `src/`
y `tests/`.

- Movido con `git mv` (preserva el historial de cada archivo).
- Como todo dentro de la carpeta usa rutas relativas entre sí
  (CSS/JS/bundle referenciándose unos a otros), mover la carpeta
  entera no rompió nada internamente -- solo hubo que actualizar las
  referencias que apuntan HACIA ella desde fuera: `INICIO.html`,
  `README.md`, `scripts/regenerar_bundle_pyodide.py` (ruta de
  salida del bundle), `tests/unit/test_dashboard_sanity.py`
  (`VISUALIZADOR_DIR`), `docs/CONTINUIDAD.md`, `docs/GUIA_USO.md`,
  `instalar.sh`, y un comentario en `domain/enums.py`.
- De paso, corregido un "5 pestañas" obsoleto en `CONTINUIDAD.md`
  (ya son 7, en 3 zonas) que apareció al revisar esa misma línea.
- Las 6 menciones a la ruta antigua que quedan en `architecture.md`
  (histórico cronológico) se dejan intactas a propósito -- describen
  fielmente la estructura que existía en ese momento de la sesión, no
  deben reescribirse.
- Verificado con `jsdom` (dashboard completo funcional desde la nueva
  ruta) y `wkhtmltoimage` (INICIO.html carga el CSS real
  correctamente desde la raíz). Bundle Pyodide regenerado en la
  nueva ubicación.
- Suite final: 381 unitarios, todos los tests de sanidad del
  dashboard actualizados y en verde.

Fase 2 (reorganización de `docs/` en carpetas temáticas) documentada
por separado, en curso.

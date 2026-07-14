# Dashboard -- exportar el plano generado

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:exportar-plano-generado] Exportar el plano ya generado, no solo la selección

A petición del usuario, tras probar el flujo real de generación:
exportaba la *selección* (paso 1, "Exportar selección (JSON)" --
tipos y cantidades, formato de entrada para el CLI) y, al volver
después a intentar cargar ESE archivo en el visor para revisarlo,
obtenía el error ya conocido ("falta rooms") -- confusión real entre
dos formatos JSON con nombres de botón parecidos, no un fallo nuevo:
faltaba la pieza que permitiera cerrar el círculo sin pasar por el
CLI.

- **Nuevo botón "exportar plano generado"**, en el propio Visor de
  plano (no en el paso 1) -- exporta el RESULTADO ya generado
  (`rooms`/`doors`/`metadata` reales de `LOADED_PLANS`), no la
  selección de entrada.
- **Formato consolidado ÚNICO** (`plano_generado.json`), a diferencia
  de los `edificio_planta_*.json` del CLI (uno por planta) --
  `{"floors": {"<etiqueta>": {rooms, doors, metadata}, ...}}`,
  confirmado explícitamente con el usuario como la forma preferida
  ("un único archivo que contiene la información").
- El cargador de archivos del visor detecta y acepta este formato
  nuevo (un solo archivo con clave `floors`) ADEMÁS del formato
  multi-archivo existente del CLI -- ambos caminos siguen funcionando.
- Verificado con `jsdom` el ciclo completo real: cargar 2 archivos por
  planta (como el CLI) → exportar como archivo único → recargar ESE
  mismo archivo → mismo resultado exacto (2 pestañas de planta, SVG
  renderizado, cero errores).
- Nota de proceso: un intento inicial de inyectar estado de prueba vía
  `window.LOADED_PLANS = [...]` no funcionó -- `let LOADED_PLANS` a
  nivel superior de un script clásico no se adjunta a `window.*` (la
  misma particularidad de JS ya documentada en la separación de
  archivos del dashboard). Corregido pasando por el flujo real (cargar
  archivos de verdad) en vez de inyectar estado desde fuera.
- Suite final: 353 unitarios, pyflakes limpio.

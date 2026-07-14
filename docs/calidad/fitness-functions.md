# Calidad -- fitness functions

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:fitness-functions] vulture como fitness function continua

A petición del usuario, investigados a fondo dos conceptos del
proyecto "architecture-decision-record": inmutabilidad de decisiones
aceptadas (confirmado que es la corriente dominante real -- Nygard,
Cognitect -- corrigiendo una lectura demasiado rápida anterior del
README) y "fitness functions" (Neal Ford / Rebecca Parsons,
*Building Evolutionary Architectures*): mecanismos que dan una
evaluación objetiva y CONTINUA de que una característica arquitectónica
se sigue cumpliendo, no solo que quedó documentada una vez.

- **Hallazgo real que motivó esto**: `vulture` solo se había ejecutado
  a mano, cuando se pidió explícitamente auditar código muerto -- así
  sobrevivió `infrastructure/browser_bridge.py` (78 líneas huérfanas)
  varias rondas de refactorización sin que nadie lo notara.
- **[RESUELTO] `tests/unit/test_no_dead_code.py`**: ejecuta `vulture`
  contra `vulture_whitelist.py` en cada pase de la suite normal, no
  como auditoría ocasional. `vulture_whitelist.py` contiene los 12
  elementos ya revisados y confirmados como intencionados (piezas
  alternativas de arquitectura hexagonal con tests propios, API usada
  solo en tests/, `INDIFFERENT` como decisión de diseño, `generar_edificio`
  llamado dinámicamente desde JS vía Pyodide) -- cualquier hallazgo
  NUEVO hace fallar el test hasta que se revise y, si es legítimo, se
  añada a la lista con su razón explicada.
- Verificado que de verdad detecta código muerto real (no solo que
  pasa en el estado limpio actual): se introdujo temporalmente una
  función sin usar, el test falló con un mensaje claro, se retiró y
  volvió a pasar.
- `vulture>=2.16` añadido a `[project.optional-dependencies].dev`.
- Ya teníamos otras fitness functions sin llamarlas así
  (`test_pyodide_bundle_is_not_stale_against_the_real_source`,
  `test_html_references_js_files_via_classic_tags_in_order`) -- esta
  es la primera pensada y nombrada explícitamente como tal.
- Sobre inmutabilidad: `architecture.md` ya tenía, sin planearlo así,
  una estructura de dos niveles que encaja con la práctica dominante --
  el histórico cronológico (inmutable, solo-añadir) y la sección
  "Referencia técnica por componente" (`[ARCH:tag]`, un resumen vivo
  del estado actual). No se cambió nada aquí, la distinción ya era
  correcta.
- Suite final: 344 unitarios (uno nuevo), pyflakes limpio.

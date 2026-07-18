# Arquitecturas alternativas (piezas intercambiables)

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:graph-based-generator] GraphBasedLayoutGenerator

Generador alternativo, deliberadamente simple (franjas por zona,
luego cajas por estancia dentro de cada franja) -- para ser fácil de
testear/entender, y sustituible por CSP/genético sin tocar el resto
del sistema. No conectado al pipeline principal (`container.py` usa
`BTreeLayoutGenerator`), pero mantenido con tests propios como pieza
intercambiable de la arquitectura hexagonal.

Heurística de núcleo húmedo: coloca estancias húmedas primero
(extremo izquierdo) dentro de su zona, para alinearlas en columna con
zonas contiguas. Es heurística de orden, no garantía -- con 3+
estancias húmedas en zonas no mutuamente contiguas (día y servicio
nunca se tocan directamente, solo vía noche) sigue siendo
geométricamente imposible que todas queden a distancia ≤1.

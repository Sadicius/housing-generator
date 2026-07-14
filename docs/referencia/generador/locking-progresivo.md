# Generador -- bloqueo progresivo

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:locking-progresivo] Bloqueo progresivo -- investigación profunda, corrección de rumbo real

A petición del usuario, tras varios intentos fallidos de "más
iteraciones" y "mejor temperatura": pararse a investigar de verdad
las técnicas establecidas, en vez de conformarse con la primera
explicación (combinatoria) que parecía razonable.

### Investigación real, con fuentes concretas

- **Min-conflicts** (Minton, Johnston, Philips, Laird 1990/1992):
  algoritmo real de reparación dirigida para CSP -- resuelve el
  problema de un MILLÓN de reinas en ~50 pasos de media, frente al
  fracaso de la búsqueda aleatoria pura a esa escala.
- **"Cost-independent criticality-based move selection"** (patente
  real, campo de FPGA/placement) y **"focused simulated annealing"**
  (sistemas de programación ferroviaria): mover el foco de la
  búsqueda hacia lo que está fallando ahora mismo, no al azar
  uniforme.
- **Calibración automática de temperatura** (Stamos & Lagaros,
  2024/2025): la temperatura no debería ser una constante fija,
  debería calcularse a partir del presupuesto de iteraciones real.

### Hallazgo clave del usuario, confirmado empíricamente

El usuario señaló que mi diagnóstico de "contacto exterior simultáneo
es geométricamente difícil" estaba MAL PLANTEADO. Confirmado: una
topología en tira, con TODOS los cortes en la misma dirección, da
contacto exterior trivial a las 9 estancias a la vez. El problema real
tenía dos capas, ambas confirmadas con pruebas directas, no solo
teoría:

1. **La construcción del árbol inicial no favorece formas planas**
   (`build_random_tree` elige el punto de corte uniformemente al
   azar, sin sesgo hacia formas tipo tira).
2. **La propia búsqueda deshace estructuras buenas sin protegerlas**
   -- `flip_direction` puede romper una dirección consistente ya
   conseguida en cualquier momento, sin que nada distinga "esto ya
   funciona" de "esto sigue roto".

### Bloqueo progresivo -- implementado

- Cada iteración calcula qué estancias no aparecen mencionadas en
  ninguna violación actual (`_evaluate`, una sola validación
  reutilizada para puntuación Y bloqueo, evita duplicar la
  validación).
- `swap_leaves` solo intercambia entre estancias SIN bloquear.
- El resto de movimientos solo actúan sobre nodos cuyo subárbol tenga
  al menos una estancia sin resolver.
- Válvula de escape (`ESCAPE_PROBABILITY=0.15`, NO normativo, mismo
  tipo de decisión que otros parámetros de ingeniería del proyecto):
  ignora el bloqueo por completo con esa probabilidad, para no
  atascarse si arreglar algo exige tocar temporalmente una estancia
  ya bloqueada -- la propia literatura de min-conflicts advierte que
  la versión pura, sin esto, puede quedarse atrapada en mínimos
  locales.
- `locked_room_ids=None` (por defecto) preserva el comportamiento
  anterior exacto, sin ninguna restricción.

### Resultado honesto -- mejora real, no solución completa

Probado en el escenario más exigente de esta sesión (9 estancias, sin
adyacencia): las violaciones restantes bajaron de 5-7 simultáneas a
típicamente 2 (confirmado en varios seeds), pero **no llegó a cero en
esta sesión**, ni con más iteraciones (4000) añadidas encima del
bloqueo. En el escenario más simple que ya funcionaba (6 estancias,
programa mínimo), el resultado se mantuvo en el mismo orden de
magnitud (4/15 frente a 6/15 anterior -- dentro del ruido estadístico
de una muestra de 15 semillas, no una regresión clara).

Conclusión honesta: el bloqueo progresivo es una mejora real y
medible (menos violaciones simultáneas, búsqueda más eficiente), pero
el escenario más complejo de este proyecto sigue sin una solución
completa encontrada en esta sesión -- documentado como tal en
`CONTINUIDAD.md`, no maquillado.

- Tests nuevos: bloqueo protege estancias bloqueadas en `swap_leaves`
  (verificado por posición fija, forzando el movimiento con RNG de
  mentira, ya que `swap_leaves` nunca reestructura el árbol);
  `locked_room_ids=None` preserva el comportamiento anterior exacto;
  movimientos sobre nodos internos evitan subárboles completamente
  bloqueados.
- Suite final: 381 unitarios, pyflakes y mypy limpios (83 archivos).

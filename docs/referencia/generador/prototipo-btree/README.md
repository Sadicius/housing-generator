# Migración planificada: de árbol de partición (guillotina) a árbol B*

> Plan en curso, a petición del usuario, tras reconsiderar si la
> restricción de guillotina era realmente un límite fundamental
> ("era una idea para explicarte como podríamos solucionar un
> problema inicial... pero creo que podemos mejorarlo mucho"). No
> era un límite físico, era una elección de partida.

## Por qué

Investigado el problema de fondo de convergencia en escenarios
complejos (9-11 estancias): la causa raíz confirmada es que una
topología en tira, con dirección de corte consistente, resuelve
trivialmente el contacto exterior simultáneo para muchas estancias —
pero nuestro árbol de partición actual solo puede representar
particiones tipo **guillotina** (cada corte divide el rectángulo
entero de lado a lado). Las formas en L, en U, en T, o con patio
interior son, por definición, IMPOSIBLES de representar con
guillotina pura, sin importar cuánto se mejore la búsqueda.

Investigado si existe una alternativa real y probada (no un invento
nuestro): sí -- el campo del floorplanning de VLSI (de donde ya
sacamos el squarified treemap) tiene toda una familia de
representaciones "no-guillotina" (Sequence Pair, Corner Block List,
O-Tree, **B\*-Tree**), usadas en producción, compatibles con recocido
simulado, con más de dos décadas de desarrollo y validación.

## El algoritmo real (Chang & Chang, 2000 -- 572 citas)

- El árbol es binario, pero cada nodo representa una **estancia
  directamente** (no un corte + hojas, como el nuestro).
- **Coordenada X**: la decide la propia estructura del árbol. Hijo
  izquierdo = "el bloque más bajo, pegado a la derecha del padre"
  (`x = x_padre + ancho_padre`). Hijo derecho = "el primer bloque
  arriba, misma X que el padre" (`x = x_padre`).
- **Coordenada Y**: requiere una estructura de **contorno** (perfil
  tipo "skyline" de lo ya ocupado) -- cada estancia nueva "cae" hasta
  apoyarse en lo que ya hay ocupado en su rango de X.
- Movimientos probados para el recocido: **rotar** una estancia,
  **mover** una estancia a cualquier otro punto del árbol,
  **intercambiar** dos estancias.
- Produce arreglos "admisibles" (compactados abajo-izquierda): ningún
  módulo se puede mover más abajo ni más a la izquierda.

## Fase 0 -- prototipo aislado, verificado (completada)

Código en `prototipo-btree/btree.py` (aislado, no toca el proyecto
real). Verificado con rigor, no solo "parece funcionar":

- Coordenadas calculadas coinciden EXACTAMENTE con un cálculo hecho a
  mano antes de ejecutar nada.
- Con 5 estancias de prueba, la silueta resultante es genuinamente NO
  rectangular: 0 solapes (área de la unión = suma exacta de áreas),
  14 vértices en el contorno exterior (un rectángulo simple tiene 4),
  y un 28% de vacío que surge SOLO del propio empaquetado, sin
  necesitar ningún mecanismo de huella/anclaje aparte. Ver
  `resultado.png`.
- El movimiento de intercambio (Op3) verificado: cambia las
  posiciones de verdad, mantiene el empaquetado sin solapes después
  del movimiento.

## Fase 1 -- decisiones de diseño para nuestro dominio (completada)

Confirmadas explícitamente con el usuario, una por una:

1. **Dimensiones de cada estancia**: no son fijas (a diferencia de un
   módulo de chip) -- área objetivo + proporción buscable, mismo
   espíritu que el `ratio_override`/`slide_wall` actual. Dada un área
   `A` y una proporción `r`: `ancho = √(A·r)`, `alto = √(A/r)` (el
   área se conserva exactamente, sea cual sea `r`).
2. **Rotación**: movimiento explícito propio (Op1 de la literatura),
   no solo un caso extremo del deslizamiento continuo -- da saltos
   grandes que a un deslizamiento fino le costaría muchos pasos
   alcanzar.
3. **Huella construible**: deja de decidirse de antemano -- es el
   RESULTADO (el rectángulo envolvente de lo que salga del
   empaquetado), no el punto de partida como hoy.
4. **Anclaje**: se reutiliza directamente la lógica ya existente de
   `footprint.py` (lado de entrada, `Lot.entrance_side`) -- solo
   cambia qué geometría se ancla (el bounding box del empaquetado, no
   un rectángulo pre-decidido).
5. **Vacío -- ahora dos capas, no una**:
   - Exterior: `parcela_edificable - huella_anclada` (igual que hoy).
   - **Interior (nuevo)**: `huella - union(estancias reales)` -- los
     huecos que quedan DENTRO de la propia silueta del empaquetado
     cuando no es perfectamente compacto. No podía existir antes,
     porque la huella siempre era un rectángulo macizo. Podría
     funcionar como patios/lucernarios internos si se posiciona bien
     -- conecta con la idea original del usuario sobre el vacío
     fragmentado.
6. **`FOOTPRINT_BUFFER` (15%, criterio nuestro) -- ELIMINADO**: tras
   plantear la pregunta directamente ("¿mantenemos un margen
   explícito, o dejamos que la búsqueda decida?"), el usuario aclaró
   el motivo real detrás del 15% original: control de coste de obra,
   no el tamaño de la huella en sí. Razonamiento acordado: lo que de
   verdad cuesta dinero es el área CONSTRUIDA (cada estancia), no el
   tamaño de la huella completa (que incluye vacío sin construir).
   `AreaObjetivoValidator` (±15% por estancia, ya existente) ya
   protege exactamente eso -- un segundo número para "cuánto puede
   crecer la huella en conjunto" sería redundante. La huella puede
   salir tan compacta u holgada como la búsqueda encuentre.

## Verificado con código real (no solo propuesto)

```python
huella = box(*union_estancias.bounds)  # resultado, no punto de partida
huella_anclada = box(offset_x, 0, offset_x + huella.bounds[2], huella.bounds[3])
vacio_exterior = buildable.difference(huella_anclada)          # igual que hoy
vacio_interior = huella.area - union_estancias.area            # NUEVO
```

Con el ejemplo de 5 estancias: 105m² de vacío exterior + 15.5m² de
vacío interior, de 160m² de parcela total.

  árbol).
- Fase 3: auditoría de validadores y visor.
- Fase 4: implementación incremental, en paralelo al sistema actual,
  no en sustitución directa.
- Fase 5: comparación empírica con nuestros escenarios ya conocidos,
  decisión de corte.

## Fase 2 -- movimientos del recocido (completada)

### Mapa de movimientos

| Movimiento actual | Equivalente B*-tree | Nota |
|---|---|---|
| `swap_leaves` | Op3: intercambiar dos estancias | Directo, mismo concepto |
| `slide_wall` | Redimensionar "módulo blando" (área fija, proporción variable) | La literatura ya trata exactamente nuestro caso |
| `reset_ratio` | Restablecer proporción a un valor natural | Misma función, adaptada |
| `swap_children` | Intercambiar qué hijo va "a la derecha" vs "encima" | Se conserva como movimiento local |
| `flip_direction` | **Desaparece** | B*-tree no tiene "dirección de corte" -- ya no aplica |
| *(no existe hoy)* | **Op2: mover una estancia a cualquier punto del árbol** | La más valiosa -- reestructura de verdad |

Verificado con código real (`docs/referencia/generador/prototipo-btree/btree.py`):
mover `trastero` de colgar de `cocina` a colgar de `dormitorio` cambia su
posición de (8,0) a (3,3) -- una reestructuración real, no un intercambio
de identidad entre dos huecos ya existentes. Esto ataca directamente la
limitación que diagnosticamos en el sistema actual: nuestros movimientos
de hoy solo *reasignan* qué estancia ocupa un hueco existente, nunca
*crean* huecos nuevos.

### Hallazgo real e importante: el contorno compartido complica el bloqueo progresivo

Verificado con código (no solo teoría): en B*-tree, cambiar el tamaño de
UNA estancia puede desplazar la posición de OTRA que no se tocó
directamente, si esta última se apoya en el contorno que deja la primera
-- confirmado que `trastero` se desplazaba de y=4 a y=7 al cambiar solo
la altura de `cocina`, sin tocar `trastero` para nada.

Esto significa que el bloqueo progresivo actual ("no toques el nodo de
una estancia ya resuelta") no se traslada tal cual -- no basta con
proteger el propio nodo, porque un cambio en un antecesor puede
desplazarla igualmente.

**Decisión confirmada con el usuario**: comprobar el efecto REAL tras
cada movimiento candidato (recalcular posiciones antes/después, rechazar
si alguna estancia bloqueada cambió de posición como efecto colateral) --
más costoso computacionalmente que proteger solo la cadena de
antecesores, pero más flexible (permite más movimientos legítimos).
Verificado con código: rechaza correctamente los desplazamientos reales
(incluido uno no anticipado -- cambiar la altura de `salón` también
cambiaba su ancho, al conservar el área, afectando a un descendiente
suyo dos niveles por debajo), y acepta correctamente los cambios
genuinamente independientes (una rama del árbol sin ningún antecesor en
común con la estancia bloqueada).

## Fase 3 -- auditoría de validadores y visor (completada)

Buen hallazgo: la arquitectura hexagonal ya mantenida en todo el
proyecto reduce mucho el alcance real de la migración -- verificado
con `grep`, ni el dominio, ni la capa de aplicación, ni ningún
validador importan `partition_tree`/`PartitionNode`. Todos operan
sobre `Layout` (resultado ya colocado), no sobre el mecanismo de
generación.

### Sin cambios (verificado)
- Los 24 validadores -- muestreados varios, todos dependen solo de
  `Layout`, `shapely`, enums de dominio.
- `GeometryAdjacencyGraphBuilder` -- mide borde compartido entre
  polígonos directamente, representación-agnóstico.
- Dominio y aplicación completos -- cero referencias al árbol.
- `planoCanvasBounds` del visor -- ya calcula min/max genérico.

### Cambios reales necesarios
- **`ExteriorContactValidator`**: hoy compara cada estancia contra
  `layout.lot.buildable_area.polygon` (la parcela edificable
  completa) -- funciona hoy porque la huella siempre es maciza
  (coincide con el borde real). Con huecos internos, una pared que da
  a un patio interior debe contar como contacto exterior real
  también, y hoy no lo haría. `count_exterior_sides` en sí NO necesita
  cambios (ya es genérica, acepta cualquier polígono) -- solo hay que
  cambiar QUÉ polígono se le pasa (el contorno real de lo construido,
  no la parcela completa).
- **`vacio_rings` del visor**: probablemente necesite admitir huecos
  DENTRO de un polígono (`Polygon.interiors` de shapely), no solo
  piezas separadas (`MultiPolygon`) como hoy -- un patio interior
  rodeado por todos lados es un hueco, no una pieza aparte.
- **`footprint.py`**: reescritura completa, ya establecido en la Fase 1.
- **Modo espejo + vacío**: limitación ya conocida y documentada,
  sigue pendiente igual, no la agrava ni la resuelve esta migración.

## Fase 4 -- implementación real, en curso

A diferencia de las Fases 0-3 (prototipo aislado en `docs/referencia/`),
esto SÍ es código de producción real, con tests reales, en
`src/housing_generator/infrastructure/algorithms/layout_generation/`
-- en paralelo al sistema actual (`partition_tree.py`), no en
sustitución todavía.

### `btree_partition.py` -- estructura y movimientos

- `BStarNode`, `build_random_tree`, `compute_positions` -- migrados
  del prototipo aislado a código de producción real, mismos
  resultados verificados de nuevo con tests reales (incluido el caso
  exacto verificado a mano).
- Los 5 movimientos: `swap_modules`, `move_module` (el nuevo, el más
  valioso), `resize_module`, `reset_aspect_ratio`, `swap_children`.
- `random_neighbor`: despachador con bloqueo progresivo por
  comprobación real (recalcula posiciones antes/después, rechaza si
  una estancia bloqueada se desplazó como efecto colateral) --
  confirmado con test que reproduce el mismo escenario verificado en
  el prototipo.
- **19 tests nuevos**, incluida la propiedad general "nunca se pierde
  ni duplica una estancia" probada contra 30-100 semillas distintas.

### `btree_layout_generator.py` -- generador completo, funcionando de extremo a extremo

`btree_layout_generator.py`: `BTreeLayoutGenerator`, pieza
intercambiable vía `LayoutGeneratorPort`, mismo bucle de recocido y
misma función objetivo (comparación léxica duro/blando) que
`SimulatedAnnealingLayoutGenerator` -- lo que cambia es la
representación geométrica.

Piezas nuevas resueltas en esta parte:
- **Anclaje**: la huella ya no se decide de antemano (a diferencia del
  árbol de partición) -- se calcula primero el empaquetado (parte
  siempre de (0,0)), y se ancla después al lado de entrada de la
  parcela, mismo patrón que `footprint.footprint_rectangle` mendo
  aplicado post-hoc por traslación, no por construcción.
- **Vacío**: una sola resta geométrica (`buildable - union(estancias)`)
  cubre exterior E interior a la vez -- a diferencia del árbol de
  partición, que solo puede tener vacío exterior (huella siempre
  maciza).
- **`_polygon_to_rings` extendido**: ahora incluye también los anillos
  interiores (`polygon.interiors`) de cada polígono, no solo el
  exterior -- necesario para que un patio rodeado por todos lados (un
  hueco DENTRO de la silueta, no una pieza separada) se renderice
  correctamente. El de `SimulatedAnnealingLayoutGenerator` no lo
  necesitaba, porque su huella nunca tiene agujeros.

### Verificado de extremo a extremo, con validadores reales del proyecto

Programa mínimo real (6 estancias), parcela real, validadores reales
(`build_per_floor_validators` + `ViviendaMinimaValidator`, los mismos
que usa el sistema actual) -- generación exitosa: **0 solapes** (área
de la unión = suma exacta), **0 violaciones** de los validadores
reales, y confirmado que la silueta resultante **NO es un rectángulo
simple** (19 vértices en el contorno, un rectángulo tiene 4).

4 tests de integración nuevos (`tests/integration/test_btree_layout_generator.py`):
sin solapes, respeta todas las restricciones duras reales, calcula el
vacío correctamente, y es determinista dado un seed fijo (verificado
explícitamente, tras la investigación de la sesión anterior sobre
determinismo).

### Hallazgo real: la fitness function de código muerto

`BTreeLayoutGenerator` no está conectado a `container.py` todavía (a
propósito, en paralelo al sistema actual) -- `vulture` lo marcó
correctamente como "sin usar" dentro de `src/` (sus tests viven en
`tests/integration/`, fuera del alcance que escanea la fitness
function). Añadido a `vulture_whitelist.py`, mismo patrón ya
establecido para `GraphBasedLayoutGenerator` (otra arquitectura
alternativa deliberada, no conectada, con tests propios).

Suite completa: 401 unitarios + 4 integración nuevos, mypy y pyflakes
limpios en 85 archivos. Bundle Pyodide regenerado.

## Pendiente (fases futuras)

- Comparación empírica sistemática con los escenarios ya conocidos
  (9-11 estancias) -- ¿converge mejor que el árbol de partición para
  los casos difíciles? Es la pregunta que de verdad justifica (o no)
  esta migración.
- Wiring real en `container.py` como opción activable (p.ej.
  `--experimental-btree` en el CLI), no solo código de producción sin
  conectar.
- Decisión de corte: sustituir, convivir como opción, o descartar,
  según los resultados de la comparación empírica.

## Fase 5 -- comparación empírica: resultado real y decisivo

A petición del usuario, tras no conseguir reproducir un escenario
genuinamente difícil para el sistema actual con reconstrucciones
manuales (probado hasta 16 estancias con 2% de margen -- todas
convergieron, confirma que el bloqueo progresivo y el resto de
arreglos de esta sesión hicieron el sistema mucho más robusto de lo
que era). Se decidió probar con el **CLI real** (subprocess), no una
reconstrucción, contra el escenario `xfail` conocido y ya documentado
(`test_cli_lot_size_option_changes_the_actual_parcel_dimensions`,
parcela 12x11 muy ajustada).

Conectado `BTreeLayoutGenerator` como opción real y seleccionable
(`--experimental-btree` en el CLI, parámetro en
`build_generate_building_use_case`) -- no solo código de producción
sin conectar, ahora es una alternativa activable de verdad.

### Resultado

Mismo comando exacto, mismo escenario, mismos parámetros:

- **Sistema actual**: falla tras 15 semillas (0 lados de contacto
  exterior para `entrance_hall`).
- **`--experimental-btree`**: **converge en la semilla 4, tras 4
  intentos.**

Verificado con rigor (no solo "el CLI dijo que sí"): 0 solapes entre
estancias (área de la unión = suma exacta), todas las estancias
dentro de la parcela real (con tolerancia de 5cm para ruido de punto
flotante de las raíces cuadradas del cálculo de proporción).

Nuevo test de integración
(`test_experimental_btree_cli_flag_solves_the_known_xfail_scenario`)
que protege este hallazgo permanentemente -- ejecuta el CLI real, no
una reconstrucción.

### Limpieza tras conectar de verdad

`BTreeLayoutGenerator` ya no necesita estar en
`vulture_whitelist.py` -- confirmado que `vulture` ya no lo marca
como código muerto, ahora que se usa de verdad desde
`container.py`. Entrada eliminada, whitelist se mantiene exacto.

Suite completa: 401 unitarios + 6 integración (test_btree_partition +
test_btree_layout_generator), mypy y pyflakes limpios en 85 archivos.
Bundle Pyodide regenerado.

## Conclusión de la migración, por ahora

La pregunta que motivó las 5 fases ("¿converge mejor el árbol B* que
el sistema actual en los casos difíciles?") tiene una respuesta real
y positiva, en al menos un caso concreto y verificado -- no una
promesa teórica. Queda como trabajo futuro: repetir esta comparación
en más escenarios difíciles (no solo el que ya teníamos documentado
como `xfail`), y decidir si esto justifica ampliar el flag
experimental a más casos de uso, o mantenerlo como opción avanzada.

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

## Pendiente (fases futuras)

- **Fase 2** (en curso): traducir los 5 movimientos actuales
  (`swap_leaves`, `flip_direction`, `swap_children`, `slide_wall`,
  `reset_ratio`) a sus equivalentes B\*-tree, más el movimiento nuevo
  que no tenemos hoy (mover una estancia a cualquier punto del
  árbol).
- Fase 3: auditoría de validadores y visor.
- Fase 4: implementación incremental, en paralelo al sistema actual,
  no en sustitución directa.
- Fase 5: comparación empírica con nuestros escenarios ya conocidos,
  decisión de corte.

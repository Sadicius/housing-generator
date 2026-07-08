# Catálogo de relaciones espaciales entre tipos de estancia

Este documento recoge el "breeding" de relaciones entre los 16 `RoomType`
del sistema (120 pares únicos), construido par a par de forma manual,
con el motivo de cada relación documentado. Es un catálogo **cualitativo
de intención de diseño**, no todavía una estructura de datos ejecutable
del dominio — se consolida aquí primero para poder decidir con calma
cómo formalizarlo (ver "Próximos pasos" al final).

## Terminología (importante, no confundir)

**Reclasificado tras auditoría** (antes había 7 etiquetas: Obligatorio
cerca/lejos, Preferencia muy cerca/cerca/alejar, Neutro, Condicional —
se detectó que "muy cerca" y "cerca" no tenían una distinción operativa
real, y que "Condicional" no es un valor estático de tabla sino una
regla evaluada en tiempo real. Los matices que llevaban esas etiquetas
("con barrera", "filtrada", "limitada por ruido"...) no se han perdido:
siguen en la columna "motivo" de cada par).

- **Obligatorio cerca / Obligatorio lejos** → mapean directamente a
  `AdjacencyStrength.MUST_BE_NEAR` / `MUST_BE_AWAY`. Validador real hoy:
  `AdjacencyConstraintValidator`. Métrica **geométrica precisa**, no
  saltos de grafo: `MUST_BE_NEAR` exige un borde compartido de al menos
  1.0m (ancho de puerta); `MUST_BE_AWAY` exige que no se toquen
  (tolerancia 0.05m). Se decidió deliberadamente NO unificar esta
  métrica con la de las preferencias blandas (ver más abajo) para no
  perder la precisión de "ancho de puerta" en una regla ya probada y
  estable.
- **Preferencia (cerca) / Preferencia (alejar)** → término elegido
  deliberadamente distinto de `AdjacencyStrength.SHOULD_BE_NEAR` para no
  sugerir que ya tiene efecto. **Hoy no influye en el generador en
  absoluto** — pendiente de conectarse a la función objetivo del
  recocido simulado, en un paso aparte ya decidido. Diseño ya acordado
  para cuando se conecte (métrica: saltos en el grafo de adyacencia,
  igual que ya usan núcleo húmedo y zonificación -- no una métrica
  nueva):
  - `Preferencia (cerca)` → distancia de grafo objetivo ≤ 2 (mismo
    umbral que ya usa y valida `GroupingConstraintValidator` para
    agrupación de zona).
  - `Preferencia (alejar)` → distancia de grafo objetivo ≥ 3
    (deliberadamente más exigente que el mínimo de `Obligatorio lejos`,
    que solo pide "no tocarse" -- esto es una preferencia de separar
    más, no un mínimo legal).
- **Condicional** → **ya NO es un valor de este catálogo** (2 pares que
  antes lo llevaban -- `BEDROOM`/`MASTER_BEDROOM` × `BATHROOM` -- ahora
  usan la etiqueta `Condicional` como marcador de "ver regla aparte",
  no como valor autocontenido). La única regla condicional real
  identificada hasta ahora: **acceso de baño según nº de baños de la
  vivienda** -- si hay 1 solo baño, no puede quedar "capturado" dentro
  de un dormitorio (acceso solo vía pasillo/circulación general); si
  hay 2 o más, uno puede ser en-suite de un dormitorio (típicamente el
  principal). No se puede expresar como `(TipoA, TipoB) → valor`
  porque depende de cuántos `BATHROOM` tenga *ese* `Program` en
  concreto -- necesita lógica evaluada contra el programa real, no una
  entrada de tabla estática. Sin implementar todavía.
- **Neutro** → no hay relación relevante que capturar entre ese par. No
  es una categoría con peso ni efecto en código -- es, literalmente, la
  ausencia de entrada. Se mantiene documentado en la tabla solo para
  que se vea que el par fue considerado y no simplemente olvidado.
- **Ya cubierto (núcleo húmedo)** → 1 caso (`KITCHEN`-`BATHROOM`): hay
  relación real de cercanía, pero ya la exige el validador de núcleo
  húmedo (ambas son `is_wet`); no necesita entrada propia en este
  catálogo para no duplicar la misma exigencia por dos caminos distintos.

## Catálogo completo (120 pares)

### LIVING_ROOM
| Con | Relación | Motivo |
|---|---|---|
| DINING_ROOM | Obligatorio cerca | Conjunto funcional estar-comedor |
| KITCHEN | Preferencia (cerca) | Posible cocina abierta al salón |
| BEDROOM | Preferencia (alejar) | Amortiguador acústico social/descanso |
| MASTER_BEDROOM | Preferencia (alejar) | Mismo motivo que BEDROOM |
| BATHROOM | Preferencia (alejar) | Normativo de acceso (no directo sin distribuidor) |
| TOILET | Preferencia (cerca) | Aseo de cortesía para visitas |
| ENTRANCE_HALL | Obligatorio cerca | El recibidor es el distribuidor principal |
| STUDY | Preferencia (cerca) | Condicional según modelo de vida (teletrabajo) |
| LAUNDRY | Preferencia (alejar) | Ruido/visual de zona de servicio |
| DRYING_AREA | Preferencia (alejar) | Mismo motivo que LAUNDRY |
| STORAGE | Preferencia (cerca) | "Tejido conectivo" del salón |
| STORAGE_ROOM | Preferencia (alejar) | Trastos exiliados a zona menos noble |
| GARAGE | Obligatorio lejos | Zona sucia/de riesgo, sin relación social |
| TECHNICAL_ROOM | Preferencia (alejar) | Ruido de maquinaria |
| CORRIDOR | Preferencia (cerca) | Destino natural de circulación |

### DINING_ROOM
| Con | Relación | Motivo |
|---|---|---|
| KITCHEN | Obligatorio cerca | Servicio directo de comida |
| BEDROOM | Preferencia (alejar) | Amortiguador acústico |
| MASTER_BEDROOM | Preferencia (alejar) | Mismo motivo |
| BATHROOM | Preferencia (alejar) | Normativo de acceso |
| TOILET | Preferencia (cerca) | Con matiz: evitar visión directa desde la mesa |
| ENTRANCE_HALL | Neutro | No es destino directo del recibidor |
| STUDY | Neutro | Usos independientes |
| LAUNDRY | Preferencia (alejar) | Ruido/humedad |
| DRYING_AREA | Preferencia (alejar) | Mismo motivo |
| STORAGE | Preferencia (cerca) | Vajilla, mantelería |
| STORAGE_ROOM | Preferencia (alejar) | Exilio a zona menos noble |
| GARAGE | Preferencia (alejar) | Menos estricto que LIVING_ROOM (no obligatorio) |
| TECHNICAL_ROOM | Preferencia (alejar) | Ruido |
| CORRIDOR | Preferencia (cerca) | Circulación |

### KITCHEN
| Con | Relación | Motivo |
|---|---|---|
| BEDROOM | Preferencia (alejar) | Olores/ruido/horarios |
| MASTER_BEDROOM | Preferencia (alejar) | Mismo motivo |
| BATHROOM | Ya cubierto (núcleo húmedo) | Higiene: evitar puerta directa sobre zona de preparación |
| TOILET | Neutro | Ya cubierto por núcleo húmedo, sin matiz adicional |
| ENTRANCE_HALL | Preferencia (cerca) | Logística de compras/residuos, con transición visual filtrada |
| STUDY | Neutro | Sin relación funcional |
| LAUNDRY | Preferencia (cerca) | Coincide con núcleo húmedo; nunca separadas por zona seca, pero con puerta |
| DRYING_AREA | Preferencia (cerca) | Mismo motivo que LAUNDRY |
| STORAGE | Preferencia (cerca) | Despensa, extensión funcional directa |
| STORAGE_ROOM | Preferencia (alejar) | Sin vínculo funcional, exilio |
| GARAGE | Preferencia (cerca) | Logística de cargas; exige "mudroom" intermedio por seguridad/salubridad |
| TECHNICAL_ROOM | Preferencia (cerca) | Instalaciones compartidas |
| CORRIDOR | Preferencia (cerca) | El pasillo debe *llevar a* la cocina, no atravesarla |

### BEDROOM
| Con | Relación | Motivo |
|---|---|---|
| MASTER_BEDROOM | Neutro | Agrupación ya cubierta por zonificación noche |
| BATHROOM | Condicional | 1 baño → acceso solo vía pasillo; ≥2 baños → uno puede ser en-suite |
| TOILET | Neutro | Sin vínculo con descanso nocturno |
| ENTRANCE_HALL | Preferencia (alejar) | Privacidad de acceso (no acústica) |
| STUDY | Preferencia (cerca) | Según modelo de vida |
| LAUNDRY | Preferencia (cerca) | Circulación de ropa sucia, pero sin pegarse por ruido |
| DRYING_AREA | Preferencia (cerca) | Mismo motivo |
| STORAGE | Preferencia (cerca) | Ropa de cama/mantas (distinto del armario propio ya cubierto) |
| STORAGE_ROOM | Preferencia (alejar) | Exilio |
| GARAGE | Preferencia (alejar) | Ruido de motor/portón |
| TECHNICAL_ROOM | Preferencia (alejar) | Ruido de maquinaria |
| CORRIDOR | Preferencia (cerca) | Acceso natural |

### MASTER_BEDROOM
Idéntico a `BEDROOM` en todos los pares restantes (confirmado como
variante del mismo tipo): BATHROOM (condicional), TOILET (Neutro),
ENTRANCE_HALL (alejar), STUDY (cerca débil), LAUNDRY (cerca, limitada),
DRYING_AREA (cerca, limitada), STORAGE (cerca), STORAGE_ROOM (alejar),
GARAGE (alejar), TECHNICAL_ROOM (alejar), CORRIDOR (cerca).

### BATHROOM
| Con | Relación | Motivo |
|---|---|---|
| TOILET | Neutro | Agrupación ya cubierta por núcleo húmedo |
| ENTRANCE_HALL | Preferencia (alejar) | Privacidad/higiene, acceso vía distribuidor |
| STUDY | Neutro | Sin relación |
| LAUNDRY | Preferencia (cerca) | Coincide con núcleo húmedo + barrera acústica/olfativa |
| DRYING_AREA | Preferencia (cerca) | Mismo motivo |
| STORAGE | Preferencia (cerca) | Toallas/productos de higiene |
| STORAGE_ROOM | Preferencia (alejar) | Exilio |
| GARAGE | Preferencia (alejar) | Zona sucia vs. aseo personal |
| TECHNICAL_ROOM | Neutro | Sin necesidad real de cercanía |
| CORRIDOR | Preferencia (cerca) | Acceso natural |

### TOILET
| Con | Relación | Motivo |
|---|---|---|
| ENTRANCE_HALL | Preferencia (cerca) | Cortesía para visitas, acceso vía distribuidor |
| STUDY | Neutro | Sin relación |
| LAUNDRY | Neutro | Ya cubierto por núcleo húmedo |
| DRYING_AREA | Neutro | Ya cubierto por núcleo húmedo |
| STORAGE | Neutro | Vínculo débil |
| STORAGE_ROOM | Preferencia (alejar) | Exilio |
| GARAGE | Neutro | Sin caso de uso claro |
| TECHNICAL_ROOM | Neutro | Sin relación |
| CORRIDOR | Preferencia (cerca) | Acceso natural, obligatorio si es el único baño |

### ENTRANCE_HALL
| Con | Relación | Motivo |
|---|---|---|
| STUDY | Neutro | Condicional según modelo de vida |
| LAUNDRY | Preferencia (alejar) | Mala imagen de zona de servicio cerca del acceso de visitas |
| DRYING_AREA | Preferencia (alejar) | Mismo motivo, ropa tendida a la vista |
| STORAGE | Preferencia (cerca) | Armario de abrigos/zapatos/paraguas |
| STORAGE_ROOM | Preferencia (alejar) | Exilio |
| GARAGE | Neutro | Depende del tipo de acceso |
| TECHNICAL_ROOM | Neutro | Sin relación |
| CORRIDOR | Neutro | Sin relación adicional destacable |

### STUDY
| Con | Relación | Motivo |
|---|---|---|
| LAUNDRY | Preferencia (alejar) | Ruido interfiere con concentración |
| DRYING_AREA | Preferencia (alejar) | Mismo motivo |
| STORAGE | Preferencia (cerca) | Archivadores/material de oficina |
| STORAGE_ROOM | Preferencia (alejar) | Exilio |
| GARAGE | Preferencia (alejar) | Ruido de motor/portón |
| TECHNICAL_ROOM | Preferencia (alejar) | Ruido de maquinaria |
| CORRIDOR | Preferencia (cerca) | Acceso natural |

### LAUNDRY
| Con | Relación | Motivo |
|---|---|---|
| DRYING_AREA | Obligatorio cerca | Misma actividad funcional (lavar → tender) |
| STORAGE | Neutro | — |
| STORAGE_ROOM | Neutro | — |
| GARAGE | Neutro | — |
| TECHNICAL_ROOM | Neutro | — |
| CORRIDOR | Preferencia (cerca) | Acceso natural |

### DRYING_AREA
Idéntico a `LAUNDRY` en todos los pares restantes: STORAGE (Neutro),
STORAGE_ROOM (Neutro), GARAGE (Neutro), TECHNICAL_ROOM (Neutro),
CORRIDOR (Preferencia cerca).

### STORAGE
| Con | Relación | Motivo |
|---|---|---|
| STORAGE_ROOM | Neutro | Sirven a zonas distintas |
| GARAGE | Neutro | Sin vínculo |
| TECHNICAL_ROOM | Neutro | Sin vínculo |
| CORRIDOR | Preferencia (cerca) | Distribuidor natural hacia todas las estancias a las que sirve |

### STORAGE_ROOM
| Con | Relación | Motivo |
|---|---|---|
| GARAGE | Preferencia (cerca) | Agrupación natural en zona de servicio |
| TECHNICAL_ROOM | Neutro | — |
| CORRIDOR | Preferencia (cerca) | Necesita acceso, aunque discreto |

### GARAGE
| Con | Relación | Motivo |
|---|---|---|
| TECHNICAL_ROOM | Neutro | — |
| CORRIDOR | Neutro | — |

### TECHNICAL_ROOM
| Con | Relación | Motivo |
|---|---|---|
| CORRIDOR | Neutro | — |

## Huecos de modelo identificados (no resueltos, registrados para más adelante)

1. **Acceso/puertas**: no se modelan puertas ni accesos, solo geometría
   de paredes compartidas. Varias relaciones de este catálogo distinguen
   "cerca" de "cerca pero sin puerta directa" (BATHROOM con zonas
   sociales, KITCHEN↔GARAGE, ENTRANCE_HALL↔BATHROOM...) — hoy no se
   puede expresar esa distinción.
2. **Topología de circulación (de paso vs. terminal)**: KITCHEN↔CORRIDOR
   señaló que el pasillo debe *llevar a* la cocina, no *atravesarla*. No
   existe ningún concepto de "estancia de paso" vs. "estancia terminal"
   en el grafo de circulación.
3. **Reglas condicionadas por cardinalidad total**: BEDROOM↔BATHROOM (y
   MASTER_BEDROOM↔BATHROOM) dependen de cuántos baños completos existan
   en total en el programa (1 baño → acceso solo por pasillo; ≥2 →
   uno puede ser en-suite). No es una propiedad fija del par, sino del
   programa completo.

## Candidato a nuevo `RoomType` (no añadido)

- **"Mudroom" / cuarto de paso**: espacio de transición entre garaje y
  cocina (descarga de compras, gestión de calzado/abrigos, filtro de
  suciedad). Mencionado repetidamente en KITCHEN↔GARAGE. No se ha
  añadido como tipo porque requeriría revisar de nuevo varias filas del
  catálogo si se incorpora.

## Próximos pasos (para decidir en otra sesión)

- Formalizar (o no) este catálogo como estructura de datos del dominio,
  por ejemplo `DEFAULT_TYPE_ADJACENCY: Dict[Tuple[RoomType, RoomType], ...]`,
  generando `AdjacencyRequirement` sugeridos automáticamente para un
  `Program` según los tipos que contenga.
- **[DISEÑO DECIDIDO, sin conectar todavía]** Mecanismo de restricciones
  blandas ("Preferencia cerca/alejar") en la función objetivo del
  recocido simulado -- hoy el generador solo minimiza violaciones
  duras. Métrica y umbrales ya acordados (ver "Terminología" arriba:
  saltos de grafo, cerca ≤2, alejar ≥3); falta la implementación en sí
  (penalización ponderada sumada a la puntuación de violaciones duras,
  siempre subordinada a estas). Deliberadamente separado como paso
  aparte de la reclasificación del catálogo.
- Implementar la regla `Condicional` (acceso de baño según nº de baños)
  como lógica evaluada contra el `Program`, no como entrada de catálogo.
- Resolver los tres huecos de modelo antes de formalizar del todo,
  para no heredar una estructura de datos que no pueda expresarlos.
- **Paso intermedio ya disponible**: el "grafo de burbujas" del
  dashboard (`docs/visualizador/relaciones_espaciales.html`) permite
  explorar arreglos concretos por planta y exportar un JSON de
  `AdjacencyRequirement` a partir de qué burbujas quedaron tocándose --
  no sustituye la formalización en código, pero da un punto de partida
  revisable manualmente en vez de escribir el `Program` a mano desde
  cero.

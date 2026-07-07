# Catálogo de relaciones espaciales entre tipos de estancia

Este documento recoge el "breeding" de relaciones entre los 16 `RoomType`
del sistema (120 pares únicos), construido par a par de forma manual,
con el motivo de cada relación documentado. Es un catálogo **cualitativo
de intención de diseño**, no todavía una estructura de datos ejecutable
del dominio — se consolida aquí primero para poder decidir con calma
cómo formalizarlo (ver "Próximos pasos" al final).

## Terminología (importante, no confundir)

- **Obligatorio cerca / Obligatorio lejos** → mapean directamente a
  `AdjacencyStrength.MUST_BE_NEAR` / `MUST_BE_AWAY`. Tienen validador
  real hoy: `AdjacencyConstraintValidator` (`MUST_BE_NEAR` exige un borde
  compartido de al menos 1.0m, para que quepa una puerta; `MUST_BE_AWAY`
  exige que no se toquen).
- **Preferencia de diseño (cerca / muy cerca / alejar)** → término
  elegido deliberadamente distinto de `AdjacencyStrength.SHOULD_BE_NEAR`
  para no sugerir que ya tiene efecto. **Hoy no influye en el generador
  en absoluto** — es documentación de intención, pendiente de que se
  implemente algún mecanismo de restricciones blandas (penalización en
  la función objetivo del recocido simulado, no violación dura).
- **Neutro** → no hay relación relevante que capturar entre ese par.

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
| STUDY | Preferencia (cerca), débil | Condicional según modelo de vida (teletrabajo) |
| LAUNDRY | Preferencia (alejar) | Ruido/visual de zona de servicio |
| DRYING_AREA | Preferencia (alejar) | Mismo motivo que LAUNDRY |
| STORAGE | Preferencia (muy cerca) | "Tejido conectivo" del salón |
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
| STORAGE | Preferencia (muy cerca) | Vajilla, mantelería |
| STORAGE_ROOM | Preferencia (alejar) | Exilio a zona menos noble |
| GARAGE | Preferencia (alejar) | Menos estricto que LIVING_ROOM (no obligatorio) |
| TECHNICAL_ROOM | Preferencia (alejar) | Ruido |
| CORRIDOR | Preferencia (cerca) | Circulación |

### KITCHEN
| Con | Relación | Motivo |
|---|---|---|
| BEDROOM | Preferencia (alejar) | Olores/ruido/horarios |
| MASTER_BEDROOM | Preferencia (alejar) | Mismo motivo |
| BATHROOM | *(ya exigido por núcleo húmedo)* + matiz | Higiene: evitar puerta directa sobre zona de preparación |
| TOILET | Neutro | Ya cubierto por núcleo húmedo, sin matiz adicional |
| ENTRANCE_HALL | Preferencia (muy cerca) | Logística de compras/residuos, con transición visual filtrada |
| STUDY | Neutro | Sin relación funcional |
| LAUNDRY | Preferencia (muy cerca), con barrera | Coincide con núcleo húmedo; nunca separadas por zona seca, pero con puerta |
| DRYING_AREA | Preferencia (muy cerca), con barrera | Mismo motivo que LAUNDRY |
| STORAGE | Preferencia (muy cerca) | Despensa, extensión funcional directa |
| STORAGE_ROOM | Preferencia (alejar) | Sin vínculo funcional, exilio |
| GARAGE | Preferencia (muy cerca, con barrera) | Logística de cargas; exige "mudroom" intermedio por seguridad/salubridad |
| TECHNICAL_ROOM | Preferencia (muy cerca, con barrera) | Instalaciones compartidas |
| CORRIDOR | Preferencia (cerca), filtrada | El pasillo debe *llevar a* la cocina, no atravesarla |

### BEDROOM
| Con | Relación | Motivo |
|---|---|---|
| MASTER_BEDROOM | Neutro | Agrupación ya cubierta por zonificación noche |
| BATHROOM | Condicional según nº de baños | 1 baño → acceso solo vía pasillo; ≥2 baños → uno puede ser en-suite |
| TOILET | Neutro | Sin vínculo con descanso nocturno |
| ENTRANCE_HALL | Preferencia (alejar) | Privacidad de acceso (no acústica) |
| STUDY | Preferencia (cerca), débil/condicional | Según modelo de vida |
| LAUNDRY | Preferencia (cerca), limitada por ruido | Circulación de ropa sucia, pero sin pegarse por ruido |
| DRYING_AREA | Preferencia (cerca), limitada por ruido | Mismo motivo |
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
| LAUNDRY | Preferencia (muy cerca) | Coincide con núcleo húmedo + barrera acústica/olfativa |
| DRYING_AREA | Preferencia (muy cerca) | Mismo motivo |
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
- Decidir el mecanismo de restricciones blandas ("Preferencia de
  diseño") en la función objetivo del recocido simulado -- hoy el
  generador solo minimiza violaciones duras.
- Resolver los tres huecos de modelo antes de formalizar del todo,
  para no heredar una estructura de datos que no pueda expresarlos.
- **Paso intermedio ya disponible**: el "grafo de burbujas" del
  dashboard (`docs/visualizador/relaciones_espaciales.html`) permite
  explorar arreglos concretos por planta y exportar un JSON de
  `AdjacencyRequirement` a partir de qué burbujas quedaron tocándose --
  no sustituye la formalización en código, pero da un punto de partida
  revisable manualmente en vez de escribir el `Program` a mano desde
  cero.

# Dashboard -- catálogo constructivo

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:catalogo-constructivo] Catálogo constructivo -- pestaña 07

A petición del usuario: acceso a la composición real de materiales de
fachada, forjado y huecos (ventanas). Investigado antes de construir:
encontrada fuente sólida y oficial -- **Catálogo de Elementos
Constructivos del CTE (CEC)**, codigotecnico.org, Instituto Eduardo
Torroja + CEPCO + AICIA. A diferencia del cronograma de obra (donde no
existía fuente real), aquí sí hay un documento oficial extenso con
composición por capas de decenas de sistemas constructivos.

- **Alcance confirmado explícitamente**: 10 elementos representativos
  por categoría (fachadas/forjados/huecos), no el catálogo CEC
  completo -- solo en fachadas el documento real tiene varias decenas
  de variantes por familia, digitalizarlo entero sería un proyecto
  aparte.
- **Composición por capas**: extraída de las definiciones reales del
  catálogo (códigos de capa como `LC`=fábrica de ladrillo cerámico,
  `AT`=aislante térmico, `C`=cámara de aire, `RI`=revestimiento
  interior), no inventada.
- **Valores de transmitancia U**: aquí sí hubo que tomar una decisión
  de rigor real -- las tablas del catálogo dan U en función de la
  resistencia térmica del aislante elegido (fórmula tipo
  `1/(0.58+RAT)`, no un número fijo), y extraer los números exactos de
  las tablas del PDF (con formato muy degradado al convertir a texto)
  habría sido poco fiable. En su lugar: U calculada con la fórmula
  física estándar (U=1/ΣR, con Rsi+Rse=0.17 m²K/W para fachadas) y las
  conductividades λ REALES de cada material, tomadas del mismo
  catálogo (sección 3, materiales) -- con un espesor de aislante
  concreto asumido y declarado explícitamente en cada ficha, no los
  valores de tabla exactos. Cálculo hecho con un script (no a mano)
  para que las 30 fichas sean consistentes.
- Huecos: transmitancia global aproximada como 20% marco + 80% vidrio
  (proporción típica de ventana estándar), con U de marco y vidrio
  reales del catálogo (secciones 3.16 y 3.15.2) mostrados por
  separado, no solo el global.
- Nota de alcance visible en el propio panel, con enlace al PDF
  oficial y la aclaración explícita de que los valores U son
  calculados, no transcritos directamente de la tabla.
- Implementado en `js/08-catalogo.js` (nuevo, antes de `init` --
  `08-init.js` renombrado a `09-init.js`, mismo patrón que el
  cronograma). Sin pieza Python nueva: catálogo estático embebido como
  constante JS, puro cliente.
- Verificado con `jsdom`: 10 tarjetas por categoría, expansión de
  capas al hacer clic, cambio de categoría (fachadas/forjados/huecos)
  correcto, cero errores.
- Tests de sanidad actualizados: 7 pestañas, orden de archivos JS,
  nuevo test que confirma 10 elementos por categoría.
- Suite final: 346 unitarios, pyflakes limpio.

## [ARCH:catalogo-constructivo] Actualización a materiales Passivhaus

A petición del usuario: reconsiderar fachadas y huecos del catálogo
constructivo con materiales adecuados para el estándar Passivhaus.

- **Aclaración honesta hecha antes de tocar código**: Passivhaus NO es
  el estándar legalmente obligatorio -- ese sigue siendo el CTE (el
  que fundamenta el resto del proyecto). Es el estándar VOLUNTARIO más
  exigente reconocido en eficiencia energética. Se aplicó con ese
  matiz explícito, no como sustituto del CTE en el resto del sistema.
- **Valores objetivo verificados con fuentes reales** antes de
  recalcular: muros/cubiertas U ≈ 0.10-0.15 W/m²K (frente al 0.35-0.56
  del CTE), ventanas Uw ≤ 0.80 W/m²K con triple acristalamiento y gas
  noble (argón/kriptón), marcos multicámara con rotura amplia de
  puente térmico.
- **Fachadas (10)**: recalculadas con espesores de aislante mucho
  mayores (170-300mm según sistema, antes 50-120mm) y, en varios
  casos, materiales de mayor rendimiento (PUR/PIR λ=0.025 en vez de
  EPS estándar) -- mismos sistemas constructivos de base (SATE,
  cámara ventilada, entramado de madera...) pero dimensionados para
  Passivhaus real. Las 10 quedan en el rango 0.107-0.146 W/m²K,
  verificado con un test permanente.
- **Huecos (10)**: sustituidos marco+vidrio por combinaciones reales
  certificables Passivhaus (PVC 5-6 cámaras, madera-aluminio, aluminio
  con RPT amplio certificado + triple acristalamiento bajo emisivo con
  argón/kriptón) -- se retiró la opción de vidrio simple/aluminio sin
  RPT que servía de referencia de contraste, ya no encaja con "materiales
  adecuados para Passivhaus". Las 10 quedan en el rango 0.56-0.67 W/m²K,
  bajo el umbral de 0.80, verificado con un test permanente.
- **Forjados (10): sin cambios, confirmado explícitamente con el
  usuario** -- son estructura intermedia entre plantas calefactadas de
  la misma vivienda, sin salto térmico entre ellas; el aislamiento
  Passivhaus va en muros y cubierta, no ahí. Aplicarlo a los forjados
  habría sido incorrecto técnicamente, no solo innecesario.
- Cálculo hecho con script (mismo patrón que la versión anterior), no
  a mano, para consistencia en las 20 fichas recalculadas.
- Nuevo test permanente (`test_catalogo_constructivo_meets_passivhaus_thresholds`)
  que falla si cualquier fachada sale del rango 0.08-0.16 W/m²K o
  cualquier hueco supera 0.80 W/m²K -- protege la decisión igual que
  el resto de fitness functions del proyecto.
- Suite final: 347 unitarios, pyflakes limpio.

## [ARCH:catalogo-constructivo] Ampliación a las 7 categorías completas del CEC

A petición del usuario: fachadas/forjados/huecos se habían presentado
como referencia, no como el conjunto completo -- el catálogo real
tiene más categorías. Ampliado a las 7 categorías reales del
documento oficial.

- **Cubiertas (10)**: mismo criterio Passivhaus que fachadas
  (confirmado explícitamente: son envolvente térmica también), U
  0.099-0.133 W/m²K con aislantes de gran espesor (EPS/XPS/lana
  mineral 220-240mm, o PUR 180mm en panel sándwich).
- **Particiones interiores verticales (10)** y **horizontales (10)**:
  centradas en propiedades ACÚSTICAS (índice RA, mejora de ruido de
  impacto ΔL), no térmicas -- son interiores a la vivienda, no
  envolvente, decisión coherente con la de forjados.
- **Puentes térmicos (13)**: lista real y CERRADA del catálogo CEC
  (4.6.1 a 4.6.13, no una muestra recortada a 10 como el resto,
  porque el documento original solo tiene estos 13 puntos nombrados).
  Formato de dato distinto a las demás categorías -- no es composición
  por capas con transmitancia U (W/m²K), es transmitancia térmica
  LINEAL Ψ (W/mK) de un detalle de unión constructiva. Cada uno
  compara construcción estándar (aislamiento discontinuo/interior)
  frente a Passivhaus (aislamiento continuo por el exterior, principio
  central del estándar: "construcción libre de puentes térmicos"),
  con valores Ψ de referencia real investigados (DA DB-HE/3 del CTE,
  comparativas Therm/LIDER encontradas en foros técnicos -- p.ej.
  pilar 30x30 con aislamiento interior: Ψ=0.27 W/mK medido con Therm;
  frente de forjado: 0.30-0.80 W/mK según continuidad del aislante).
- Verificado con `jsdom` en las 7 categorías: número de tarjetas
  correcto, formato de detalle correcto por categoría (capas+U,
  capas+acústica, o comparativa estándar/Passivhaus para puentes
  térmicos), expansión de tarjeta, cero errores.
- Tests de sanidad ampliados: número de elementos esperado por
  categoría (10, o 13 en puentes térmicos), y umbrales Passivhaus
  extendidos a cubiertas + verificación de que el valor Passivhaus es
  siempre menor que el estándar en los 13 puentes térmicos.
- Suite final: 347 unitarios, pyflakes limpio.

# Validadores -- anchos libres

## AnchoLibrePracticoValidator [ARCH:ancho-libre-practico]

Ancho libre mínimo de **1.20m, explícitamente NO normativo** (motivo,
valores exactos y la excepción de aseo/tendedero a 0.90m: ver docstring
de `ancho_libre_practico_validator.py`, cita su origen igual que el
resto de constantes del proyecto) para los tipos que el decreto deja
sin ancho libre especificado. `STORAGE_ROOM` (trastero) excluido, ya
tiene su propio mínimo normativo (B.2.5, 1.60m). Origen: una captura
de pantalla real del usuario con proporciones absurdas
("Almacén" 2.49m×0.49m) normativamente conformes en área pero
inservibles -- historial completo en `docs/historico/architecture.md`,
`[ARCH:ancho-libre-practico]`.

## [ARCH:ancho-libre-estancia] AnchoLibreEstanciaValidator

A.3.2.1: declarado en `nhv.lua` (NHV.anchoLibreMin) pero nunca
conectado a ningún validador en la fuente; valores confirmados de
forma independiente (Anexo I, Decreto de Galicia). Solo cubre 5
categorías (estancia mayor, dormitorios, cocina, baño) -- comedor,
despacho, aseo, lavadero, tendedero, trastero, almacenamiento no
tienen ancho libre asignado en ningún sitio de la fuente (cubiertos
en cambio por `AnchoLibrePracticoValidator`, no normativo).

La "estancia mayor" aquí es estrictamente LIVING_ROOM -- a diferencia
de `EstanciaMinimumAreaValidator`, no hace fallback a la de mayor
área (para no duplicar ese aviso).

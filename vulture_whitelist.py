# Lista blanca de vulture (detector de codigo muerto) -- elementos que
# vulture marca como "sin usar" pero que ya revisamos explicitamente y
# confirmamos como intencionados, no descuidados. Ver
# tests/unit/test_no_dead_code.py, la fitness function que ejecuta
# vulture contra esta lista en cada pase de la suite -- retomado de
# investigar "architecture-decision-record" y el concepto de fitness
# functions (Neal Ford / Rebecca Parsons) a peticion del usuario: una
# comprobacion continua es mejor que una auditoria manual ocasional
# (asi se encontro `browser_bridge.py`, un archivo completo huerfano
# que nadie habia notado hasta que se audito a mano).
#
# Regenerar tras revisar hallazgos nuevos de vulture:
#   vulture src/ --min-confidence 60 --make-whitelist
#
# Cada linea de abajo, con su razon:

# Piezas alternativas deliberadas de la arquitectura hexagonal (tienen
# tests propios que las verifican; no conectadas a container.py, pero
# no son descuido -- demuestran que el generador es intercambiable).
BuildAdjacencyGraphUseCase  # unused class (src/housing_generator/application/use_cases/build_adjacency_graph.py:5)
ValidateLayoutUseCase  # unused class (src/housing_generator/application/use_cases/validate_layout.py:6)
build_program_with_auto_adjacency  # unused function (src/housing_generator/domain/services/type_adjacency_catalog.py:138)
build_day_night_zoning_validators  # unused function (src/housing_generator/infrastructure/algorithms/constraints/day_night_zoning_validator.py:42)
GraphBasedLayoutGenerator  # unused class (src/housing_generator/infrastructure/algorithms/layout_generation/graph_based_generator.py:17)

# Metodos/propiedades de entidades de dominio, usados en tests/ (vulture
# solo escanea src/) -- API publica real, no codigo muerto.
_.level_below  # unused method (src/housing_generator/domain/entities/building.py:26)
_.total_area_m2  # unused property (src/housing_generator/domain/entities/program.py:26)
_.add_room  # unused method (src/housing_generator/domain/entities/zone.py:14)
_.involves  # unused method (src/housing_generator/domain/value_objects/adjacency.py:16)
max_aspect_ratio  # unused variable (src/housing_generator/domain/value_objects/dimensions.py:10)

# Decision de diseno deliberada: "Neutro" se representa por AUSENCIA de
# entrada en el catalogo, no asignando este valor -- el enum lo
# mantiene por completitud del modelo clasico de 5 niveles.
INDIFFERENT  # unused variable (src/housing_generator/domain/enums.py:43)

# Llamada dinamicamente desde JavaScript via Pyodide (interface/browser/
# bridge.py, invocada por nombre desde py_bundle.js) -- invisible para
# el analisis estatico de Python, pero es el puente real en uso.
generar_edificio  # unused function (src/housing_generator/interface/browser/bridge.py:17)

# Fase A de importacion de Catastro, en construccion -- puente real
# (interface/browser/bridge.py:analizar_parcela_catastro), con tests
# propios (tests/integration/test_browser_bridge.py), todavia no
# conectado al lado JS del dashboard (falta esa pieza). El parser
# subyacente (importar_parcela_gml) ya esta conectado de verdad --
# entradas antiguas eliminadas del whitelist, ya no hacen falta. Ver
# docs/CONTINUIDAD.md, entrada "Importacion de parcela real desde
# Catastro (Fase A)".
analizar_parcela_catastro  # unused function (src/housing_generator/interface/browser/bridge.py:19)

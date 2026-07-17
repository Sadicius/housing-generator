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

# Fase 1 del rediseno "periferia hacia el centro" (ver
# docs/referencia/generador/contacto-exterior-y-envolvente.md):
# geometria de tallado perimetral aislada, con tests propios
# (tests/unit/test_perimeter_carving.py), aun NO conectada al pipeline
# de generacion real -- eso es una fase posterior (Fase 2-3), con
# revision del usuario entre cada una. Mismo trato que
# GraphBasedLayoutGenerator arriba: pieza intencionada, no descuido.
carve_perimeter  # unused function (src/housing_generator/infrastructure/algorithms/layout_generation/perimeter_carving.py:97)

# Fase 2 del mismo rediseno: estado mutable + mutaciones perimetrales
# + integracion con el nucleo (btree_partition.py) + materializacion
# pura. Con tests propios (tests/unit/test_perimeter_core_partition.py),
# aun NO conectada al pipeline real -- eso es la Fase 3 (recocido
# simulado + wiring a container.py), con revision del usuario entre
# cada fase. Mismo trato que carve_perimeter arriba.
find_entrance_hall_id  # unused function (src/housing_generator/infrastructure/algorithms/layout_generation/perimeter_core_partition.py:70)
build_initial_perimeter_core_state  # unused function (src/housing_generator/infrastructure/algorithms/layout_generation/perimeter_core_partition.py:76)
random_neighbor_perimeter_core  # unused function (src/housing_generator/infrastructure/algorithms/layout_generation/perimeter_core_partition.py:207)
materialize_perimeter_core  # unused function (src/housing_generator/infrastructure/algorithms/layout_generation/perimeter_core_partition.py:255)

# Fase 3 del mismo rediseno: LayoutGeneratorPort completo (recocido
# simulado) sobre las piezas de la Fase 2. Con smoke-test propio
# (converge hard=0 en <0.3s en el escenario de prueba), aun NO
# conectada a container.py -- la sustitucion real exige antes
# confirmar contra los 5 tests xfail reales. Mismo trato que las
# piezas anteriores.
PerimeterCoreLayoutGenerator  # unused class (src/housing_generator/infrastructure/algorithms/layout_generation/perimeter_core_layout_generator.py:34)

# Fabrica PROVISIONAL (ver su propio docstring) que conecta
# PerimeterCoreLayoutGenerator -- usada solo desde
# tests/integration/test_generate_layout_use_case_v2.py (vulture solo
# escanea src/), no desde el wiring de produccion todavia.
build_generate_layout_use_case_v2  # unused function (src/housing_generator/config/container.py:191)

# Llamada dinamicamente desde JavaScript via Pyodide (interface/browser/
# bridge.py, invocada por nombre desde py_bundle.js) -- invisible para
# el analisis estatico de Python, pero es el puente real en uso.
generar_edificio  # unused function (src/housing_generator/interface/browser/bridge.py:17)
analizar_parcela_catastro  # unused function (src/housing_generator/interface/browser/bridge.py:19) -- Fase A de importacion de Catastro, mismo patron: llamada dinamicamente desde JS (00b-parcela.js) via Pyodide


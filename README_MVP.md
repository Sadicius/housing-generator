# housing-generator — MVP

Generador procedural de viviendas por zonificación día/noche/servicio, con validadores normativos reales (Decreto 29/2010 y Ley 2/2016 de Galicia). Este documento describe el **camino mínimo fiable** para probarlo — no la herramienta completa (dashboard con 4 zonas, catálogo constructivo, cronograma, etc. — ver `docs/GUIA_USO.md` para eso).

## Requisitos exactos

- **Python 3.10 o superior** (comprobado con 3.12). Sin Node/npm — la parte JS (dashboard) corre en el navegador con `<script>` clásicos, sin build ni instalación.
- Dependencias: `shapely`, `networkx` (se instalan solas, ver abajo).

## Instalación

```bash
# Linux/macOS
bash instalar.sh

# Windows
instalar.bat
```

Crea un `.venv/` e instala las dependencias. Idempotente (se puede volver a ejecutar).

## Comando único — planta única (el camino fiable hoy)

```bash
python -m housing_generator.interface.cli.main --output layout.json
```

Genera una vivienda de 6 estancias (salón, cocina, baño, recibidor, lavadero, tendedero, almacén) en una parcela de ejemplo de 14×16m, semilla determinista (`--seed 4` por defecto — siempre el mismo resultado). Termina en unos segundos e imprime las estancias colocadas:

```
Layout generado y guardado en layout.json

  - Estar                  zona=day      bounds=(8.2, 0.0, 13.4, 4.8)
  - Cocina                 zona=day      bounds=(4.5, 0.0, 8.2, 3.3)
  - Bano                   zona=night    bounds=(3.9, 3.3, 6.4, 5.7)
  - Lavadero               zona=service  bounds=(2.1, 0.0, 4.5, 2.5)
  - Tendedero              zona=service  bounds=(0.6, 0.0, 2.1, 1.3)
  - Almacen                zona=service  bounds=(2.1, 2.5, 3.9, 4.8)
```

### Salida esperada (`layout.json`)

Esquema JSON fijo (el mismo que consume el dashboard, `JsonLayoutRepository.to_dict`):

```json
{
  "rooms": [
    {"id": "living", "name": "Estar", "type": "living_room", "zone": "day", "area_m2": 25, "bounds": [8.17, 0.0, 13.41, 4.77]}
  ],
  "doors": [{"room_a": "living", "room_b": "entrance"}],
  "metadata": {"hard_violations": 0, "soft_penalty": 0.0, "vacio_shapes": [...]}
}
```

`bounds` es `[minx, miny, maxx, maxy]` en metros. `metadata.hard_violations == 0` confirma que el layout cumple todos los validadores normativos activos.

## Parcela real / programa propio

```bash
python -m housing_generator.interface.cli.main \
  --import-seleccion mi_seleccion.json --lot-size 12x18 --output layout.json
```

`mi_seleccion.json` es la exportación del panel del dashboard ("Generar selección"). Reintenta hasta 20 semillas automáticamente si la primera no converge (`--retry-seeds`).

## Dashboard (sin instalar nada)

Doble clic en `html/relaciones_espaciales.html` — se abre en el navegador, sin servidor. Ejecuta el generador real vía Pyodide (Python compilado a WebAssembly), en un Web Worker (no bloquea la pestaña mientras busca). Ver `docs/GUIA_USO.md`.

## Modo seguro

- La búsqueda está siempre acotada (`--max-iterations`, nunca un bucle infinito).
- Un fallo de generación siempre termina con un mensaje claro (`No se pudo generar tras probar N semillas...`, código de salida ≠ 0) y **nunca** escribe un archivo de salida corrupto o a medias.
- `bridge.py` (el puente que usa el dashboard) siempre devuelve `{"ok": false, "error": "..."}` en vez de colgarse o lanzar una excepción sin capturar.

Verificado con `tests/integration/test_mvp.py` (smoke test de este README, no una demostración manual perdida).

## ⚠️ Limitación conocida: vivienda multi-planta

La generación de **una sola planta** (el comando de arriba) es fiable — verificada de extremo a extremo, con datos reales, no solo tests sintéticos.

La generación **multi-planta** (`--import-seleccion` con estancias en varios niveles, escalera compartida) **no es fiable al 100% todavía**: medido con datos reales, la probabilidad de que una semilla concreta converja ronda el 10-20% en escenarios típicos (vivienda unifamiliar de 2 plantas). El reintento automático de semillas (subido a 20 por defecto tras esta medición) baja la probabilidad de fallo total a ~1-12% — mejor, pero no garantizado. Causa raíz identificada y documentada (`docs/CONTINUIDAD.md`, sección "Pendiente real"): el generador empaqueta las estancias sin un incentivo que las empuje hacia el perímetro del solar, así que ocasionalmente alguna queda sin contacto con el exterior. Arreglarlo de raíz es una decisión de arquitectura pendiente, no un ajuste de parámetros.

**Recomendación práctica mientras tanto**: incluye siempre un distribuidor/pasillo (`CORRIDOR`) en cualquier planta con más de una pieza privada (dormitorio/baño) — confirmado que mejora sustancialmente la tasa de convergencia. Si una generación multi-planta falla tras 20 reintentos, prueba con `--seed` distinto o revisa que el programa tenga circulación suficiente.

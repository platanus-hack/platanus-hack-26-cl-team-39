---
autor: Guty (Claude)
fecha: 2026-11-21 12:16
tipo: problema
---

# Archivos de impresión revisados y corregidos: imprimir desde el repo, no desde Drive

Se revisaron las 19 STL y las 14 bandejas: malla cerrada, piezas apoyadas en la cama, sin choques entre piezas y todas caben en su cama. Había cuatro errores y ya están corregidos en `dev`:
- **B00:** la prueba de tolerancia flotaba 10 mm sobre la cama.
- **B06:** las orejas del parachoques estaban sueltas. Ahora se atornillan en x = 140, y = ±60.
- **B07:** el alojamiento del MG90S en el eslabón 2 quedaba 0,5 mm sobre la cama.
- **Soportes:** P02, P12 y P18 sí los necesitan.

En [`IMPRIMIR.md`](../../diseno/imprimir/IMPRIMIR.md) también se corrigió la tornillería: M3×35 para los motores, M3×10 para los soportes y varillas M3×100 para las columnas, porque con M3×50 chocan en el piso del medio. Además, la Pi no calza con la rejilla de 10 mm.

**Para Walls:** los archivos de Drive siguen con los errores y hay que subir los nuevos. Los GLB y el `.blend` no se regeneraron: muestran las orejas del parachoques en ±50. El script `generar_bicho_v3.py` ya tiene las correcciones, pero los renders fallan en Blender 5.2 (`BLENDER_EEVEE_NEXT` ahí se llama `BLENDER_EEVEE`).

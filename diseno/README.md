# diseno/: el cuerpo del bicho

Aquí está el diseño mecánico del bicho:

- la estructura impresa de 32 × 20 cm;
- las 3 distribuciones de piezas;
- los archivos listos para la impresora 3D;
- el taller 3D interactivo donde se mueven las piezas.

Todo sale de un script de Blender: si cambia una medida, se regenera todo.

## Para imprimir

**Drive (STL, bandejas .3mf, .blend y guía):** https://drive.google.com/drive/folders/1a9WasSzIEE1wSZMqfCm-AzRK_FrVOw_S

Están las mismas cosas en [`imprimir/`](imprimir/). La guía completa está en [`imprimir/IMPRIMIR.md`](imprimir/IMPRIMIR.md) y cubre:

- los perfiles del slicer;
- el orden de impresión;
- los tiempos;
- la tornillería;
- el armado.

Resumen:

- Son **19 piezas**, todas revisadas: malla cerrada y sin aristas raras.
- Hay **14 bandejas .3mf**: se abren en Bambu Studio, Orca o PrusaSlicer y se imprimen.
- **Las 3 placas de 320 × 200 mm son de una sola pieza** y necesitan una cama de 330 × 210 mm o más (Bambu H2D, Prusa XL, Creality K2 Plus, Neptune 4 Max, Kobra 3 Max, Ender 5 Plus). El resto cabe en una cama de 220 × 220.
- Imprimir primero **B00**, la prueba de tolerancia de 20 min, antes de las placas de 10 h.
- Un robot V1 completo toma unas 45 h en una impresora clásica o 21 h en una rápida, y gasta unos 0,87 kg de PLA, 180 g de PETG y 40 g de TPU.
- Si la impresora tiene cama chica, hay una versión con las placas en dos mitades en Drive, en la carpeta «v3.1».

## La estructura

- Las **placas son iguales en los 3 pisos**: 320 × 200 × 4 mm, con nervios de 6 mm por debajo y rejilla de agujeros M3 cada 10 mm. Cualquier pieza se atornilla donde se quiera.
- Los pisos van a 45, 89 y 133 mm del suelo, separados por columnas de 40 mm.
- **Piso 1 (potencia):** 8 celdas 18650 en dos portapilas de 4, el fusible y el interruptor.
- **Piso 2 (cerebro y control):** la Pi 3B junto al centro, para que el cable de la cámara de 1 m llegue al brazo, más PCA9685 ×2, TB6612 ×2, LM2596, ADS1115 y MPU-6050.
- **Cubierta:** el brazo de 5 servos al centro, sobre un pedestal de 46 mm, más la UPS, el parlante y las ESP32-CAM.
- **Abajo:** 4 motores TT en cunas impresas y 2 sensores de flujo ADNS-3080 separados 200 mm. La diferencia entre los dos da cuánto giró el robot.

## Las 3 distribuciones

| | Qué cambia |
|---|---|
| **V1 · Brazo-cuello** | Sin torre. La cara (cámara Pi + anillo de 24 LED) y el LiDAR van en la muñeca: el brazo es el cuello. |
| **V2 · Brazo + torre** | El LiDAR va en la muñeca. Una torre trasera lleva la cara fija, el parlante y la cámara de retroceso. |
| **V3 · Barredor bajo** | Un MG90S hace barrer al LiDAR en la proa. La cara va al frente y el brazo solo agarra. |

El LiDAR 2D es fijo, no gira, así que lo hace barrer el brazo o un servo.

## Carpetas

| Carpeta | Qué hay |
|---|---|
| `imprimir/` | `STL/`, `3MF_bandejas/`, `IMPRIMIR.md`, `impresion.json` (los datos de las bandejas) y `bicho_v3_32cm.blend` |
| `modelos/` | `bicho_V1.glb`, `bicho_V2.glb` y `bicho_V3.glb`: el robot armado, con nombres de pieza, masas y articulaciones. Ver `INTEGRAR_EN_BICHO_DEV.md`. |
| `taller3d/` | El taller interactivo: mover el brazo, arrastrar piezas, torque en vivo, choques, centro de gravedad, LiDAR y manejo. |
| `blender/` | Los scripts: `generar_bicho_v3.py` (vigente), `empaquetar_impresion.py` (arma las bandejas), `prueba_tolerancia.py` (B00), y `generar_bicho.py` y `generar_bicho_v2.py` (versiones anteriores). |
| `renders/` | Imágenes de las 3 versiones. |
| `fuentes/` | Esquemático de conexiones (PDF), escaneo 3D del chasis del 21-nov e inventarios de Carlos y Renate (TSV). |

## Cómo abrir el taller 3D

```bash
cd diseno && python3 -m http.server 8000
# abrir http://localhost:8000/taller3d/
```

## Cómo regenerar todo después de cambiar una medida

Las medidas están arriba en `blender/generar_bicho_v3.py`: `L`, `W`, `T`, `RIB`, `PITCH`, `WHEEL_X`, `MOTOR_Y`, `COLS` y `ENTERA`.

```bash
B=/Applications/Blender.app/Contents/MacOS/Blender      # Blender 4.2
$B -b -P diseno/blender/generar_bicho_v3.py -- /tmp/bicho        # STL, GLB, renders y .blend (unos 20 s)
$B -b -P diseno/blender/prueba_tolerancia.py -- /tmp/bicho/stl   # B00
python3 -I diseno/blender/empaquetar_impresion.py /tmp/bicho diseno/imprimir   # bandejas .3mf + impresion.json
```

Después hay que copiar `/tmp/bicho/stl/*.stl` a `imprimir/STL/` y `/tmp/bicho/glb/*.glb` a `modelos/`.

## Lo que hay que confirmar con el hardware

- **Agujeros de montaje del motor TT:** las ranuras de la cuna P24 tienen ±7 mm de juego.
- **Diámetro del parlante omnidireccional:** se supuso de 90 mm. El del inventario (#130) es cuadrado, de 40 a 50 mm.
- **Lente del ADNS-3080 (M12, f = 8 mm):** de fábrica enfoca desde unos 30 cm. Hay que desenroscarla unos 3 mm para que enfoque el suelo.

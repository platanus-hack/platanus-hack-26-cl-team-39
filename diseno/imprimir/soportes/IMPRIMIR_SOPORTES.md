# Soportes de sensores y audio de Bicho: listos para imprimir

21-nov-2026 · **El brazo se descartó.** Lo que queda por imprimir son los soportes de cada componente, en **una sola impresión**.

## Imprimir ya

| Impresora | Archivo (copiar a la microSD) | Tiempo | PLA |
|---|---|---|---|
| **Bambu A1** (la chica) | [`SD/A1_SOPORTES.gcode.3mf`](SD/A1_SOPORTES.gcode.3mf) | **2 h 32 min** | 94 g |
| Bambu A2L (la grande, respaldo) | [`SD/A2L_SOPORTES.gcode.3mf`](SD/A2L_SOPORTES.gcode.3mf) | 2 h 30 min | 95 g |

Antes de imprimir, comprueba esto:
- Filamento PLA, blanco o del color que haya; el color no importa.
- Boquilla de 0,4 mm.
- Placa **Textured PEI**.

**Pasos:**
1. Copia el archivo a la raíz de la microSD.
2. En la impresora, entra a **Imprimir archivos** y elígelo.

No hay que laminar nada. El archivo ya trae el modelo de impresora correcto (A1 = N2S, A2L = N9), así que la impresora no lo rechaza.

El perfil es rápido: capa de 0,28 mm, 3 paredes, 15 % de giroide, brim de 3 mm y sin soportes.

## Qué trae (7 piezas)

| Pieza | Para qué | Cómo va |
|---|---|---|
| **P40** · LiDAR | Módulo EAI S850 y su placa Radar_Con | Las dos placas entran desde arriba en ranuras, el sensor adelante mirando al frente. 4 M3 a la rejilla o pegado |
| **P41** · Cámara frontal | Pi Camera v1.3 | Entra desde arriba, lente al frente, inclinada 12° hacia arriba. La cinta baja por la ventana de la base al pasacables delantero (x = 130) |
| **P04 ×3** · ESP32-CAM | Las cámaras ESP32 | 2 M3 a la rejilla. La lente asoma por el agujero de 9 mm |
| **P42** · ReSpeaker XVF3800 | El micrófono y su anillo de LED | La placa redonda de Ø99 se apoya en una repisa a 10 mm y la retienen 3 trabas. Tiene salida de 28 mm para el USB y el parlante. 4 M3 a ±40 mm |
| **P43** · Parlante | Parlante de 40 a 52 mm | Entra desde arriba mirando al frente (rejilla de Ø38). Se fija con silicona caliente. 2 M3 |

**Medidas que conviene comprobar con pie de metro:**
- **ReSpeaker:** se diseñó para Ø99 mm.
- **S850 y Radar_Con:** sus medidas salieron de una foto (≈20 × 25 y 25 × 31 mm).
- **Parlante:** se supuso de hasta 52 mm de ancho.

Si alguna no calza, se cambia la cifra al inicio de `diseno/blender/generar_soportes_sensores.py` o de `generar_soportes_audio.py` y se regenera.

## Archivos
- `STL/`: las 5 piezas sueltas.
- `3MF/`: las bandejas sin laminar, para abrirlas en Bambu Studio.
- `SD/`: los archivos laminados y `tiempos.json`.

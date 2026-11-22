---
autor: Walls (Claude)
fecha: 2026-11-21
tipo: decision
---

# El brazo se descarta; los soportes de sensores y audio salen en una sola impresión

**Decisión de Rodrigo (≈22:30):** no se hace el brazo. Del brazo v4 se alcanzaron a imprimir en la CR-3040 las placas P09B, P10A y P10B y los separadores. Las bandejas de la torreta y las cunas se cancelan, y también la Sermoon que se cortó.

**Lo que hay que imprimir ahora** está en [`diseno/imprimir/soportes/`](../../diseno/imprimir/soportes/IMPRIMIR_SOPORTES.md). Es **una sola impresión** con 7 piezas:
- LiDAR (S850 + Radar_Con);
- cámara Pi frontal;
- 3 ESP32-CAM;
- ReSpeaker XVF3800 (nuevo);
- parlante (nuevo).

Para la **Bambu A1**: `SD/A1_SOPORTES.gcode.3mf`, **2 h 32 min**, 94 g de PLA. La versión para la A2L tarda 2 h 30 min.

Se copia a la microSD y se elige en la pantalla; no hay que laminar nada.

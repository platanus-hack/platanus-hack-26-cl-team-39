---
autor: Guty (Claude)
fecha: 2026-11-21 04:41
tipo: avance
---

# Simulador 3D del bicho en bicho·dev

En bicho·dev → **Simulador** está el bicho en 3D con piezas del inventario: chasis 4WD, Pi 3, LiDAR, ultrasonido, pantalla 8×8, bomba de agua y un brazo de 3 ejes con la cabeza en la punta (anillo de 24 LEDs con la cámara al centro). Se puede poner un perro o una persona en el patio, ver lo que sienten los sensores y lo que ve la cámara, y la app del dueño (el círculo al que se le habla) al lado.

El **idioma del bicho** está en [`bicho/lenguaje.json`](../../bicho/lenguaje.json): 30 estados con su sonido, luz, gesto del brazo, movimiento, ícono y texto para la app, más 5 escenas para ensayar la demo. Es una propuesta: **Walls y Cristian** (personalidad), ajústenlo ahí mismo, porque lo lee el simulador y la idea es que lo lea también la Pi. Regla incluida: "Rocía agua" solo para animales; con una persona cambia a advertencia.

Para quien hace los deploys: la web ahora usa three.js (se carga solo al abrir el simulador) y lee `../bicho/lenguaje.json`, fuera de `web/`. Revisen que Vercel incluya los archivos fuera del directorio raíz.

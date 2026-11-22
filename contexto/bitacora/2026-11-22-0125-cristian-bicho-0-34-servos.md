---
autor: Cristian (Claude)
fecha: 2026-11-22 01:25
tipo: avance
---

# bicho v0.34.0: comando `servo`, en un segundo PCA9685

Los servos van en otro PCA9685 (dirección 0x41: hay que soldarle el puente A0), no en el de los motores: la frecuencia es una por chip, y los motores van a ~200 Hz mientras un servo necesita 50 Hz. `{"cmd":"servo","i":0,"deg":90}` lo lleva a un ángulo y lo sostiene; `"us"` manda el pulso en crudo para calibrar, `"barrer":true` lo prueba y `"soltar":true` le corta el pulso. Código en [`bicho/servos.py`](../../bicho/servos.py).

Cableado, distinto al de los motores: el servo usa las tres filas del canal (señal, V+, GND) y la bornera verde lleva 5 a 6 V de una fuente aparte, nunca los 9 V de los motores. Publicada en bicho·dev; probada solo en simulación, falta probarla con un servo de verdad.

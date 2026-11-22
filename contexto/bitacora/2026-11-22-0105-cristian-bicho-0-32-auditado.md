---
autor: Cristian (Claude)
fecha: 2026-11-22 01:05
tipo: avance
---

# bicho v0.32.0: versión auditada, publicada y sin instalar

Auditoría de lo que el bicho llevaba escrito (v0.30.0, 7.666 líneas en 22 módulos): no hay módulos ni imports muertos; el tamaño viene de las habilidades. Lo que sí estaba mal y quedó arreglado en la 0.32.0:

- **Los motores no partían después de un reinicio:** el STBY de los 4 drivers TB6612 va a los GPIO 27, 22, 23 y 24 y nadie lo subía (el 27 y el 22 los tenía `luces.py` como luz verde y roja). Ahora `motores.py` los sube al partir y los baja al terminar, y las luces no los tocan mientras se mueve.
- **«Invertir» deshacía lo anterior:** `"invertir":[4]` reemplazaba la lista, así que dar vuelta el motor 4 dejaba el 1 otra vez al revés. Ahora da vuelta solo los nombrados; `"invertidos":[1,4]` fija la lista completa.
- Topes de motores a 60 % y 10 s (eran 30 % y 3 s).
- La descripción de versión tenía 8 mil caracteres y viajaba en cada `info` y en cada decisión del cerebro: quedó en 400.

`bicho/` en `dev` ahora es esta versión (trae `motores.py`, `i2c.py`, `gpios.py` y `descubrir.py`, que solo vivían en el Pi). Está publicada en bicho·dev como disponible: **instalarla es apretar Actualizar**, con el bicho conectado. Ojo: si el Cerebro aprende algo antes de instalarla, parte de la 0.30.0 y esto habría que volver a aplicarlo.

Cableado que supone el mapa de motores (PCA9685, fila de señal): motor N → PWM 3(N−1), IN2 3(N−1)+1, IN1 3(N−1)+2.

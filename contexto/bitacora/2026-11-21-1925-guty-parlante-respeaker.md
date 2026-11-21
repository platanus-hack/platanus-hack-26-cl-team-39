---
autor: Guty (Claude)
fecha: 2026-11-21 19:25
tipo: avance
---

# El parlante del Bicho ya suena (por el ReSpeaker)

El parlante va conectado al ReSpeaker XVF3800, no al Pi. No sonaba aunque `aplay` terminaba bien: el volumen de salida del ReSpeaker en ALSA (el PCM-1 de `alsamixer`) estaba en 67 %, y con este parlante chico no se oía nada. Al subirlo al 100 % empezó a sonar. El Bicho quedó en la v0.21.0, con `{"cmd":"speaker","mezclador":true}` para ver ese volumen y `{"cmd":"speaker","volumen":100}` para subirlo: queda guardado y se repone al arrancar. La salida elegida es el ReSpeaker (`plughw:Array`), y el sonido del gesto también sale por ahí.

**Ojo:** el código que escribió el Cerebro (v0.20 y v0.21) vive en el Pi y no en git, y el `bicho/` del repo sigue en 0.5.0. Si alguien publica una versión desde el repo, el Bicho pierde todo lo que aprendió. Para cambiarlo a mano: bajar lo que corre con `{"cmd":"fuente"}`, editar eso y mandarlo con `POST /update`.

**Sigue:** pedirle "bicho, aprende a hablar por tu parlante" para que implemente `hablar`, ahora que el parlante, la salida y el volumen ya están listos.

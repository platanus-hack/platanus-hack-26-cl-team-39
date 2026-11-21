---
autor: Guty (Claude)
fecha: 2026-11-21 20:02
tipo: avance
---

# El Bicho ya se expresa con luz y sonido, como en el simulador

Bicho v0.24.0 trae `{"cmd":"expresar","estado":"contento"}`: la luz del estado en el anillo de 12 LEDs del ReSpeaker y su sonido por el parlante, con los mismos patrones y notas del simulador (los sonidos se sintetizan en el Pi). También corre las 5 escenas completas: `{"cmd":"expresar","escena":"pieza"}` es «Pide una pieza y aprende», la del pitch. Para manejar solo la luz está el comando `anillo` (estados, patrones, efectos del chip, brillo). Las dos cosas se probaron en el bicho real.

**Límite:** el ReSpeaker tiene el firmware 2.0.6, y pintar LED por LED llegó en el 2.0.7. Mientras no se actualice, 22 de los 31 estados se ven igual que en el simulador y los que giran o avanzan alrededor del anillo (piensa, patrullando, reprogramando, probando, emocionado…) se ven como pulso, parpadeo o arcoíris del chip. El código LED por LED ya está y se activa solo al detectar el firmware nuevo. Actualizarlo toma unos 10 minutos con `dfu-util` y el ReSpeaker conectado a un computador: está por decidir.

**Repo:** `bicho/` en `dev` ahora es igual al Pi (antes seguía en 0.5.0 y todo lo que aprendió el Bicho vivía solo en el Pi). La 0.24.0 también quedó publicada en bicho·dev. Junta el arreglo del relé de Cristian en `bichod.py` y las voces de `lenguaje.json`, que estaban en el repo y no en el Pi.

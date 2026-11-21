# Bicho

**El bicho que se parcha solo.** Un robot que se programa solo: si le pides algo que no sabe hacer, escribe, instala y prueba su propio código en vivo.

## Qué hace

Los robots hacen lo que el fabricante les programó. Bicho no viene con habilidades fijas: cuando le pides algo nuevo, se lo enseña a sí mismo.

1. **Le pides algo.** Bicho escucha y sabe de dónde le hablan.
2. **Escribe un parche.** Escribe el código nuevo con Claude.
3. **Se lo instala.** Por WiFi, y lo prueba antes de activarlo.
4. **Lo hace.** Si el parche falla, vuelve solo al anterior.

## Cómo funciona

- **Oído:** micrófono ReSpeaker que da el ángulo de la voz; Whisper pasa lo que oye a texto.
- **Cerebro:** Claude decide si le hablan a él y qué hacer; cuando no sabe hacer algo, escribe el parche.
- **Relé:** le hablamos y lo vemos desde cualquier red.
- **Raspberry Pi 3:** prueba cada parche antes de activarlo y, si no responde en 60 s, vuelve al anterior. El código que lo mantiene vivo no se puede reescribir.
- **bicho·dev:** el panel para verlo aprender: sensores, consola, parches y simulador.

## Equipo CRBRC

Carlos, Cristian, Guty, Renate y Walls.

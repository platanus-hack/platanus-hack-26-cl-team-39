---
autor: Guty (Claude)
fecha: 2026-11-21 12:25
tipo: avance
---

# El Bicho ya puede hablar en vivo, con dos voces

El Bicho se expresa casi siempre con sonidos y luces; la voz es especial. Ahora tiene dos, diseñadas en ElevenLabs: **dueño** (grave, algo robótica, cercana) y **extraños** (demoníaca, para asustar a quien entra al terreno). Los `voice_id` están en `bicho/lenguaje.json` → `voces`. El Cerebro tiene una herramienta nueva, `hablar`: decide qué decir y con qué voz, pide el audio a ElevenLabs en el momento y lo manda al Bicho (`{"cmd":"hablar"}`) y a bicho·dev (`{"t":"voz"}`). En bicho·dev → Cerebro se ve qué dijo y se puede escuchar; con "Voz aquí: sí" suena también en el computador, como plan B si el parlante falla. Formato en `PROTOCOLO.md`.

**Cristian:** para que funcione hay que hacer pull, poner `ELEVENLABS_API_KEY` en `cerebro/.env` de EDITH (Guty te la pasa por privado; es de su cuenta, donde están las voces) y reiniciar el Cerebro y el relé. Sin la clave, el Cerebro sigue igual que antes y solo responde por escrito.

Después, que alguien le escriba "bicho, aprende a hablar por tu parlante": el Cerebro ya conoce el formato del comando y lo aprende solo (con `aplay`). Mientras no lo aprenda, su voz se oye solo en bicho·dev. La cadena completa todavía no se probó porque falta la clave; las voces y el audio se probaron por separado.

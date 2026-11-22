---
autor: Cristian (Claude)
fecha: 2026-11-22 08:05
tipo: avance
---

# El oído del bicho transcribe con ElevenLabs Scribe; Groq queda de respaldo

Groq se quedó sin cupo: el plan gratis da 2000 transcripciones al día y la sala las gastó (el micrófono transcribe todo lo que se habla cerca). Ahora el relé transcribe con **ElevenLabs Scribe v2** usando la clave de ElevenLabs que ya estaba en EDITH: ~0,7 s por frase y, con `bicho` como término clave, entiende «Bicho» y no «Nicho» o «Micho». Si Scribe falla, el relé prueba con Groq (que además acepta varias claves separadas por comas).

Ojo: cada frase de la sala gasta créditos de esa cuenta de ElevenLabs, los mismos que usa la voz del bicho. Para la demo conviene revisar el saldo.

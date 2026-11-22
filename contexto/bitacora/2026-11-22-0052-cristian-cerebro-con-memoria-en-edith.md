---
autor: Cristian (Claude)
fecha: 2026-11-22 00:52
tipo: avance
---

# El cerebro con memoria ya corre en EDITH

`platanus-cerebro` quedó con el `cerebro.mjs` y el `memoria.mjs` de `dev` (commit `cafefca`); el anterior está al lado como `cerebro.antes-de-memoria.mjs`. Probado en vivo: recuerda entre mensajes y entre reinicios, y contesta lo escrito aunque el bicho esté desconectado.

Quedó con `CEREBRO_ESCUCHA=estricto` en su `.env` por la sala llena: del micrófono solo evalúa lo que dice «bicho». Para volver a como estaba, cambiar a `nombre` y reiniciar. La voz sigue apagada: falta `bicho/lenguaje.json` (los `voice_id`) al lado del cerebro en EDITH.

Ojo al desplegar el cerebro: ahora son dos archivos, `cerebro.mjs` y `memoria.mjs`. Su memoria vive en `C:\srv\platanus\cerebro\memoria.json`; borrarlo es dejarlo sin recuerdos.

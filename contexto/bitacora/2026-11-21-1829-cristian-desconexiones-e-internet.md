---
autor: Cristian (Claude)
fecha: 2026-11-21 18:29
tipo: problema
---

# El bicho se desconectaba del relé cada minuto: arreglado. Y el cerebro ya puede buscar en internet

**Desconexiones.** Eran dos problemas juntos:

1. **Error en `bichod.py`:** el bicho cortaba la conexión con el relé si pasaba un minuto sin recibir un mensaje de texto, y no contaba como señal de vida los pings que el relé manda cada 5 s. Si nadie le mandaba un comando, se reconectaba cada 62 s exactos. Ahora cualquier trama que llegue cuenta. Está corregido en `bicho/bichod.py` y aplicado a mano por SSH en el Pi, sobre la versión 0.16.0 que corre (el original quedó al lado como `bichod.py.antes-del-parche`). Después del arreglo: 3 minutos y medio seguidos sin reconectarse.
2. **El hotspot donde estaba el Pi:** su internet celular dejaba pegadas las conexiones TCP por ratos de 8 a 25 s, aunque el WiFi local y los pings andaban perfecto. El Pi se cambió a otro hotspot, que quedó con prioridad; el anterior sigue guardado como respaldo.

De paso: el ahorro de energía del WiFi del Pi quedó apagado y fijo (también en `bicho/install.sh` para instalaciones nuevas). No era la causa. El Pi marca `throttled=0x50000`: tuvo bajones de voltaje desde que prendió, así que la fuente de 5 V y 2,5 A sigue pendiente, sobre todo antes de conectar servos.

Si el bicho vuelve a caerse cada minuto después de un aprendizaje, es que la versión nueva salió sin el arreglo: hay que revisar que el `bichod.py` del Pi tenga `ws.visto`.

**Para entrar al Pi:** el computador tiene que estar en el mismo hotspot que el Pi; ahí `ssh team39@team39.local` entra con llave. El log del servicio no se guarda (el servicio es de usuario: `systemctl --user status bichod`).

**Internet para el bicho.** El cerebro tiene una herramienta nueva, `buscar`, que consulta Exa cuando le preguntan algo que no sabe o algo actual. Solo se activa si hay `EXA_API_KEY`. **Quien corre el cerebro:** hacer pull, agregar `EXA_API_KEY=...` a `cerebro/.env` (pedir la clave por privado a Cristian) y reiniciarlo. Las llamadas a Exa se probaron sueltas; el cerebro completo con la herramienta todavía no.

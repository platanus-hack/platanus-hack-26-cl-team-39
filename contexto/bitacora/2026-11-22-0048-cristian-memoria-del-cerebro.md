---
autor: Cristian (Claude)
fecha: 2026-11-22 00:48
tipo: avance
---

# El cerebro ahora tiene memoria de verdad

Antes recordaba 12 líneas que compartía con todo lo que oía el micrófono: en la sala, lo que uno le escribía se le borraba en menos de un minuto. Ahora ([`cerebro/memoria.mjs`](../../cerebro/memoria.mjs)) guarda hechos que él elige (`recordar` / `olvidar`), la conversación reciente como mensajes de verdad y un resumen de lo anterior, todo en `cerebro/memoria.json` (no se sube; sobrevive a reinicios). Lo ignorado ya no ocupa memoria, y escribirle no pone a escuchar la sala.

Para la sala llena: `CEREBRO_ESCUCHA=estricto` (solo si dicen «bicho») o `no` (solo escrito). Si el bicho está desconectado, el cerebro igual contesta lo escrito y bicho·dev lo avisa en el panel del Cerebro.

Falta: copiar `cerebro.mjs` y `memoria.mjs` a EDITH y reiniciar `platanus-cerebro`; la copia de allá es de ayer en la mañana.

---
autor: Guty (Claude)
fecha: 2026-11-21 11:21
tipo: problema
---

# Lo que se le escribía al Cerebro no llegaba: el relé lo botaba sin avisar

Si la conexión de bicho·dev con el relé no traía la clave correcta del equipo (o se puso después de conectar), el relé descartaba en silencio lo que se le escribía al Cerebro y la web no decía nada. Ya está arreglado en `dev` (commit 980c593): lo escrito aparece como "Enviando…" y, si el relé no lo devuelve, la web muestra el problema con un botón para volver a conectar.

**Cristian:** el commit también cambia `rele/servidor.mjs` para que el relé conteste con un aviso en vez de botar el mensaje, y para que diga en el saludo si la conexión puede mandar. Para que corra hay que hacer pull y reiniciar el relé en EDITH. La web funciona igual mientras tanto.

Si a alguien no le llega lo que escribe: en Equipo → Inventario tiene que estar la misma clave que usa el relé, y después hay que tocar "Volver a conectar".

# Decisiones

_Una línea por decisión, la más nueva abajo. Formato: fecha y hora · decisión · por qué · quién. Si una decisión se revierte, no la borres: agrega una nueva que lo diga._

- **19 nov** · Track hardware sí o sí · el track lo pide y es tendencia; la rúbrica premia originalidad, ambición y aspecto técnico · todo el equipo
- **21 nov, 00:01** · Web interna "bicho·dev" para ver el firmware, actualizarlo y ver sensores en vivo · para iterar rápido sin cables · todo el equipo
- **21 nov** · Raspberry Pi 3 en vez de ESP32 · corre Python, se actualiza por WiFi y le da espacio a un agente · todo el equipo
- **21 nov** · Se descarta la lámpara: el bicho es un robot 4WD que maneja y reprograma un agente Claude · más ambicioso y más demostrable · todo el equipo
- **21 nov** · El trabajo va en la rama `dev`; `main` solo para enviar · cada push a `main` cuenta como envío a Platanus · Guty
- **21 nov** · Los deploys los hace una sola persona del equipo · para no pisarse · equipo
- **21 nov, 04:04** · Un solo brazo, de 2 o 3 ejes · alcanza para los usos pensados (resumen de Granola) · equipo de hardware
- **21 nov, 04:00** · El inventario pasa del Claude Sheet a Neon + bicho·dev, con API para que los Claude lo lean y editen · el Sheet daba problemas y no lo podían editar los Claude · Guty
- **21 nov, 04:20** · Harness del equipo en el repo: `CLAUDE.md` + `contexto/` + skills compartidas · que todos los Claude tengan el mismo contexto · Guty
- **21 nov, 05:30** · Brazo al centro sobre un pedestal y LiDAR 2D fijo montado en el brazo (o en un servo), no en una torre · el LiDAR no gira; así barre con el movimiento del brazo · equipo de hardware
- **21 nov, 06:20** · Estructura impresa de 32 × 20 cm con 3 placas iguales de una sola pieza (rejilla M3 cada 10 mm, PLA 40 %) · rígida, sin juntas, y cualquier pieza se atornilla donde se quiera · equipo de hardware
- **21 nov, 06:20** · El bicho se conecta hacia afuera a un relé (`rele/`, servicio aparte en el mismo repo, corre en EDITH) y la web habla con el relé · el Pi no tiene dirección pública y la red del evento es solo 5 GHz (el Pi 3 queda en un hotspot); así se ve y se actualiza desde cualquier red · Cristian
- **21 nov, 11:58** · El robot se llama **Bicho** (deja de ser un nombre provisorio) · el Cerebro ya está ajustado a cómo Whisper transcribe "bicho" y todo el proyecto ya lo usa · votado por el equipo
- **21 nov, 12:10** · Marca de Bicho: «el bicho que se parcha solo»; logo con el ojo de 24 LEDs y una curita, y el estilo visual «Cristal claro» de bicho·dev (fondo crema con manchas, vidrio, azul de acento, ícono amarillo) para el pitch, el video y la entrega · un bicho también es un bug y la curita cuenta lo que lo hace distinto; el estilo de bicho·dev ya era del equipo · Guty

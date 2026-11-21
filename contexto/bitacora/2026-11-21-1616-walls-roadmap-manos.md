---
autor: Walls (Claude)
fecha: 2026-11-21 16:16
tipo: decision
---

# Roadmap del hand tracking: el wow es enseñarle un gesto, manejar con la palma es opcional

Tres agentes revisaron el hand tracking contra lo que el bicho es hoy (Pi 3 + relé, fw 0.11.0, sin motores). El plan consolidado está en `handtracking/ROADMAP.md`. Para la demo: haces la V, el bicho no reacciona, le dices «cuando te haga la V, celebra», el cerebro aprende, y a la segunda V celebra. Manejar con la palma solo entra si a la 01:00 hay motores con watchdog en el núcleo.

La app Unity ya entra por el relé (`https://<relé>` y la clave del equipo) y los gestos prenden las luces del bicho real (pulgar → `si`, V → `responder`, puño → `no`). El manejo al bicho parte apagado.

**Carlos:** (1) urgente: bajar el código vivo 0.11.0 con `{"cmd":"fuente"}` y commitearlo en `bicho/`, porque si alguien publica desde el repo (0.5.0) se pierde lo aprendido. (2) En `bichod.py`, que `manejar()` pueda responder `""` sin mandar aviso (parche en `handtracking/roadmap/plan-tecnico-xr.md`). (3) Motores: cableado y `motores.py` propuestos en ese mismo archivo, §3.
**Walls/Cristian:** describir el mensaje `gesto` en `SISTEMA_APRENDER` de `cerebro.mjs`.
**Guty:** propuesta de una sección «Manos» en bicho·dev en `handtracking/roadmap/plan-bicho-dev-manos.md`. No se tocó nada tuyo: dinos si te sirve o si lo hace otro.

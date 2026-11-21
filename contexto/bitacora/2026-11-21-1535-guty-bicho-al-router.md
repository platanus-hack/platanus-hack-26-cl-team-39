---
autor: Guty (Claude)
fecha: 2026-11-21 15:35
tipo: avance
---

# El bicho se puede pasar del hotspot al router del equipo con un comando

Nuevo `bicho/wifi.sh`: quien tenga SSH al Pi (mientras siga en el hotspot) corre `sudo bash wifi.sh "NombreDelRouter"`, escribe la clave (no queda en el repo) y el Pi se cambia al router y lo deja como red preferida. El hotspot queda de respaldo: si el router se apaga o la clave está mala, vuelve solo. Pasos completos en `bicho/README.md` → «Cambiar de red WiFi».

Ojo: el Pi 3 solo ve 2.4 GHz, así que el router tiene que tener esa banda prendida. Para que el bicho llegue al relé, al cerebro y a la voz, el router necesita internet (cable desde su puerto WAN a un punto de red del evento). No hace falta abrir puertos en el router: el bicho sale hacia el relé. Abrir el 8080 hacia el Pi solo sirve para entrar directo desde la red del evento sin el relé.

**Quien tenga SSH al Pi (¿Carlos?):** correrlo y confirmar en bicho·dev que la línea «Red» diga el nombre del router.

---
autor: Walls (Claude)
fecha: 2026-11-21 16:33
tipo: avance
---

# El bicho aprende señas: «esta seña significa para» y se detiene al verla

Nuevo `handtracking/tracker/senas.py`. Corre en un computador y se conecta al relé como un cliente más. Toma la cámara del bicho (las imágenes `{"t":"imagen"}`) y su oído (`{"t":"oido"}`). Cuando alguien muestra la mano y dice «esta seña significa X», guarda esa seña y lo anuncia en bicho·dev con eventos `paso`/`aprendido`, así sale en Cerebro y Habilidades. Cuando vuelve a ver la seña, manda la acción: para → `stop` + `no`. Lo probé de punta a punta con el relé en local y un bicho falso. Se corre con `./correr.sh senas --rele https://<relé> --clave <clave> --ver`.

**Walls/Cristian:** el cerebro también oye la frase. Que ignore las que dicen «seña», si no se pone a escribir código para eso.
**Carlos:** confirmar que la cámara se prende con `{"cmd":"camara","on":true}` (el servicio la manda cada vez que el bicho se conecta).
Ensayo interactivo de la demo, con el modelo 3D y diagramas: https://claude.ai/artifact/3Xh4pvMBCPUGVwnrkk729f (privado, pedir acceso a Walls).

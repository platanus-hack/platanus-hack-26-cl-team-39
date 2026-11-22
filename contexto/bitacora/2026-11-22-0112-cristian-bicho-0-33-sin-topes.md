---
autor: Cristian (Claude)
fecha: 2026-11-22 01:12
tipo: avance
---

# bicho v0.33.0: motores sin topes, para que pueda correr

Reemplaza a la 0.32.0 (misma auditoría, más esto): la potencia llega a 100 % y ya no hay tope de tiempo. `"seg":0` lo deja corriendo hasta `{"cmd":"motores","on":false}`; sin `"seg"` sigue siendo el movimiento corto de siempre. Publicada en bicho·dev como disponible; no está instalada.

Cuidados: son 9 V en motores de 3 a 6 V, así que al 100 % sostenido se calientan. Corriendo sin límite, si se cae el WiFi no hay cómo mandarle parar: se detiene al apagarlo (al reiniciarse la Pi el STBY de los drivers baja solo).

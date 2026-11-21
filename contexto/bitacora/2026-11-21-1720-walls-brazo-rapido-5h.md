---
autor: Walls (Claude)
fecha: 2026-11-21
tipo: decision
---

# Brazo v4 en menos de 5 h: 2 bandejas en paralelo

Con el perfil de calidad, el brazo tomaba 16,6 h en una sola máquina. Ahora se imprime en **2 bandejas, R1 y R2, una por impresora al mismo tiempo**. Cada una tarda unas 4 h 15 min en PLA:
- **Perfil:** capa de 0,28 mm, 3 paredes, 15 % de giroide.
- **Torreta v4.1:** pasó a 4 orejas, sin base entera, con pared de 2,5 mm.
- Todo queda por sobre el torque de bloqueo de los servos.

Los G-code están en `diseno/imprimir/brazo_v4/SD/` (`A1_PLA`, `A2L_PLA` y PETG de respaldo) y en Drive, en la carpeta «RAPIDO_5h». Si solo hay una impresora libre, va R1 primero. Para liberar una A2L, la placa de arriba se puede cambiar por la acrílica del kit.

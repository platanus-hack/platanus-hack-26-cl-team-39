# Bitácora

Una entrada por archivo, para que dos personas puedan anotar a la vez sin conflictos en git.

**Nombre:** `AAAA-MM-DD-HHMM-autor-tema.md`, con la hora de Santiago y todo en minúsculas sin tildes. Ejemplo: `2026-11-21-0415-renate-sensor-laser.md`.

**Contenido:**

```markdown
---
autor: Renate (Claude)
fecha: 2026-11-21 04:15
tipo: avance        # avance | decision | problema | idea | reunion | link
---

# El sensor láser ya entrega distancia por I2C

Dos a cinco líneas: qué pasó, qué significa para el resto y qué sigue.
Si cambia el estado o hay una decisión, actualiza también estado.md o decisiones.md.
```

Las entradas no se editan después (si algo cambió, se escribe una nueva). El hook de inicio de Claude Code muestra las últimas ocho.

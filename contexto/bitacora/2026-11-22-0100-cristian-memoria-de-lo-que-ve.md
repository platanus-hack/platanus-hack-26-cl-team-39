---
autor: Cristian (Claude)
fecha: 2026-11-22 01:00
tipo: avance
---

# El cerebro recuerda lo que ve, con hora y lugar

Con `CEREBRO_MIRA_S=30` el cerebro pide una foto cada 30 s, la describe y la guarda con la hora y el lugar (idea de ReMEmbR, de NVIDIA). Después responde «¿pasó alguien?», «¿cuándo viste…?» o «¿dónde quedó…?» buscando ahí (`recordar_visto`). El lugar se lo dice una persona («te dejé en el patio» → `estoy_en`): la Raspberry no tiene GPS y adentro no serviría. Probado con fotos reales contra Claude. Detalle en [`cerebro/README.md`](../../cerebro/README.md).

Sirve para el caso de uso del guardián: deja al bicho mirando, entra alguien, y después se le pregunta qué vio y a qué hora.

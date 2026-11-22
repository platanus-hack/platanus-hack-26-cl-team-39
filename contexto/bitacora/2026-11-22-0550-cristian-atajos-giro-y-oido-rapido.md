---
autor: Cristian (Claude)
fecha: 2026-11-22 05:50
tipo: avance
---

# El bicho reacciona al tiro: atajos sin modelo, giro, oído más corto y cámara derecha

- **Atajos en el cerebro** (ya en EDITH): «para», «avanza», «atrás» y «gira a la izquierda/derecha» se reconocen por palabras y salen al bicho sin pasar por Claude. La orden sale en el instante; antes eran 1 a 3 s de modelo. «Para» corta siempre, aunque no lo nombren. Detalle en [`cerebro/README.md`](../../cerebro/README.md).
- **bicho v0.35.0** (publicada, hay que instalarla con Actualizar): `"giro":"izquierda"|"derecha"` gira en el lugar (lados por defecto: M1 y M2 a la izquierda, M3 y M4 a la derecha; se cambia con `"lados"`). El oído corta las frases a los 4 s o tras 0,35 s de silencio (eran 12 s y 0,6 s: en la sala, un tercio de las frases esperaba los 12 s). La imagen de la cámara sale girada 180°, porque quedó montada cabeza abajo.
- El cerebro ya no se niega ni pide confirmación por lo que ve en la cámara: obedece a la primera.

Sin la 0.35.0 instalada, «gira…» todavía pasa por el modelo; parar, avanzar y atrás ya van por atajo.

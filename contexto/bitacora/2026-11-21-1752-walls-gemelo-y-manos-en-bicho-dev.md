---
autor: Walls (Claude)
fecha: 2026-11-21 17:52
tipo: avance
---

# bicho·dev: pestañas «Gemelo 3D» y «Manos»

**Gemelo 3D** (`#gemelo`, `web/src/gemelo/`): el bicho completo pieza por pieza. Es el chasis impreso V1 (`web/public/modelos/bicho_V1.glb`) con el **brazo v4** de la vista Brazo (`/bim/brazo.glb`) montado en la cubierta, y el brazo viejo escondido. Los servos se mueven con el mismo `registro.json`. Encima van los sensores en vivo del relé:
- las luces de los GPIO 17, 27 y 22 se prenden en el modelo;
- la Pi se pone roja según `temp_cpu`;
- un anillo y una flecha muestran el ángulo de la voz del ReSpeaker;
- la última imagen de la cámara flota sobre el robot y se dibuja su campo de visión;
- cada lectura es clicable y resalta su pieza.

Trae poses del brazo (al frente, recoger, saludar, escanear, pinza), sliders por servo y «Mover el robot real» apagado por defecto (manda `servo` como la vista Brazo). Sin bicho, hay «Simular sensores». Todo cabe en una pantalla, igual que Brazo. Lo probé en local contra el relé en vivo: 19 Hz, con la cámara real en la pantalla flotante.

**Manos** (`#manos`, `web/public/manos/index.html`): la demo de enseñarle una seña (lo llamas, viene, aprende la seña frente a su cámara y se detiene al verla), ahora con el brazo v4 y la cámara en el soporte frontal. Con «Oído del bicho real», lo que transcribe su oído mueve la demo. Muestra también lo que anuncia `senas.py`.

**Guty:** no toqué tus vistas. En `App.tsx` hay dos enlaces más en la barra, dos ramas en el `main` y una línea en `onMessage` que reparte los mensajes (`web/src/lib/puente.ts`). Revísalo cuando puedas, y si prefieres otro lugar para las pestañas, muévelas. Falta publicar (deploy).

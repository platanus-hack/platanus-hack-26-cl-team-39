# Roadmap · hand tracking del Bicho

Sábado 21 nov, 16:15 → domingo 22, 8:30. Lo armaron tres agentes por separado y aquí está consolidado: ORBI (criterio XR), el desarrollador XR (Unity + Pi) y el desarrollador web (bicho·dev). El detalle de cada uno está en [`roadmap/`](roadmap/). [V] = verificado en vivo o en el repo; [I] = inferido.

## La decisión

**El momento wow es enseñarle un gesto.** Quien presenta hace la V y el bicho no reacciona. Le dice «Bicho, cuando te haga la V, celebra con el arcoíris», el cerebro escribe el parche en pantalla, vuelve a hacer la V y el bicho celebra. Es la misma frase del pitch («le pidieron algo que no sabía hacer y lo aprendió solo»), ahora con dos formas de enseñarle: la voz y la mano. Usa piezas que ya existen: luces, relé con clave y un cerebro que aprende [V].

**Manejar con la palma va como «una más».** Hoy el bicho no tiene motores ni comando `drive` [V], y en el escenario es el riesgo físico más alto. Se corta a la 01:00 si para entonces no hay motores con freno en el núcleo.

**Dónde corren las manos:**
- **Principal:** MediaPipe en el navegador, dentro de bicho·dev. El jurado ve en una sola pantalla la mano, el Cerebro y el Simulador, y llega al bicho por el relé desde cualquier red.
- **Plan B:** la app Unity, que ya funciona por el relé (ver abajo), con su gemelo virtual.
- **Plan C:** el video de 60 s.

## Qué quedó hecho hoy (16:15)

- **Unity → relé** [V]: escribe `https://<relé>` en el campo de IP y la clave del equipo. Por el relé real se conectó en 0,45 s, ve al bicho (fw 0.10/0.11), recibe sensores a 20 Hz y el relé responde un comando en 0,08 s.
  - El HUD muestra si el bicho está en línea y si la clave sirve.
  - Descarta las imágenes y la voz (más de 64 KB).
  - Ya no corrompe tildes.
- **Los gestos prenden las luces del bicho real** [V en código, sin probar con el robot]:
  - pulgar arriba → `si` (verde);
  - V → `responder`;
  - puño → `no` (rojo).
  
  Son comandos que el bicho vivo ya entiende.
- **Interruptor «enviar manejo al bicho»**, apagado por defecto. Mientras el bicho no tenga `drive`, cada comando de manejo vuelve como «comando desconocido» a todas las consolas: a 15 Hz serían 15 avisos por segundo [V, `bichod.py:350-354`].
- **Ya no sale a fondo si la palma entra por un borde:** hay que pasar por el centro para arrancar.
- 10 tests verdes.

## Fases

| Fase · límite | Qué | Quién | Terminado cuando |
|---|---|---|---|
| **0 · sáb 20:00** | **Rescatar el código vivo**: bajar 0.11.0 con `{"cmd":"fuente"}` y commitearlo en `bicho/`. Si alguien publica un release desde el repo (0.5.0), el bicho pierde cámara, flujo, luces y lo aprendido | Carlos o quien tenga la clave | `bicho/version.json` = 0.11.0 en `dev` |
| 0 | Gesto → relé → bicho, con la cámara del Mac (Unity hoy, navegador después) | Rodrigo (Unity) | Pulgar arriba frente al Mac prende la luz verde del bicho real |
| 0 | `bichod.py`: que `""` signifique «atendido sin aviso» (parche de 4 líneas en `roadmap/plan-tecnico-xr.md`). Lo instala una persona, porque el cerebro no puede tocar `bichod.py` | Carlos | Un `gesto` o un `drive` no llenan la consola |
| **1 · dom 00:30** | Que el cerebro sepa de los gestos: describir el mensaje `gesto` y sus 6 valores en `SISTEMA_APRENDER` (`cerebro/cerebro.mjs`) | Walls / Cristian | «Cuando te haga la V, prende el arcoíris» produce un parche que atiende `gesto` |
| 1 | Sección **Manos** en bicho·dev: `@mediapipe/tasks-vision@1.2.3` servido local, clasificador portado del C# a TS con los mismos tests, cámara espejada | Guty (dueño) con ayuda, avisando antes | Esqueleto y gesto a 24 fps o más en el Mac de la demo; la V manda **un** `gesto` por cambio |
| 1 | Ensayo de la demo A, 3 de 3, desde el parche publicado | Walls + Guty | Tiempo real anotado en el `[N] s` del pitch |
| **2 · dom 04:00 (opcional)** | Motores: 2 TB6612 directo a GPIO (PWM 12/13, IN 5/6 y 16/26, STBY 25, VM 6 V del LM2596, **nunca de los 5 V del Pi**) + `motores.py` con watchdog de 0,5 s, rampa, tope y `stop` que siempre gana | Renate (cables) + Carlos | Ruedas en el aire: `drive` mueve cada lado; el freno actúa con el WiFi cortado; `vcgencmd get_throttled` = `0x0` |
| 2 | Manejar con la palma por el relé; latencia medida | Rodrigo / Guty | p95 < 300 ms o solo modo fino |
| 2 | El Simulador obedece los mismos `drive` (gemelo) | Guty | Con la palma el bicho 3D avanza y gira hacia el lado correcto |
| **3 · dom 06:00** | Código congelado. 07:30: video de 60 s y plan B en el otro computador. 08:30: ensayo con la luz del escenario | todos | — |

## Seguridad (líneas rojas)

1. Ningún motor se mueve sin el watchdog de 500 ms, sin el tope de velocidad (40 % en la demo) y sin el `stop` **en el núcleo publicado**, nunca en código aprendido.
2. Un interruptor físico en la alimentación de los motores, aparte del Pi.
3. Puño = stop. Sin mano 0,3 s = stop. Espacio o botón rojo = parada con traba.
4. En la demo, las ruedas van en el aire o en el suelo, nunca andando sobre la mesa.
5. Mientras se maneja con las manos, el cerebro no maneja: hay un solo piloto a la vez.
6. La clave del equipo no va al repo ni se muestra en pantalla. La imagen de la cámara del Mac no sale del computador.

## Después de la hackathon

- Meta Quest 3 con `com.unity.xr.hands` como otra fuente de manos (`IHandSource` ya existe).
- Teleoperación con la cámara del bicho de fondo.
- Rutinas enseñadas con la mano y pedidas con la voz.
- Gemelo movido con la odometría de los dos sensores de flujo óptico.

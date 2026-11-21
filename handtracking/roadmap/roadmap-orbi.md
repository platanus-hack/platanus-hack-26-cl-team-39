# Roadmap hand tracking del Bicho · criterio ORBI

Sábado 21-nov 16:00 → domingo 22-nov 8:30 (demo 9:30). [V] = verificado en repo o en vivo hoy · [I] = inferido.

**Veredicto:** el wow sale de **enseñarle un gesto hablando** y que el cerebro escriba el código que le responde, con las luces que ya existen. Manejar con la palma va como «una más», solo si a la 01:00 hay motores con freno en el núcleo. Camino principal: **MediaPipe en el navegador dentro de bicho·dev, por el relé**. Plan B: la app Unity que ya existe, con su gemelo virtual.

## 1. Tesis de demo

| Opción | Wow | Encaja en «se parcha solo» | Depende de | Riesgo |
|---|---|---|---|---|
| **A. Enseñar un gesto nuevo** | Alto | Total: es la misma demo del pitch, ahora con las manos | Luces (existen [V]), relé con clave [V], cerebro que aprende [V] | Medio |
| B. Manejar con la palma | Muy alto | Bajo: es un control remoto | Motores y `drive`: **no existen hoy** [V] | Alto |
| C. Ver la mano en el Simulador 3D | Medio | Bajo | Solo bicho·dev | Bajo |

**Elijo A, y C de adorno.** El guion es este:
1. Quien presenta muestra la mano en V. bicho·dev dibuja el esqueleto y dice «victoria». Bicho no hace nada, porque no conoce ese gesto.
2. «Bicho, cuando te haga la V, celebra con el arcoíris.» → «Eso no lo sé hacer todavía. Dame un minuto.» → el parche se escribe en pantalla.
3. Vuelve a hacer la V → anillo arcoíris. «Nadie escribió esa línea. Le enseñamos con la mano y la voz.»

Así la frase del pitch («le pidieron algo que no sabía hacer y lo aprendió solo») gana una segunda entrada, la mano, y el jurado ve en una sola pantalla la mano, el código y la reacción. B es más espectacular, pero hoy no hay motores y en la mesa del escenario es el riesgo físico más alto.

## 2. Arquitectura

| Criterio | Unity de escritorio (existe) | **MediaPipe en el navegador, en bicho·dev** |
|---|---|---|
| Qué ya existe | Tracker Python a 30 fps, gestos, hombre muerto, gemelo y 10 tests verdes [V] | El relé, la clave, el Simulador three.js y la sección Cerebro [V]. MediaPipe web: por hacer |
| Conexión al bicho | `BichoLink` va **solo directo**, sin relé ni clave [V]: el Mac tendría que estar en el hotspot del iPhone | Relé `wss://…/ws?clave=` [V]: funciona desde cualquier red |
| Latencia | UDP local < 5 ms [I] + WS directo | Inferencia en el navegador ~30 fps [I, dato del fabricante] + túnel cloudflare 100-300 ms [I, hay que medirlo]. Para luces sobra; para manejar es el límite |
| Qué ve el jurado | Una segunda app, con un HUD IMGUI | La misma pantalla del pitch: mano, Cerebro y Simulador |
| Riesgo en la demo | 2 procesos, permiso de cámara de la terminal y la red local | 1 pestaña, permiso de cámara del navegador y el túnel |

**Camino principal:** pasar a TypeScript el reconocedor de gestos (ángulo de los dedos más un estabilizador de 3 cuadros, mismo criterio que `GestureRecognizer.cs`) con `@mediapipe/tasks-vision` dentro de bicho·dev. Se manda por el relé con el protocolo que ya define `handtracking/README.md` (`gesto`, `drive`, `stop`), sin inventar uno nuevo.
**Plan B:** la app Unity con `--mock`. Sin robot maneja igual el bicho virtual: se muestra en el computador de respaldo como «así lo manejaríamos».
**Plan C:** el video de 60 s.

## 3. Roadmap por fases

| Fase · hora límite | Qué | Quién | Terminado cuando (verificable) | Riesgo |
|---|---|---|---|---|
| **0 · sáb 20:00 (sí o sí)** | Mano → gesto → relé → bicho | Guty (bicho·dev) | En una pestaña de bicho·dev, la V manda **un solo** `{"cmd":"gesto","g":"victoria","mano":"der"}` por cambio de gesto (no un flujo continuo), y aparece en la consola del bicho [medir en vivo] | Permiso de cámara, el peso del modelo wasm |
| 0 | El bicho recibe `gesto` sin romperse | Carlos | Un `gesto` desconocido no lanza una excepción en `manejar()`: devuelve «no sé ese gesto» y queda en el log | Bajo |
| 0 | `stop` en el **núcleo** publicado | Carlos | `{"cmd":"stop"}` apaga las salidas (luces y, más adelante, motores) desde el código base, no aprendido | Bajo |
| **1 · dom 00:30** | Que el cerebro sepa que existen los gestos | Walls / Cristian | `SISTEMA_APRENDER` (`cerebro.mjs`) describe el mensaje `gesto` y sus 6 valores. El pedido «cuando te haga la V, prende el arcoíris» produce un parche que maneja `gesto` en `comandos.py` sin tocar el núcleo | Que el parche tarde más de 60 s o haga vuelta atrás |
| 1 | Ensayo A completo, 3 veces seguidas | Walls + Guty | 3 de 3 desde que el bicho vuelve al parche publicado. Se anota el `[N] s` real del pitch | Ruido de la sala en el Oído (se puede escribir el pedido en Cerebro) |
| 1 | Mano en el Simulador | Guty | Esqueleto de 21 puntos sobre la cámara, o como overlay en `#simulador`, a 30 fps o más medidos en el Mac de la demo | Bajo |
| **2 · dom 04:00 (opcional, se corta a la 01:00)** | Motores en el Pi | Renate (cableado) + Carlos | Ruedas **en el aire**: `drive` mueve cada lado; `stop` y el watchdog de 500 ms frenan, medido con el WiFi cortado | Alto: el driver no está confirmado y el Pi anda con poco voltaje [V] |
| 2 | Manejar con la palma | Guty | Palma = joystick a 10-15 Hz, zona muerta, puño = stop, 0,3 s sin mano = stop, pestaña oculta = stop. Latencia de ida y vuelta por el relé medida y anotada | Si la latencia pasa de 300 ms, se maneja solo en modo fino o se corta |
| **3 · dom 06:00 (congelado)** | Congelar | todos | Rama `dev` pusheada; ningún cambio a bichod ni al cerebro después de las 06:00 | Que se cuele un último arreglo |
| 3 · 07:30 | Video de 60 s con A + plan B en el otro computador | Guty + Walls | El video está en Drive. La app Unity abre con `--mock` en el computador de respaldo | Bajo |
| 3 · 08:30 | Ensayo en el escenario | Walls / Cristian | 1 ensayo completo con la luz y el fondo reales: la luz de contraluz baja la detección [I] | Iluminación de la sala |

**Línea para el pitch (Walls/Cristian):** en la lámina «Cómo funciona», el Oído pasa a ser «Oído y Manos»: «le enseñas con la voz o con un gesto».

## 4. Seguridad física

- **Parada de emergencia física:** un interruptor accesible en la alimentación de los **motores**, distinto del Pi (Renate). Es la única parada que no depende de ningún software.
- **E-stop por software:** botón rojo y tecla Espacio en bicho·dev mandan `stop` con traba. El puño también es stop.
- **Hombre muerto:** el navegador manda `drive` solo con la palma a la vista. Con 0,3 s sin mano, con la pestaña oculta o con el WS caído, deja de mandar y manda `stop`.
- **Watchdog en el Pi, en el núcleo:** con 500 ms sin `drive`, motores en cero. Vive en el código base que no se aprende ni se pisa: un parche aprendido nunca puede manejar motores sin pasar por él. Al arrancar y en cada vuelta atrás de 60 s, los motores parten apagados.
- **Límite de velocidad:** tope de 40 % de PWM puesto en el núcleo, no en el navegador. Si un parche aprendido pide más, se recorta.
- **En la demo:** ruedas en el aire o en el suelo, nunca andando sobre la mesa del escenario.

## 5. Después de la hackathon

`IHandSource` ya separa de dónde vienen las manos [V]. El paso natural es una fuente con `com.unity.xr.hands` en Meta Quest 3 (OpenXR hand tracking, mismos 21 puntos) para manejar con el visor puesto. Después viene la teleoperación con la cámara CSI del bicho como video en el visor, con un presupuesto de latencia de punta a punta de 150 ms o menos [I, por medir] y siempre con el watchdog en el robot. La otra rama es que el cerebro aprenda gestos **por demostración**: muestras el gesto 3 veces y escribe el clasificador. Ninguna de estas se promete hasta medirla en el dispositivo.

## 6. Riesgos y líneas rojas

| Riesgo | Mitigación |
|---|---|
| Latencia del túnel cloudflare desconocida | Medirla en la Fase 0. A no la necesita; B se corta si pasa de 300 ms |
| El parche de gestos se aprende mal o con vuelta atrás | Mostrarlo como show («para eso está la curita»), con el video de respaldo |
| El firmware vivo es 0.10.0 y el repo dice 0.5.0 [V]: lo aprendido vive solo en el Pi | Antes de la demo, volver al parche publicado. Lo de seguridad (stop, watchdog, tope) tiene que estar en el publicado, no aprendido |
| `handtracking/README.md` y el `.ino` asumen un ESP32 [V], descartado por el equipo | No usarlos como guía de cableado. Marcarlos obsoletos |
| Demasiados gestos inundan el relé o el cerebro | Mandar solo cuando cambia el gesto y como máximo 2 por segundo |

**Líneas rojas:** (1) ningún motor se mueve sin watchdog y tope de velocidad en el núcleo; (2) no se promete «lo manejas con la mano» si no se ensayó 3 de 3 con el robot real; (3) el código aprendido nunca toca `bichod.py`, `salida.py`, `oido.py` ni el freno; (4) la clave del equipo no va al repo público, que se envía con un push a `main` que solo hace una persona del equipo; (5) la cámara del navegador procesa la imagen en el computador y no se graba ni se envía al relé.

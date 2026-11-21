# bicho · hand tracking (Unity)

Manejar el bicho con las manos frente a la cámara del computador.

```
 cámara ──► tracker (Python + MediaPipe) ──UDP 5065──► app Unity ──WebSocket :8080/ws──► Pi ──UART──► ESP32 ──► PCA9685 ──► motores / servos
             21 puntos por mano, ~30-60 fps              gestos, joystick,             (mismo canal que el
                                                          gemelo virtual, HUD           panel Bicho Dev)
```

## Arrancar (3 pasos)

1. **Tracker**: `./correr.sh` (la primera vez instala el entorno). En macOS hay que darle permiso de cámara a la terminal.
   - Sin cámara: `./correr.sh --fake` (una mano sintética dibuja círculos y cierra el puño).
   - Sin robot: `./correr.sh --mock` levanta además un bicho simulado en `ws://127.0.0.1:8080/ws` que imprime cada comando.
2. **Unity 2022.3.60f1**: abre `unity/BichoHands` desde Unity Hub, abre cualquier escena y aprieta **Play**. La app se arma sola (cámara, pista, bicho virtual, manos y panel), sin configurar nada.
3. En el panel, escribe la **IP de la Pi** (o `127.0.0.1` con `--mock`) y aprieta **Conectar**.

Sin robot conectado igual se maneja el **bicho virtual** de la pantalla, así que la demo funciona siempre.

## Gestos

| Mano | Gesto | Qué hace |
|---|---|---|
| Derecha (manejo) | **Palma abierta** | Arma el manejo. La palma es un joystick: arriba = avanza, abajo = retrocede, a los lados = gira. Al centro hay una zona muerta. |
| Derecha | **Índice** | Modo fino (40 % de velocidad) |
| Derecha | **Puño** | STOP |
| Cualquiera | **Sin mano 0,3 s** | STOP (hombre muerto) |
| Izquierda | **Pinza** (pulgar + índice) | Servo 0 = altura de la mano · servo 1 = posición horizontal |
| Cualquiera | **Victoria / pulgar arriba** | Se manda `{"cmd":"gesto"}` al bicho para que el firmware haga lo que quiera (baile, luz) |
| Teclado | **Espacio** o el botón rojo | Parada de emergencia con traba (otro Espacio la suelta) |

La mano de manejo se cambia en el componente `BichoHandController` (`driveHand`).

## Protocolo (nuevo: lo tiene que entender el firmware)

La app usa el mismo WebSocket que el panel (`ws://<pi>:8080/ws`, una línea JSON por mensaje). **Comandos nuevos**:

```json
{"cmd":"drive","l":0.42,"r":0.31}        // -1..1 por lado; 15 Hz mientras se maneja
{"cmd":"stop"}
{"cmd":"servo","i":0,"deg":90}
{"cmd":"gesto","g":"victoria","mano":"izq"}   // palma | puno | indice | victoria | pulgar_arriba | pinza
```

Lee la telemetría que ya existe (`{"t":"s","d":{dist_cm, imu, servo, temp_cpu…}}`) y la muestra en el panel.

**Lo que falta en el bicho real:**
- **Pi**: que el servidor de `:8080/ws` reenvíe al ESP32 por UART las líneas con `cmd` = `drive`, `stop`, `servo` y `gesto`. Si ya reenvía todo, no hay que hacer nada.
- **ESP32**: pegar `firmware/bicho_manos_esp32.ino`, que trae los canales del esquemático (PCA9685 0x40 motores, 0x41 servos, STBY en GPIO13) y un **watchdog de 500 ms**: si deja de llegar `drive`, frena solo. No lo saquen: es lo que detiene el robot si se cae el WiFi.

## Archivos

```
correr.sh                       arranca el tracker (--fake, --mock)
tracker/hand_tracker.py         cámara → MediaPipe → UDP
tracker/mock_bicho.py           bicho simulado (WebSocket + watchdog)
tracker/muestras/               mano real del equipo (IMG_7996) usada en los tests
firmware/bicho_manos_esp32.ino  manejo de motores y servos con watchdog
unity/BichoHands/Assets/BichoHands/
  Scripts/HandData.cs           formato de datos + IHandSource (para cambiar de fuente: Quest XR Hands)
  Scripts/HandTrackingReceiver  UDP en un hilo aparte
  Scripts/GestureRecognizer     gestos por ángulo de los dedos + estabilizador de 3 cuadros
  Scripts/BichoHandController   gestos → drive/servo/gesto, mezcla diferencial, hombre muerto
  Scripts/BichoLink             WebSocket con el bicho («el último gana» para drive)
  Scripts/VirtualBicho          gemelo digital 4WD
  Scripts/HandSkeletonView      dibuja las manos
  Scripts/BichoHud              panel IMGUI
  Tests/Editor/                 10 tests (Window › General › Test Runner)
```

## Siguiente paso posible: Meta Quest

`IHandSource` separa de dónde vienen las manos. Para manejar con el visor puesto, se agrega una fuente con `com.unity.xr.hands` que llene los mismos 21 puntos, y el resto queda igual.

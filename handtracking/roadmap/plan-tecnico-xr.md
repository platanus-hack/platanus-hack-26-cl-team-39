# Plan técnico XR · hand tracking del Bicho contra la arquitectura real

ORBI · Desarrollador XR · 21-nov-2026 ~16:45 · solo análisis, no se tocó el repo.
Repo: `platanus-hack-26-cl-team-39` en `dev` (al día con origin/dev, último commit `99f11ae`).
Marcas: [V] verificado (archivo leído o medición en vivo) · [I] inferido.

## 0. Lo que medí en vivo (16:40, solo mirando, sin clave)

- [V] `GET /` del relé: `{"bicho":true,"espectadores":5,"fw":"0.11.0"}`. **El fw ya es 0.11.0, no 0.10.0** (build 2026-11-21 16:06). En el repo `bicho/version.json` dice 0.5.0.
- [V] `GET /info` → desc 0.11.0: cámara CSI ov5647 (`camara` = 640x480 a **1 imagen/s**, `foto`), luces GPIO 17/27/22 (`luz`, `verde`, `rojo`, `si`, `no`, `responder`, `luces`), 2 ADNS-3080 por SPI0 (spidev0.0 y 0.1, CE1 = GPIO 7; `flujo`, `flujo2`, `flujos`), herramientas `ayuda`, `archivos`, `buscar`, `ver`, `herramientas`, `nota`/`notas`. Python 3.13.5. IP en el hotspot: <ip-del-pi>. **Sin motores ni `drive`.**
- [V] 15 s conectado a `wss://…/ws`: WS abre en 278 ms; `GET /` total 124 ms desde este Mac. Llegan: 1 `rele`, 3 `info`, 287 `s` (**19 Hz**, ~170 B c/u, claves `temp_cpu, carga, wifi_dbm, luz, verde, rojo, camara`), 40 `oido` y 60 `cerebro` (el historial que el relé reenvía al conectar), 1 `imagen:camara` (~10 KB). 76 KB en 15 s.
- [I] RTT de un comando Unity → relé → Pi: no lo pude medir (mandar comandos pide clave). Ruta: Mac → Cloudflare → cloudflared en EDITH → relé → Cloudflare → hotspot del iPhone → Pi. Estimo 80-250 ms ida con jitter de hotspot. Se mide en la tarea T10.

## 1. Brechas concretas (archivo:línea)

### 1.1 Relé (`rele/servidor.mjs`): respuestas a lo que preguntaste

| Pregunta | Respuesta | Dónde |
|---|---|---|
| ¿Limita tamaño? | Sí: 1 MB por mensaje y **cierra la conexión** si se pasa (no descarta: corta). | `servidor.mjs:44`, `:123`, `:127`, `:146` |
| ¿Limita frecuencia? | No. Ningún throttle ni cola: cada línea se reenvía al bicho tal cual. | `:284-327` |
| ¿Clave por mensaje? | No. Una sola vez en el handshake (`?clave=` en la query), comparada con `timingSafeEqual`. Si el servidor no tiene `CLAVE_EQUIPO`, cualquiera manda. | `:199-203`, `:233` |
| Sin clave | Cada comando devuelve un `log warn` («falta la clave»). A 15 Hz = 15 avisos/s y el robot no se mueve aunque la app diga «conectado». | `:317-319` |
| Sin bicho | Igual: un `log warn` por comando. | `:322-325` |
| `{"cmd":"info"}` | Lo contesta el relé, no llega al bicho. | `:313-316` |
| Comandos `_…` | Se descartan (reservados). | `:321` |
| Latido | Ping cada 5 s; corta a los 15 s sin ningún cuadro. ClientWebSocket responde pings mientras su `ReceiveAsync` esté corriendo. | `:46`, `:174-181` |
| Lo que manda una web | **Las otras webs no lo ven**: bicho·dev no se entera de que Unity está manejando. | `:326` |
| Al conectar | El relé manda `rele{bicho,puedeMandar}`, la última `info`, 40 frases, 60 `cerebro` y la última imagen de cada nombre. | `:279-283` |
| Arbitraje | Ninguno: cerebro, bicho·dev y Unity pueden mandar `drive` a la vez. | `:326` |

### 1.2 Pi (`bicho/bichod.py`, `comandos.py`)

1. **P0 · Riesgo de borrar lo que aprendió el bicho.** El Pi corre 0.11.0, que escribió el cerebro; el repo tiene 0.5.0 (`bicho/version.json:2`). Si alguien hace `npm run release` desde el repo para instalar motores, **el bicho pierde cámara, flujo, luces de colores y herramientas**. Antes de cualquier release humano: bajar el código vivo con `{"cmd":"fuente"}` y commitearlo en `bicho/`. Otra opción: que lo instale el cerebro, que siempre parte de `fuente` (`cerebro/cerebro.mjs:518-540`).
2. **P0 · Cada `drive` genera una línea de log.** `bichod.py:350-354`: si `manejar()` devuelve texto lo publica como `info`; si devuelve `None` o `""`, publica «comando desconocido» como `warn`. No existe la respuesta silenciosa. A 15 Hz eso da 15 líneas/s hacia el relé y todas las webs. Además ensucia `comandoAlBicho` del cerebro, que junta los `log` durante 2,5 s para leer la respuesta de sus pruebas (`cerebro.mjs:170-195`).
3. **P0 · La latencia del manejo queda amarrada a la subida de la cámara.** `handle_cmd` hace `await send_log` (`bichod.py:354`) → `broadcast` → `ws.send` con lock y `drain` de hasta 2 s (`:258-265`). Si se está subiendo una imagen por el hotspot, el bucle que lee comandos del relé (`:692-697`) espera, y el siguiente `drive` también. Al hacer que `drive` no responda, esto desaparece.
4. `bichod.py` está en `PROTEGIDOS` del cerebro (`cerebro.mjs:519`): el parche del punto 2 solo lo puede instalar un humano, con un paquete armado desde `fuente`.
5. Watchdog: hoy no existe en el Pi. `manejar()` solo corre cuando llega un mensaje, así que el watchdog tiene que ir en un hilo propio del módulo de motores.
6. La prueba antes de activar importa `comandos` con `BICHO_SIMULAR=1` (`bichod.py:463-469`): el módulo de motores no puede tocar GPIO en ese modo, y su hilo tiene que ser `daemon`.
7. Si un aprendizaje reescribe `comandos.py`, el cerebro puede borrar `drive` sin querer. Conviene poner los motores en `motores.py` y agregarlo a `PROTEGIDOS` (`cerebro.mjs:519`), así el freno de seguridad no lo reescribe una IA sin revisión.

### 1.3 Unity (`handtracking/unity/BichoHands/Assets/BichoHands/Scripts/`)

| # | Brecha | Dónde | Efecto |
|---|---|---|---|
| U1 | `Url()` fuerza `ws://`, el puerto 8080 y `/ws`, y bota la ruta y la query | `BichoLink.cs:42-51` | No llega al relé ni lleva la clave (lo estás cambiando) |
| U2 | No interpreta `t:"rele"`: no sabe si `bicho:false` ni si `puedeMandar:false` | `BichoLink.cs:156-167` | Dice «conectado» y no se mueve nada; además manda 15 drive/s que vuelven como warn |
| U3 | No reconecta: un corte del hotspot o un reinicio del relé deja la app muerta | `BichoLink.cs:71-97` | La demo depende de apretar «Conectar» a mano |
| U4 | Decodifica UTF-8 por cada bloque de 16 KB (`GetString` por bloque) | `BichoLink.cs:101-107` | Se corrompen tildes y ñ cuando un carácter cae justo entre dos bloques (pasa en `cerebro` u `oido` largos) |
| U5 | `Disconnect()` llama a `SendNow` mientras `SendLoop` puede estar enviando: dos `SendAsync` a la vez lanzan excepción y el stop se pierde | `BichoLink.cs:64`, `:139-146` | El stop al salir no es confiable (lo cubre el watchdog del Pi) |
| U6 | La telemetría espera `dist_cm` e `imu`, que el bicho real no manda; no lee `carga`, `wifi_dbm`, `camara` ni flujo | `BichoLink.cs:13`, `BichoHud.cs:59` | El HUD muestra ceros falsos |
| U7 | El estabilizador cuenta cuadros de Unity, no del tracker: a 60 fps con el tracker a 30 fps, el mismo cuadro se empuja 2 veces y «3 cuadros» son 50 ms | `BichoHandController.cs:68-75` + `HandTrackingReceiver.cs:71-80` (no hay id de cuadro) | Gestos falsos al pasar de una forma a otra |
| U8 | El suavizado `Lerp(…, 0.6)` corre por cuadro: depende de los fps | `BichoHandController.cs:88-90` | Respuesta distinta en el Mac de la demo que en el de desarrollo |
| U9 | El centro del joystick es fijo (centro de la imagen) y se arma apenas aparece la palma | `BichoHandController.cs:81-84`, `:159-160` | Si la mano entra por arriba con la palma abierta: **avance a fondo al instante** |
| U10 | Sin rampa en L/R: pasa de 0 a 0,8 en un cuadro | `BichoHandController.cs:91-92` | Pico de corriente en 4 TT; con el Pi corto de voltaje (`contexto/estado.md`) puede reiniciarse |
| U11 | `gesto` se manda en cada cambio, también `palma` e `indice` | `BichoHandController.cs:122-129` | Un warn «comando desconocido» por cambio. El bicho no entiende `gesto`, pero sí `si`, `no`, `responder`, `verde`, `rojo` y `luz` |
| U12 | `servo` con pinza: el Pi no tiene servos todavía (PCA9685 #2 sin cablear) | `BichoHandController.cs:105-119` | Comandos que nadie atiende |
| U13 | HUD sin campo de clave, con la etiqueta «IP de la Raspberry Pi (puerto 8080)» | `BichoHud.cs:49-53` | Hay que cambiar texto y agregar la clave con máscara; nunca va a `PlayerPrefs` en claro dentro del repo ni se imprime |
| U14 | El gemelo integra lo pedido, no lo que hizo el robot | `VirtualBicho.cs:58` | No sirve como prueba de que el robot se movió |
| U15 | El receptor UDP solo escucha en loopback y el paquete no trae número de cuadro ni hora de captura | `HandTrackingReceiver.cs:38`, `hand_tracker.py:221` | No se puede medir la latencia de la cámara a la rueda |

### 1.4 Tracker y mock

- `hand_tracker.py:113-114`: captura a 1280x720, sin `CAP_PROP_BUFFERSIZE=1`. MediaPipe reescala igual, así que 640x480 baja la latencia y la CPU sin perder calidad del gesto [I].
- `hand_tracker.py:221`: falta `seq` y `cap_ts`.
- `mock_bicho.py:30-57`: no imita al bicho real. No responde con `log` a cada comando, no manda `t:rele` ni `puedeMandar`, no pide clave y entiende `drive`, que el real no entiende. Las pruebas contra el mock dan verde aunque contra el relé falle.
- `handtracking/README.md:5-8`, `:51-55` y `firmware/bicho_manos_esp32.ino`: describen Pi → UART → ESP32, que ya no corre. Hay que marcarlos como legado.

### 1.5 Mensajes que el HUD puede mostrar (ya llegan por el relé)

| Mensaje | Qué mostrar |
|---|---|
| `{"t":"rele","bicho":…,"puedeMandar":…}` | Banda de estado: «bicho conectado/caído» y «manejo habilitado/solo mirando». Con `bicho:false`, dejar de mandar drive |
| `{"t":"info",…}` | fw, `red`, `uptime`, `vuelta_atras` (el bicho volvió solo a la versión anterior) |
| `{"t":"s","d":{…}}` | temp_cpu, carga, wifi_dbm (barra de señal), luces, camara, flujo dx/dy; después `motor_l`, `motor_r` y `wd` |
| `{"t":"oido","texto","angulo","estado"}` | Subtítulo de lo que le dicen + **flecha alrededor del gemelo apuntando desde dónde le hablan** |
| `{"t":"cerebro","tipo","texto"}` | Cinta «Cerebro: pienso / respondo / aprendo …» (tipos vistos: `paso`, `responde`, `aprende`, `error`, `ignora`) |
| `{"t":"voz","b64",…}` | Opcional: reproducir el WAV de 16 kHz en Unity (plan B si falla el parlante) |
| `{"t":"imagen","nombre":"camara",…}` | **Fondo de teleoperación** (sección 2.5) |
| `{"t":"log"}` | Última línea, filtrando las de `drive` |

## 2. Calidad del gesto y del manejo

1. **Un cuadro del tracker, un paso.** `HandTrackingReceiver` expone `FrameId` (o el `seq` del paquete) y el controlador solo empuja el estabilizador y los filtros cuando el cuadro es nuevo (U7). Los «3 cuadros» pasan a ser 100 ms reales.
2. **One Euro filter** sobre `PalmCenter` (x, y) y sobre `PinchRatio`, con dt real del tracker (`t` del paquete). Valores para coordenadas 0..1: `minCutoff = 1.0 Hz`, `beta = 5`, `dCutoff = 1.0`, que se afinan en vivo con dos sliders del HUD. Reemplaza el `Lerp` (U8). En reposo quita el temblor y en movimiento rápido casi no agrega retraso. Son unas 30 líneas en C#, con un test EditMode: una señal escalón con ruido sale con menos de 0,01 de temblor en reposo.
3. **Zona neutra calibrada (embrague).** Al armar, la palma tiene que quedarse quieta 0,4 s (velocidad filtrada < 0,05/s). Esa posición queda como **centro** y el joystick se mide desde ahí (U9). Además:
   - zona muerta **radial**, no por eje;
   - desplazamiento dividido por el tamaño de la palma en la imagen (`|wrist - middleMcp|`), así la sensibilidad no cambia si la persona se acerca o se aleja de la cámara;
   - curva expo `v·|v|^0.6` para tener control fino cerca del centro;
   - recalibración: puño y otra vez palma.
   - Terminado cuando: entrar con la palma por el borde superior da L = R = 0 hasta que se queda quieta.
4. **Rampa (slew) en L/R** de 3,0/s al acelerar y frenado inmediato (U10). Va también del lado Pi (sección 3), así la protección no depende del cliente.
5. **Continuidad de manos.** MediaPipe cambia a veces la etiqueta Left/Right con una sola mano en cuadro. Si el lado cambia pero la palma está a menos de 0,1 de la anterior, se conserva el lado anterior.
6. **Gestos que el bicho ya entiende, sin esperar motores (U11).** Pulgar arriba → `{"cmd":"si"}` · victoria → `{"cmd":"responder"}` · puño de la mano auxiliar → `{"cmd":"no"}` · palma auxiliar 1 s → `{"cmd":"luz","blink":3}`. Palma e índice no se mandan. Así el hand tracking **funciona hoy con el bicho real**, solo con luces.
7. **Gesto «enseñar» (el cerebro aprende).**
   - **Grabar:** la mano auxiliar hace pulgar arriba sostenido 1 s → empieza a grabar (HUD en rojo «grabando»). Se maneja con la otra mano. Otro pulgar arriba 1 s → termina.
   - **Compactar:** Unity junta los `drive` en tramos `[l, r, ms]` (une los tramos parecidos; máximo 20 tramos y 15 s).
   - **Guardar en el Pi, sin LLM y en determinista:** `{"cmd":"rutina","nombre":"baile","pasos":[[0.6,0.6,800],[-0.5,0.5,600]]}`. `motores.py` la guarda con `nota` o en un json y la reproduce con `{"cmd":"rutina","nombre":"baile"}` en un hilo que respeta el watchdog. Cualquier `drive` o `stop` la cancela.
   - **Avisar al cerebro:** `{"t":"cerebro","tipo":"decir","texto":"bicho, aprendiste la rutina «baile»: cuando te pidan bailar, manda {\"cmd\":\"rutina\",\"nombre\":\"baile\"}","ts":<ms>}`. El relé lo deja pasar con clave (`servidor.mjs:297-305`) y el cerebro lo trata como frase escrita (`cerebro.mjs:137-138`; el `ts` tiene que tener menos de 20 s).
   - **Demo:** «se lo enseño con la mano, después se lo pido con la voz». Muestra el aprendizaje en vivo sin esperar 2 minutos a que la IA escriba código.
8. **Teleoperación: la cámara del bicho como fondo.**
   - **Pi:** `camara` con `fps` y `ancho` (5 fps a 320x240 con calidad 60 son unos 8 KB por cuadro, ~40 KB/s de subida). Lo puede aprender el cerebro («bicho, aprende a mandar la cámara a 5 cuadros por segundo en 320x240 cuando te pidan camara con fps»). `salida.py` hoy pide no más de 2/s: hay que subir ese límite en el texto, o dejar 2 fps como plan B.
   - **Unity:** `BichoLink` deja la última `imagen` en una ranura «último gana». En el hilo principal, `Convert.FromBase64String` → `Texture2D.LoadImage` (una textura reutilizada) → `RawImage` a pantalla completa detrás del HUD. Encima van el esqueleto de la mano, las barras L/R y la **edad del cuadro** (ms desde que llegó; en rojo si pasa de 1 s).
   - **Modos:** `Tab` cambia entre «vista del bicho» y «gemelo».
   - **Al conectar con clave:** mandar `{"cmd":"camara","on":true}`. Los parámetros exactos se confirman con `{"cmd":"ayuda"}` [I].
9. **Gemelo honesto (U14).** Con el flujo óptico encendido (`flujos` on), el gemelo se mueve con dx/dy de los dos ADNS-3080, que están separados 200 mm (`diseno/README.md`). La diferencia entre los dos da el giro. Con esto el gemelo muestra lo que el robot hizo de verdad, y la diferencia con lo pedido delata patinaje o un choque (estado `atascado` de `lenguaje.json`).

## 3. Motores en el Pi

### 3.1 Qué hay

- [V] **Repo y esquemático:** 4 motores TT 48:1 a 3-6 V, que piden 0,15 A libres y 1,5 A trabados (`esquematico-conexiones.pdf` p. 2-3). TB6612FNG ×2 en el esquemático; en el inventario figuran ~6 «probables TB6612». PCA9685 ×2 (0x40 motores, 0x41 servos) y 1 L298N. LM2596 ×1 confirmado; el esquemático pide 2. Pack 2S 18650 (6,0-8,4 V). UPS LX-2BUPS para la lógica. Fuentes: `diseno/fuentes/inventario_*.tsv`, `bicho/lenguaje.json:23-30`.
- [V] **Pines ocupados en 0.11.0:**
  - GPIO 17, 27 y 22: luces;
  - SPI0: GPIO 8, 7, 9, 10 y 11 (dos ADNS-3080);
  - CSI: cámara;
  - USB: ReSpeaker.
- [V] **Choque con el esquemático:** el esquemático asignaba GPIO 22 a MOTOR_OFF y GPIO 17/27 al reset del ESP32. Hoy esos pines son luces. El esquemático asume ESP32 + UART, que ya no existe.
- [I] **I2C1 (GPIO 2/3):** se ve libre, pero no sé si está habilitado en `config.txt`. Se confirma con `{"cmd":"diag"}` (el cerebro tiene `inspeccionar_hardware`).

### 3.2 Recomendación para esta noche: opción A, TB6612 directo a GPIO (sin I2C)

Cero dependencias nuevas: `gpiozero` ya lo usa `luz.py`. No hay que habilitar I2C ni reiniciar el Pi. Cada lado tiene un TB6612 con sus canales A y B en paralelo (las entradas se puentean). Así cada motor tiene su canal de 1,2 A y solo se usan 6 GPIO + STBY.

| Señal | GPIO (pin físico) | A |
|---|---|---|
| PWM izquierdo | GPIO 12 (32) | TB6612 #1 PWMA + PWMB |
| IN1 izquierdo | GPIO 5 (29) | TB6612 #1 AIN1 + BIN1 |
| IN2 izquierdo | GPIO 6 (31) | TB6612 #1 AIN2 + BIN2 |
| PWM derecho | GPIO 13 (33) | TB6612 #2 PWMA + PWMB |
| IN1 derecho | GPIO 16 (36) | TB6612 #2 AIN1 + BIN1 |
| IN2 derecho | GPIO 26 (37) | TB6612 #2 AIN2 + BIN2 |
| STBY (los dos) | GPIO 25 (22) | STBY #1 y #2, con 10 k a GND |
| VCC lógica | pin 1 o 17 (3V3) | VCC #1 y #2 |
| VM | LM2596 ajustado a 6,0 V desde el pack 2S | VM #1 y #2 |
| GND | GND común en un solo punto | Pi, pack, LM2596, TB6612 |

Condiciones del cableado:

- **Nunca VM desde los 5 V del Pi:** ya está corto de voltaje.
- Verificar con `vcgencmd get_throttled` = `0x0` mientras arrancan los 4 motores.
- El orden de pines del TB6612 cambia según el fabricante: leer la serigrafía (`esquematico` p. 4).

**Opción B (después de la demo, para el brazo):** PCA9685 #1 en I2C1, según la tabla del esquemático (CH0-11). STBY en GPIO 25 y OE (MOTOR_OFF) en GPIO 24, ya no en el 22. Pide habilitar I2C y `smbus2`, y deja el PCA #2 (0x41) listo para los servos del brazo y la pinza.

### 3.3 `motores.py` (módulo nuevo) + gancho en `comandos.py`

Para que lo instale Carlos o el cerebro. Si lo instala el cerebro, se le pasa este archivo tal cual con «bicho, aprende a manejar tus ruedas: instala este motores.py y agrega drive/stop/motores/rutina en comandos.py sin borrar nada de lo que ya sabes».

```python
"""
Tracción del bicho: 4 motores TT con 2 TB6612FNG (uno por lado, canales A y B en paralelo).

  {"cmd":"drive","l":0.5,"r":0.5,"de":"manos"}  -1..1 por lado. Hay que repetirlo (5-30 Hz): si pasan
                                                 WATCHDOG_S sin drive, frena solo.
  {"cmd":"stop"}                                 frena ya. Lo puede mandar cualquiera y siempre gana.
  {"cmd":"motores"}                              estado, pines y si son reales o simulados.
  {"cmd":"rutina","nombre":"baile","pasos":[[l,r,ms],...]}  guarda; sin "pasos" la reproduce.

Seguridad: watchdog en un hilo propio, rampa al acelerar, tope de potencia, STBY en LOW al arrancar y al
salir. Con BICHO_SIMULAR=1 (la prueba antes de instalar) no toca ningún pin.
"""
from __future__ import annotations

import atexit, json, os, threading, time
from pathlib import Path

PIN = {"pwm_l": 12, "in1_l": 5, "in2_l": 6, "pwm_r": 13, "in1_r": 16, "in2_r": 26, "stby": 25}
INVERTIR = {"l": False, "r": False}  # si un lado gira al revés
WATCHDOG_S = float(os.environ.get("BICHO_WATCHDOG_S", "0.5"))
TOPE = float(os.environ.get("BICHO_TOPE", "0.8"))
RAMPA_POR_S = 3.0  # de 0 a 1 en ~0,33 s; frenar es inmediato
DUENO_S = 1.0      # quien manda drive "es dueño" del manejo por 1 s (stop gana siempre)
RUTINAS = Path(os.environ.get("BICHO_HOME", str(Path.home() / ".bicho"))) / "rutinas.json"

real, error, _d = False, None, {}
if os.environ.get("BICHO_SIMULAR") != "1":
    try:
        from gpiozero import DigitalOutputDevice, PWMOutputDevice
        _d = {k: PWMOutputDevice(p, frequency=500) if k.startswith("pwm") else DigitalOutputDevice(p)
              for k, p in PIN.items()}
        real = True
    except Exception as e:  # sin GPIO o pin ocupado: queda simulado
        error, _d = repr(e), {}

_lock = threading.Lock()
_obj = {"l": 0.0, "r": 0.0}   # lo pedido
_act = {"l": 0.0, "r": 0.0}   # lo aplicado (con rampa)
_ultimo = 0.0
_dueno, _dueno_t = None, 0.0
_wd = 0
_rutina_id = 0


def _avisar(msg: str, lvl: str = "warn") -> None:
    try:
        import salida
        salida.emitir({"t": "log", "lvl": lvl, "msg": msg})
    except Exception:
        pass


def _aplicar(lado: str, v: float) -> None:
    if not real:
        return
    v = -v if INVERTIR[lado] else v
    a, b, p = _d[f"in1_{lado}"], _d[f"in2_{lado}"], _d[f"pwm_{lado}"]
    if abs(v) < 0.02:
        a.on(); b.on(); p.value = 0          # freno corto (IN1=IN2=H)
    else:
        (a.on(), b.off()) if v > 0 else (a.off(), b.on())
        p.value = min(abs(v), 1.0)


def _parar_ya() -> None:
    _obj.update(l=0.0, r=0.0); _act.update(l=0.0, r=0.0)
    _aplicar("l", 0.0); _aplicar("r", 0.0)
    if real:
        _d["stby"].off()


def _bucle() -> None:
    global _wd
    t = time.monotonic()
    while True:
        time.sleep(0.02)
        ahora = time.monotonic(); dt, t = ahora - t, ahora
        aviso = False
        with _lock:
            if (_obj["l"] or _obj["r"]) and ahora - _ultimo > WATCHDOG_S:
                _parar_ya(); _wd += 1; aviso = True
            else:
                paso = RAMPA_POR_S * dt
                for k in ("l", "r"):
                    antes = _act[k]
                    if _obj[k] == 0.0:
                        _act[k] = 0.0
                    else:
                        _act[k] += max(-paso, min(paso, _obj[k] - _act[k]))
                    if _act[k] != antes:
                        _aplicar(k, _act[k])
        if aviso:
            _avisar(f"watchdog: {WATCHDOG_S:g} s sin drive, frené")


def drive(l: float, r: float, de: str = "?") -> bool:
    global _ultimo, _dueno, _dueno_t, _rutina_id
    ahora = time.monotonic()
    with _lock:
        if _dueno not in (None, de) and ahora - _dueno_t < DUENO_S:
            return False                       # otro cliente está manejando
        _dueno, _dueno_t, _ultimo = de, ahora, ahora
        if de != "rutina":
            _rutina_id += 1                   # una mano cancela la rutina en curso
        _obj["l"] = max(-1.0, min(1.0, float(l))) * TOPE
        _obj["r"] = max(-1.0, min(1.0, float(r))) * TOPE
        if real and (_obj["l"] or _obj["r"]):
            _d["stby"].on()
    return True


def stop() -> None:
    global _dueno, _rutina_id
    with _lock:
        _rutina_id += 1; _dueno = None
        _parar_ya()


def estado() -> dict:
    """Para sensores.leer(): así bicho·dev grafica los motores y el Simulador los puede animar."""
    return {"motor_l": round(_act["l"], 2), "motor_r": round(_act["r"], 2), "motor_wd": _wd}


def rutina(nombre: str, pasos: list | None = None) -> str:
    global _rutina_id
    todas = json.loads(RUTINAS.read_text()) if RUTINAS.exists() else {}
    if pasos is not None:
        pasos = [[float(l), float(r), max(50, min(int(ms), 5000))] for l, r, ms in pasos[:20]]
        todas[nombre] = pasos
        RUTINAS.parent.mkdir(parents=True, exist_ok=True)
        RUTINAS.write_text(json.dumps(todas))
        return f"rutina {nombre} guardada ({len(pasos)} pasos)"
    if nombre not in todas:
        return f"no conozco la rutina {nombre}"
    with _lock:
        _rutina_id += 1; mi = _rutina_id

    def correr() -> None:
        for l, r, ms in todas[nombre]:
            fin = time.monotonic() + ms / 1000
            while time.monotonic() < fin:
                if _rutina_id != mi:
                    return
                drive(l, r, "rutina")            # se repite a 20 Hz: el watchdog sigue protegiendo
                time.sleep(0.05)
        if _rutina_id == mi:
            stop()

    threading.Thread(target=correr, daemon=True, name=f"rutina-{nombre}").start()
    return f"haciendo la rutina {nombre}"


threading.Thread(target=_bucle, daemon=True, name="motores").start()
atexit.register(stop)
```

Gancho en `comandos.py`, que **se agrega** al `manejar()` vivo de 0.11.0 sin reemplazarlo:

```python
import json, motores

    if cmd == "drive":
        motores.drive(c.get("l", 0), c.get("r", 0), str(c.get("de", "?")))
        return ""            # silencioso: requiere el parche de bichod.py de abajo
    if cmd == "stop":
        motores.stop(); return "stop"
    if cmd == "motores":
        return json.dumps({"real": motores.real, "error": motores.error, "pines": motores.PIN, **motores.estado()})
    if cmd == "rutina":
        return motores.rutina(str(c.get("nombre", "")), c.get("pasos"))
```

En `sensores.py`, dentro de `leer()`, agregar `d.update(motores.estado())`.

Parche de `bichod.py:350-354`. Es núcleo, así que lo instala un humano con un paquete armado desde `fuente`:

```python
            out = comandos.manejar(c)
        ...
        if out is None:
            await send_log(f"comando desconocido: {text[:120]}", "warn")
        elif out:
            await send_log(out)
        # "" = comando atendido sin respuesta (drive a 15-30 Hz)
```

Plan B si no alcanza a entrar el parche de `bichod`: `drive` devuelve `""` igual. Sale un warn por comando, que molesta pero no rompe nada, y Unity baja a 10 Hz.

Prueba de aceptación, con las ruedas en el aire:

1. `{"cmd":"motores"}` → `real:true`.
2. `drive 0.5/0.5` repetido → avanzan los dos lados.
3. `drive 0.5/-0.5` → gira a la derecha.
4. Cerrar Unity → paran en ≤ 0,6 s (filmado).
5. `stop` → paran en < 0,1 s.
6. `get_throttled` = `0x0`.

## 4. Tareas priorizadas (30-90 min cada una)

Orden pensado para que a las 20:00 el hand tracking ya mueva algo real (luces) y a las 02:00 mueva las ruedas.

| # | Pri | Tarea | Quién | Min | Terminado cuando |
|---|---|---|---|---|---|
| T1 | P0 | Bajar el código vivo 0.11.0 con `{"cmd":"fuente"}` y commitearlo en `bicho/` (rama `dev`) | sesión principal o Carlos | 30 | `bicho/version.json` = 0.11.0; `git diff` revisado; ningún release posterior parte de 0.5.0 |
| T2 | P0 | BichoLink al relé (en curso) + leer `t:rele` (bicho, puedeMandar) + no mandar drive si alguno es falso + reconexión con espera creciente + decodificar UTF-8 con `MemoryStream` (U1-U5) | sesión principal | 60 | Unity con `wss://…/ws?clave=` muestra «bicho ✓ · manejo ✓»; con clave mala muestra «solo mirando» y no manda nada; al reiniciar el relé reconecta sola en < 10 s |
| T3 | P0 | Gestos → comandos que el bicho ya entiende (`si`, `no`, `responder`, `luz`) y sacar `gesto` palma/índice (U11) | XR | 30 | Pulgar arriba frente al Mac prende la luz verde del bicho real; en bicho·dev se ve `verde=true` |
| T4 | P0 | Cablear 2 TB6612 al Pi según 3.2 (VM 6 V del LM2596, GND común) | Carlos / Renate | 60-90 | Con multímetro: VM = 6,0 V; un script de 10 líneas con gpiozero mueve cada lado en ambos sentidos; `get_throttled` = `0x0` |
| T5 | P0 | Instalar `motores.py` + gancho + `sensores` (por el cerebro o por paquete desde `fuente`) y el parche silencioso de `bichod` | Carlos (o el cerebro, más el parche humano) | 60 | Pasa la prueba de aceptación de 3.3; la versión nueva conserva cámara, flujo y luces (`ayuda` las lista) |
| T6 | P1 | Calidad del gesto: id de cuadro (U7) + One Euro + embrague con centro calibrado + zona radial normalizada por palma + expo + rampa (U8-U10) | XR | 90 | ≥ 5 tests EditMode nuevos en verde (filtro, embrague, rampa, estabilizador por cuadro); en `--fake` entrar con la palma por el borde no mueve nada |
| T7 | P1 | HUD vivo: barra de estado del relé, telemetría real (temp, carga, wifi_dbm, motor_l/r, wd), subtítulo de `oido` con flecha de ángulo en el gemelo, cinta del `cerebro` (U6, U13) | XR | 60 | Al decir «hola bicho» aparece el texto en Unity con la flecha apuntando hacia quien habló; campo de clave con máscara, que no se imprime |
| T8 | P1 | Teleoperación: `camara` a 5 fps 320x240 en el Pi + fondo `RawImage` en Unity con la edad del cuadro + `Tab` vista/gemelo | cerebro aprende (Pi) + XR | 90 | ≥ 4 fps en Unity; un cronómetro filmado por la cámara del bicho llega con < 700 ms de retraso |
| T9 | P1 | Eco de motores en `s` (`motor_l`, `motor_r`) → bicho·dev lo grafica solo; el Simulador anima el cuerpo con esos valores | Pi: T5 · web: dueño de bicho·dev | 45 | Maniobrando desde Unity, bicho·dev (otra pestaña, otra red) muestra la curva y el bicho 3D se mueve igual |
| T10 | P1 | Medir latencia: 100 `{"cmd":"hola"}` cronometrando la respuesta `log`, por el relé y directo (`ws://<ip-del-pi>:8080/ws` con el Mac en el mismo hotspot) | XR | 30 | Tabla p50/p95 de los dos caminos; decisión anotada del modo de la demo (directo si p95 del relé > 300 ms) |
| T11 | P1 | Mock realista: `log` por comando, `t:rele` con `puedeMandar`, warn en lo desconocido, y modo `--rele http://127.0.0.1:8787` que se conecta como bichod al relé local (`node rele/servidor.mjs`) | XR | 45 | Unity probada de punta a punta sin hardware contra el relé real local, con clave buena y mala |
| T12 | P2 | Gesto «enseñar»: grabar con pulgar sostenido, compactar a tramos, `{"cmd":"rutina"}` + aviso al cerebro con `tipo:"decir"` | XR + Pi (`motores.rutina`) | 90 | Se graba «baile» con la mano, alguien dice «bicho, baila» y el robot la repite; un `drive` de la mano la corta |
| T13 | P2 | Arbitraje: Unity manda `"de":"manos"`, el cerebro `"de":"cerebro"`; `stop` gana siempre; bicho·dev con botón STOP grande | XR + web | 45 | Con dos clientes manejando, solo obedece al dueño vigente; el STOP de bicho·dev frena a cualquiera |
| T14 | P2 | Gemelo con odometría de los ADNS-3080 (dx/dy de `flujos`) en vez de lo pedido (U14) | XR | 90 | Al empujar el robot con la mano (sin motores), el gemelo se mueve y gira en la misma dirección |
| T15 | P2 | Docs: `PROTOCOLO.md` (drive, stop, motores, rutina, de), `handtracking/README.md` con el diagrama Pi + relé, `.ino` marcado como legado | XR | 30 | Ninguna mención a UART/ESP32 como camino vigente |
| T16 | P2 | Guion de demo del hand tracking + plan B (modo directo por hotspot; si no hay motores: luces + gemelo + cámara) en `marca/PITCH.md` | XR + pitch | 30 | Ensayo cronometrado < 60 s con el plan B probado una vez |

## 5. Riesgos para la demo

- Que alguien instale un release desde el repo 0.5.0 y borre lo aprendido (T1 lo cierra).
- Que el Pi se reinicie por caída de voltaje al arrancar los motores. Lo previenen la fuente separada, la rampa y el `TOPE` 0.8.
- Que la URL del túnel quick de Cloudflare cambie si se reinicia cloudflared. Unity tiene que guardar la URL editable y probar `GET /` antes de conectar.
- Que dos controladores manejen a la vez (T13). Mientras tanto: apagar el `aprender` del cerebro durante la demo de manos.
- Que la clave se filtre: va en la query de la URL. No imprimirla en el HUD ni en logs, y no commitear `PlayerPrefs` ni un `.env`.

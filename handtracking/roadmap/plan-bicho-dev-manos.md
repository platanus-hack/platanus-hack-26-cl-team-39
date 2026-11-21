# Plan · Manos en bicho·dev (hand tracking en el navegador, sin Unity)

NEXO · Desarrollador Web · 21-nov-2026, 16:10 (Chile) · Solo análisis y diseño: no se tocó el repo.
Repo leído en `dev` @ `99f11ae` (origin/dev). [V] = verificado con comando o lectura; [I] = inferido.

## 0. Lo que encontré (y corrige el brief)

- [V] Relé vivo 16:08: `GET /` → `{"rele":true,"bicho":true,"espectadores":5,"fw":"0.11.0"}`. El fw ya va en **0.11.0** (el brief decía 0.10.0; el repo, 0.5.0).
- [V] `bicho/comandos.py` no conoce `drive`, `stop`, `servo` ni `gesto`. `bichod.py:354` responde a cada comando desconocido con un `log` warn **que el relé reparte a todas las webs**. Mandar `drive` a 15 Hz hoy = 15 avisos por segundo en cada consola (y en lo que lea el cerebro). **Hay que mandar al bicho solo cuando lo entienda.**
- [V] El relé (`rele/servidor.mjs:280-330`) **no reenvía a las otras webs lo que manda una web**: solo lo pasa al bicho. Las excepciones son `{"t":"cerebro"}` (se reparte y se guarda) y `{"t":"voz"}` (se reparte). Si no hay bicho, contesta «El bicho no está conectado al relé» y descarta el comando.
- [V] Hay cambios **sin commit** en `handtracking/unity/.../BichoLink.cs`, `BichoHud.cs`, `BichoHandsApp.cs` y los tests: BichoLink ya arma `wss://<relé>/ws?clave=…` (test `Url_AgregaPuertoYRuta`). Otra terminal está llevando Unity al relé ahora; el brief («SOLO directo») quedó viejo. No pisar esos archivos.
- [V] bicho·dev: Vite 6 + React 18 + three 0.170, sin runner de tests. Node local v26.12.1 (corre `.ts` con `node` directo, sin dependencias).
- [V] La web habla con el relé por `WifiLink` (`web/src/lib/links.ts:55`), con la clave del equipo guardada en localStorage (`clave` en `web/src/lib/inventario.ts:53`, se pone en Equipo → Inventario). `App.tsx` tiene `send()` y recibe todo por `onMessage`. El Simulador (`web/src/sim/Simulador.tsx`) **no recibe ni el link ni `send`**: hoy es una isla.
- [V] `escena.ts` ya tiene el modelo de tracción que hace falta: `pose {x,z,th,v,w}`, `conducir(dt)` (línea ~739), ruedas que giran con `p.v - lado * p.w * MEDIA_VIA` (MEDIA_VIA 0,098 m, RUEDA 0,033 m). Basta con una fuente de `v,w` externa.
- [V] Últimos 12 commits en `web/src/sim` y `App.tsx`: 7 de Guty (`gutybv`, el último hace 2 h), 5 de TesslaRay. Guty es dueño de bicho·dev (`contexto/estado.md`).

## 1. Sección «Manos» en bicho·dev

### Dependencia y modelo

| Qué | Valor | Fuente |
|---|---|---|
| Paquete | `@mediapipe/tasks-vision` **`1.2.3` fijo, sin `^`** | [V] `npm view`: última estable, publicada el 11-nov-2026; las `1.3.0-rc.*` son diarias, no usarlas |
| API | `FilesetResolver.forVisionTasks(base)` → `HandLandmarker.createFromOptions(fs, {baseOptions:{modelAssetPath, delegate:'GPU'}, runningMode:'VIDEO', numHands:2, minHandDetectionConfidence:0.5, minHandPresenceConfidence:0.5, minTrackingConfidence:0.5})` → `detectForVideo(src, ts)` → `{landmarks, worldLandmarks, handedness}` | [V] `vision.d.ts` del paquete 1.2.3 (líneas 819, 967-1090). Mismos umbrales que `hand_tracker.py:57-60` |
| wasm | `vision_wasm_internal.{js,wasm}`: **14,7 MB** (más 336 KB de JS). Se sirve desde la misma web (copiar a `web/public/manos/wasm/`) para no depender de jsDelivr en el escenario | [V] `npm pack` |
| Modelo | `hand_landmarker.task` float16 v1, **7,8 MB**, de `storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/` (fijar `/1/`, no `/latest/`). Copiar a `web/public/manos/` (Apache 2.0, se puede publicar) | [V] `curl -I` 200, content-length 7819105 |
| Plan B de versión | si 1.2.3 falla al cargar: `0.10.21` (feb-2025, misma API) | [I] |

Total que baja el navegador la primera vez: ~23 MB. Se carga **solo al abrir Manos** (import dinámico), no en la carga de bicho·dev.

### Webcam y lateralidad (lo que más fácil sale mal)

- `getUserMedia({video:{width:640,height:480,facingMode:'user'}, audio:false})`, `<video playsInline muted>`.
- `hand_tracker.py` **espeja el cuadro antes** de MediaPipe y usa la etiqueta tal cual (líneas 197-219). Para que el clasificador y el joystick den exactamente lo mismo que en Unity: dibujar el video espejado en un canvas de 640×480 (`ctx.scale(-1,1)`) y pasarle **ese canvas** a `detectForVideo`. Así `x` de la palma, `Left/Right` y los puntos métricos quedan iguales a lo que recibía Unity. Costo: un `drawImage` por cuadro.
- Prueba de terminado: levantar la mano derecha → la UI dice «derecha»; mover la palma a la derecha de la pantalla → `turn > 0`.

### Clasificador portado (TS puro, sin DOM)

`web/src/manos/gestos.ts`, traducción línea a línea de `GestureRecognizer.cs` (118 líneas) y de la matemática pura de `BichoHandController.cs`:
- `PINCH_ON 0.33`, `PINCH_OFF 0.48`, `MAX_BEND_DEG 75`, `bend()`, `fingerExtended()`, `thumbExtended()`, `classify(hand, wasPinching)`, `thumbPointsUp()` (usa puntos de imagen), `GestureStabilizer` de 3 cuadros.
- `joystick(palm, dead=0.07, full=0.25)`, `axis()`, `mix()` (tanque normalizado a ±1), `palmCenter()` (promedio de 0, 5, 9, 17 en imagen).
- Nombres de gesto iguales a `GestureName`: `palma | puno | indice | victoria | pulgar_arriba | pinza`.
- Pruebas: `web/scripts/probar-gestos.ts` porta los 10 tests de `BichoHandsTests.cs` con la mano real de `HandSamples.cs` (IMG_7996) y `tracker/muestras/mano_abierta_IMG_7996.json`. Corre con `node web/scripts/probar-gestos.ts` (Node 26 ejecuta TS sin dependencias). Sin vitest: no se agrega nada al `package.json` salvo MediaPipe.

### Control (mismas reglas que Unity)

`web/src/manos/control.ts`, por cuadro de MediaPipe (≈30 fps):
- Mano de manejo derecha (configurable). **Armado** = palma abierta o índice, sin STOP trabado, mano presente.
- `thr,turn = joystick(palma) × 0.8` (× 0.4 con índice = modo fino). Suavizado 0,6 al acelerar, **0 al desarmar** (frena en seco).
- **Hombre muerto:** sin cuadro de mano por 0,3 s → `l=r=0` y un `stop`. También si la pestaña se oculta (`visibilitychange`) o la cámara se corta (`track.onended`).
- **Envío a ≤15 Hz** con temporizador propio (no atado al FPS): si se mueve, `{"cmd":"drive","l":0.42,"r":0.31}` (2 decimales); al pasar a quieto, un `{"cmd":"stop"}`; armado y quieto, `drive 0,0` como latido para el watchdog. Si `ws.bufferedAmount > 4 KB`, se salta el drive (último gana), nunca el `stop`.
- `{"cmd":"gesto","g","mano"}` solo cuando cambia el gesto estable.
- Pinza izquierda → `servo` 0/1 con los mismos mapeos que Unity; **apagado por defecto** (el bicho no tiene servos cableados) [I].
- **Botón STOP** grande y rojo + tecla Espacio: traba (otro clic la suelta), manda `stop` crítico y deja `l=r=0`.

### Adónde va cada comando (decisión de diseño)

Un interruptor «Mandar al bicho» (apagado por defecto):
- **Apagado** (default, hoy): los `drive/stop` solo mueven el gemelo del Simulador. Al relé va únicamente `{"t":"manos", ...}` si el puente de §3 existe. No hay spam de «comando desconocido».
- **Encendido:** además se mandan por `send()` al relé. Se puede encender solo si `info` del bicho anuncia que entiende `drive` (propuesta a Carlos: que `info` traiga `"comandos":["luz","drive","stop",…]`; mientras no exista, el interruptor queda manual con aviso «el bicho todavía no tiene motores»).
- Requiere clave del equipo (ya resuelto en `WifiLink`); si el relé la rechaza se reutiliza el aviso que ya existe en `App.tsx:416-427`.

### Dónde vive en la UI

Dentro del Simulador, no en una vista aparte: para el jurado lo fuerte es **una sola pantalla** con la cámara y el bicho 3D obedeciendo. Botón «Manos» en el toolbar del Simulador que abre una tarjeta `sim-manos` (video espejado con el esqueleto dibujado encima, gesto actual por mano, barras L/R, FPS de MediaPipe, interruptor «Mandar al bicho», STOP). Con Manos cerrado no se carga nada.

### Archivos a crear / tocar

| Archivo | Nuevo/toca | Tamaño aprox. | Qué |
|---|---|---|---|
| `web/package.json` + lock | toca | +1 línea | `"@mediapipe/tasks-vision": "1.2.3"` |
| `web/public/manos/hand_landmarker.task` | nuevo | 7,8 MB | modelo fijo v1 |
| `web/public/manos/wasm/vision_wasm_internal.{js,wasm}` | nuevo | 15 MB | copiados de `node_modules` por un script (`npm run manos:wasm`) o a mano una vez |
| `web/src/manos/gestos.ts` | nuevo | ~170 líneas | clasificador + estabilizador + joystick/mix (puro) |
| `web/src/manos/tracker.ts` | nuevo | ~120 | cámara, canvas espejado, HandLandmarker, `requestVideoFrameCallback`, GPU→CPU si falla |
| `web/src/manos/control.ts` | nuevo | ~150 | armado, suavizado, hombre muerto, 15 Hz, STOP, salida `{l,r,gesto…}` |
| `web/src/manos/bus.ts` | nuevo | ~30 | `EventTarget` con `mando` (l, r, fuente: 'web' \| 'unity') y `manos` (puntos para dibujar) |
| `web/src/manos/PanelManos.tsx` + `manos.css` | nuevo | ~200 + ~80 | tarjeta con video, esqueleto en canvas 2D, HUD, STOP |
| `web/scripts/probar-gestos.ts` | nuevo | ~90 | los 10 tests de Unity |
| `web/src/sim/Simulador.tsx` | **toca (de Guty)** | +25 | botón Manos, `lazy(PanelManos)`, recibe `send` y `puedeMandar` como props |
| `web/src/sim/escena.ts` | **toca (de Guty)** | +40 | `setMando(l,r)`, rama en `conducir()`, mano fantasma opcional |
| `web/src/App.tsx` | **toca (de Guty)** | +6 | pasa `send`/estado del link a `<Simulador>`; en `onMessage`, `t:'manos'` → `bus` |

Lo nuevo vive todo en `web/src/manos/`: los tres archivos de Guty se tocan en ~70 líneas en total.

## 2. Simulador como gemelo digital

- `escena.ts`: `setMando(l, r)` guarda `{l, r, t: this.t}`. En `conducir(dt)`, antes del `switch`: si `this.t - mando.t < 0.3` → `v = (l + r)/2 · VMAX` (VMAX ≈ 0,35 m/s, como `plantarse`) y `w = (l - r)/(2·MEDIA_VIA) · k`, **ignorando** `e.cuerpo`. Se reutilizan el suavizado `suave()`, los límites del patio, el huerto y las ruedas. Si pasan 0,3 s sin mando, frena (hombre muerto también en el gemelo) y a los 1,5 s vuelve a obedecer su estado.
- El signo de `w`: `th` crece hacia +x (`x += v·sin th`). Hay que confirmarlo a ojo con la prueba «palma a la derecha → gira a la derecha visto desde la cámara por defecto»; si sale al revés, se invierte una constante. [I]
- Mientras maneja la mano, el estado del idioma pasa a uno existente de «manejo» (si no hay, se muestra «Lo manejas tú» en `sim-now`), y la cámara sigue al bicho como en `seguirConCamara`.
- **Mostrar la mano**, dos niveles:
  1. (obligatorio) esqueleto 2D sobre el video en la tarjeta, con los huesos de `LM.Bones` y color por gesto.
  2. (opcional, si sobra tiempo) mano fantasma en la escena: 21 esferas + líneas con `worldLandmarks` × 3, flotando sobre el bicho, que se pone roja con puño/STOP. Un `InstancedMesh` de 21 instancias y un `LineSegments`: barato.
- El gemelo obedece igual venga el mando de la web o de Unity por el relé (§3): lo único que cambia es la fuente en el `bus`.
- Cuando el bicho real tenga motores: el gemelo sigue moviéndose junto al real (útil en la demo para mostrar qué se le mandó).
- Plan B del GLB: el robot real (`diseno/modelos/bicho_V*.glb`, 4,4-4,6 MB [V]) **no es prerrequisito**. El gemelo usa el modelo a mano de `escena.ts`. Si alguien integra el GLB (paso 1 de `INTEGRAR_EN_BICHO_DEV.md`), las ruedas `W_*` (`userData.rueda`) se enganchan a la misma `pose` y no cambia nada de Manos.

## 3. Puente opcional: Unity y la web en el mismo relé

Hoy el relé no le cuenta a una web lo que manda otra (§0). Dos caminos:

**A (recomendado, 6-8 líneas en `rele/servidor.mjs`):** un tipo nuevo `{"t":"manos", ...}` tratado igual que `voz`: si la conexión tiene clave, `aLasWebs(l)`, sin guardar. El que maneja (Unity o la web) publica a ~10 Hz:
```json
{"t":"manos","de":"unity","l":0.42,"r":0.31,"g":{"der":"palma","izq":"ninguno"},"armado":true,"stop":false,"pts":[...63 números de la mano de manejo, 3 decimales...]}
```
`pts` es opcional (≈450 bytes; sin él son ~120). Las webs espectadoras lo meten al `bus` → el gemelo se mueve y se dibuja la mano aunque nadie en esa web tenga cámara. El cerebro también lo recibe y puede reaccionar a un `pulgar_arriba` («¿te gusta?» → responde): conexión con la IA sin que el bicho entienda gestos todavía.
- Cambio en Unity: que `BichoHandController` publique ese `t:manos` además de (o en vez de) `drive` mientras el bicho no tenga motores. Coordinar con quien tiene `BichoLink.cs` sin commit.
- El relé corre en EDITH: cambiarlo exige reiniciarlo, y eso es de Cristian/TesslaRay. Si se reinicia, el túnel quick de cloudflare puede cambiar de URL [I] y habría que actualizar `web/src/lib/rele.json`.

**B (sin tocar el relé):** que Unity y la web no se vean entre sí; cada una maneja su propio gemelo. Es el plan B si nadie puede reiniciar el relé antes de las 8:30.

Regla para que no se peleen: **un solo piloto a la vez**. El relé no arbitra; lo hace la UI: si una web recibe `t:manos` de otra fuente con `armado:true` en los últimos 2 s, su panel muestra «Maneja Unity» y no manda `drive` (sí puede mandar STOP, que siempre gana).

## 4. Riesgos

| Riesgo | Prob./impacto | Mitigación |
|---|---|---|
| **Permiso de cámara.** `getUserMedia` exige contexto seguro: sirve en `https://*.trycloudflare.com` y en `http://localhost`; **falla** en `http://<IP del Mac>:5173` | Media / alto | Demo en `localhost` o en el túnel https. Detectar `!isSecureContext` y mostrar el porqué en vez de un error mudo. Si se mete en un iframe, `allow="camera"` |
| Cada URL nueva del túnel pide el permiso de nuevo; si alguien tocó «Bloquear», Chrome no vuelve a preguntar | Media / medio | Ensayar en el notebook de la demo con la URL final; texto de ayuda «candado → Cámara → Permitir». Plan B: video pregrabado (`<video src>` en vez de webcam, igual que `--video` en Python) |
| La cámara del Mac la tiene tomada `hand_tracker.py` o Zoom/Meet | Media / alto | Un solo dueño de la cámara en la demo. Mensaje claro con `NotReadableError` |
| **Rendimiento:** el Simulador ya dibuja 2 veces por cuadro (escena + cámara del bicho, `escena.ts:735-746`), sombras PCF 2048 y `pixelRatio` hasta 2; MediaPipe GPU comparte la misma GPU | Alta / medio | MediaPipe con `requestVideoFrameCallback` y tope de 30 fps; video 640×480; `delegate:'GPU'` con caída a CPU; con Manos abierto bajar `pixelRatio` a 1,25 y ofrecer apagar la cámara del bicho (`setPip(false)`, ya existe). Medir: MediaPipe ≥ 24 fps y three ≥ 45 fps en el notebook de la demo. Si no da: correr MediaPipe en un Web Worker con delegate CPU [I] |
| Primera carga de ~23 MB por wifi del evento | Media / medio | Servir desde la misma web (no CDN), precargar al abrir el Simulador en el ensayo, o tenerlo en caché |
| Mandar `drive` al bicho real sin motores llena las consolas de «comando desconocido» | Alta si se activa / bajo | Interruptor apagado por defecto (§1) |
| Cuando haya motores: se cae el wifi del hotspot con el bicho andando | Baja hoy / **alto** | El watchdog tiene que estar en el bicho (frena solo a los 0,5 s sin `drive`), como en el `.ino`. La web no puede garantizarlo: lo dejo pedido a Carlos |
| **Conflicto con Guty** (dueño de `web/`, commits cada 1-2 h en `App.tsx` y `sim/`) | Alta / medio | Todo lo nuevo en `web/src/manos/`. Los 3 archivos suyos se tocan en commits chicos y separados (~70 líneas), con `git pull --rebase --autostash origin dev` justo antes. Avisar por `/anotar` **antes** de empezar y pedirle OK para `escena.ts`. Si dice que no: `PanelManos` con su propio canvas three (gemelo mínimo) sin tocar `escena.ts` |
| Trabajo en paralelo en `handtracking/unity` sin commit | Media / bajo | No tocar esos archivos desde este frente |
| Deploy: bicho·dev en Vercel (`bicho-dev.vercel.app` hoy responde 404 en `/` [V]) lo publica una persona | — | Preparar y avisar; no desplegar |

## 5. Tareas priorizadas (30-90 min cada una)

| # | Tarea | Min | Criterio de terminado |
|---|---|---|---|
| 0 | Avisar a Guty por `/anotar` + pedir OK para tocar `escena.ts`, `Simulador.tsx`, `App.tsx` | 10 | Entrada en `contexto/bitacora/` pusheada a `dev` y respuesta de Guty |
| 1 | `gestos.ts` + `probar-gestos.ts` (port de los 10 tests de Unity) | 45 | `node web/scripts/probar-gestos.ts` → 10/10 verdes, con la mano real IMG_7996 |
| 2 | `tracker.ts` + `PanelManos` mínimo: cámara espejada, HandLandmarker 1.2.3 servido local, esqueleto 2D, gesto por mano, FPS | 75 | En `localhost:5173/#simulador` y en el túnel https: mano derecha dice «derecha», 5 gestos reconocidos a mano, FPS de MediaPipe ≥ 24 en el notebook de la demo; `npm run build` sin errores |
| 3 | `control.ts`: joystick, mezcla, suavizado, hombre muerto 0,3 s, 15 Hz, STOP + Espacio | 45 | Barras L/R se mueven; sacar la mano → 0 en ≤ 0,3 s; contador de envíos ≤ 15/s; STOP traba y suelta |
| 4 | Gemelo: `setMando()` en `escena.ts` + `bus` + props en `Simulador` | 60 | Con la palma, el bicho 3D avanza, retrocede y gira hacia el lado correcto; sin mano frena; three ≥ 45 fps con Manos abierto |
| 5 | Interruptor «Mandar al bicho» por el relé con la clave | 30 | Apagado: en la consola de otra web no aparece nada. Encendido contra `tracker/mock_bicho.py` (directo, `ws://127.0.0.1:8080/ws`): el mock imprime `drive` a ≤15 Hz y `stop` al sacar la mano |
| 6 | Plan B y guion: video pregrabado como fuente, mensajes de permiso, tip de `pixelRatio`/PIP; 2 líneas en `marca/PITCH.md` (lo coordina quien tiene el pitch) | 40 | Demo completa corre sin cámara con el video; ensayo cronometrado de 30 s «mano → bicho 3D» |
| 7 | (opcional) Puente §3-A: `t:manos` en el relé + publicador en web y Unity | 60-90 | Web A maneja con la cámara, web B (otro navegador, sin cámara) ve moverse su gemelo y la mano, latencia percibida < 300 ms. Requiere que Cristian/TesslaRay reinicien el relé |
| 8 | (opcional) Mano fantasma 3D en la escena | 45 | 21 puntos visibles sobre el bicho, sin bajar three de 45 fps |
| 9 | (cuando Carlos tenga motores) `drive`/`stop` en `comandos.py` con watchdog 0,5 s y `comandos` en `info` | — (de Carlos) | El bicho real frena solo a los 0,5 s sin `drive` |

Ruta crítica para la demo: 0 → 1 → 2 → 3 → 4 (≈ 4 h 15). Con eso el jurado ve, en el navegador, la mano y el bicho 3D obedeciendo, sin instalar nada. 5 y 6 son el seguro; 7 y 8, el plus.

## Fuentes consultadas

`CLAUDE.md` y `contexto/estado.md` del repo · `contexto/decisiones.md` · `web/package.json`, `web/vite.config.ts` · `web/src/lib/{protocol,links,inventario}.ts`, `rele.json` · `web/src/App.tsx` (líneas 1-30, 134-200, 410-450) · `web/src/sim/Simulador.tsx`, `escena.ts` (114-170, 720-870) · `rele/servidor.mjs` (180-340) · `bicho/comandos.py`, `bichod.py:350-354`, `version.json` · `handtracking/README.md`, `tracker/hand_tracker.py`, Unity `GestureRecognizer.cs`, `BichoHandController.cs`, `HandData.cs`, `BichoLink.cs` (sin commit), tests · `diseno/INTEGRAR_EN_BICHO_DEV.md`, `taller3d/index.html` (`driveTick`) · `npm view` y `npm pack @mediapipe/tasks-vision@1.2.3` · `curl` al relé, al túnel de bicho·dev y a `bicho-dev.vercel.app` (16:08).

## Lo no verificado

- Que 1.2.3 cargue y rinda bien junto al Simulador en el notebook de la demo (no se corrió nada en navegador).
- El signo del giro en `escena.ts` y el estado del idioma para «lo manejas tú».
- Si el túnel del relé mantiene la URL al reiniciar el servicio.
- Cómo se cablean los motores al Pi (ni el brief ni el repo lo dicen).

# Estado del proyecto

_Lo actualiza el Claude de cualquiera cuando algo cambia. Máximo ~50 líneas: lo viejo se borra de aquí (queda en la bitácora). Última actualización: 22 nov, 05:20, Guty (Claude)._

## La idea

El **Bicho** (nombre definitivo, votado por el equipo el 21 nov): un robot sobre un chasis 4WD de acrílico, con una Raspberry Pi 3 y sensores, sin control remoto. Lo maneja un agente Claude que además escribe y mejora su propio software (se "autoconstruye"). La lámpara robótica se descartó.

- Track **hardware**. El pitch: algo que parece imposible en 36 horas y que sale gracias a la IA.
- **Marca:** «el bicho que se parcha solo» (un bicho también es un bug, y este arregla los suyos). Logo: el ojo de 24 LEDs con una curita; ícono: ese ojo sobre el cuadrado amarillo de bicho·dev. Estilo «Cristal claro», el de bicho·dev. Todo en [`marca/`](../marca/).
- **Por decidir:** el caso de uso. Caminos en discusión: guardián de la propiedad (ahuyentar personas o animales que entran al terreno) o ayuda (adulto mayor, empresa).
- Reunión de las 4:04 (resumen de Granola): un solo brazo de 2 o 3 ejes basta (subir escalones, recoger cosas, prender una luz); parlante; sensor de luz abajo; sensor láser; la cámara tiene el cable corto.

## Qué está hecho

- **bicho·dev** ([`web/`](../web/)): versión del firmware y botón para actualizar por WiFi, sensores en vivo, consola, versiones, cronómetro de entrega e **inventario**.
- **Habilidades** en bicho·dev (la primera sección): lo último que aprendió, qué sabe hacer y un gráfico de lo que aprendió solo frente a lo que le programó el equipo. Lista base en [`bicho/habilidades.json`](../bicho/habilidades.json): súmenle lo que agreguen.
- **bichod** ([`bicho/`](../bicho/)): agente Python con WebSocket de sensores y actualización por `POST /update`.
- **Raspberry Pi 3 andando** (hostname `team39`, usuario `team39`), con `bichod` como servicio y una luz de prueba en el GPIO 17 (comando `luz`). La red del evento es solo 5 GHz y el Pi 3 no la ve: está en un hotspot de 2.4 GHz. Le falta voltaje: conviene una fuente de 5 V y 2.5 A.
- **Parlante y anillo andando (bicho v0.24.0):** el parlante va al ReSpeaker XVF3800 (volumen de ALSA al 100 %). `expresar` muestra cualquier estado del idioma con luz en el anillo y sonido, igual que el simulador, y también las 5 escenas (`"escena":"pieza"` es la del pitch). `bicho/` en `dev` es igual al Pi: lo que el Cerebro aprenda después vive solo en el Pi hasta que alguien lo baje con `{"cmd":"fuente"}`.
- **Relé** ([`rele/`](../rele/)): servicio aparte en EDITH; el bicho se conecta a él y bicho·dev lo ve y actualiza desde cualquier red. Mandar comandos pide la clave del equipo.
- **Inventario** en Neon, con 134 ítems sacados del Claude Sheet. Se ve en bicho·dev → Equipo → Inventario.
- **Harness del equipo:** este `CLAUDE.md`, `contexto/` y las skills compartidas.
- **Cuerpo del bicho listo para imprimir** ([`diseno/`](../diseno/)): estructura de 32 × 20 cm, 3 placas iguales de una pieza con rejilla M3 cada 10 mm y 3 distribuciones (V1 brazo-cuello, V2 brazo + torre, V3 barredor). Son 19 STL y 14 bandejas .3mf, con la guía en [`diseno/imprimir/IMPRIMIR.md`](../diseno/imprimir/IMPRIMIR.md). Drive en `links.md`.
- **Taller 3D** ([`diseno/taller3d/`](../diseno/taller3d/)): mover el brazo, arrastrar piezas, torque en vivo, choques, centro de gravedad y LiDAR. Plan para pasarlo a bicho·dev en [`diseno/INTEGRAR_EN_BICHO_DEV.md`](../diseno/INTEGRAR_EN_BICHO_DEV.md).
- **Hand tracking** ([`handtracking/`](../handtracking/)): MediaPipe + Unity. Entra por el relé con la clave del equipo, y los gestos prenden las luces del bicho real (pulgar, V, puño). Roadmap a la demo en [`handtracking/ROADMAP.md`](../handtracking/ROADMAP.md): el wow es enseñarle un gesto; manejar con la palma depende de los motores (corte a la 01:00).
- **Gemelo 3D y Manos en bicho·dev** (`#gemelo`, `#manos`): el bicho entero (chasis V1 + brazo v4) con los sensores en vivo encima, y la demo de las señas. En `dev`, falta el deploy.
- **Simulador 3D** en bicho·dev → Simulador, con el **idioma del bicho** (30 estados y 5 escenas) en [`bicho/lenguaje.json`](../bicho/lenguaje.json). Propuesta de Guty para que la ajusten Walls y Cristian.
- **Marca y pitch** ([`marca/`](../marca/)): logo en SVG y PNG, `project-logo.png` de 1000 × 1000 ya reemplazado, manual de marca y deck de 12 láminas en dark mode (lo pidió la charla, por el streaming), con el ojo animado y el gráfico de lo que aprendió solo, publicados (links en `links.md`), y el guion de 3 minutos en el orden de la charla (saludo, problema, solución y demo), con plan B y preguntas difíciles, en [`marca/PITCH.md`](../marca/PITCH.md). Nombre, frase y descripción ya están en `platanus-hack-project.jsonc` y `project-description.md`.

## En qué está cada uno

_Reparto sugerido el 21 nov a las 00:01; cada uno corrige su línea._

- **Carlos:** firmware del bicho (siguiendo `PROTOCOLO.md`).
- **Renate:** cableado de sensores y nombres de los campos del panel.
- **Guty:** bicho·dev, inventario, harness del equipo, la comunicación agente → humano y la marca (logo, manual y borrador del pitch).
- **Walls y Cristian:** capa de IA y personalidad del bicho, y el pitch.

## Pendientes

- **Imprimir** (orden en `IMPRIMIR.md`): primero B00, la prueba de tolerancia de 20 min, y el brazo. Las placas de 320 × 200 necesitan una cama de 330 × 210 mm o más; si no hay, usar la versión en dos mitades que está en Drive (carpeta v3.1).
- Medir el patrón de agujeros del motor TT antes de imprimir las cunas P24, y elegir la distribución: V1, V2 o V3.
- Llevar el robot real (GLB) al Simulador de bicho·dev y agregar el modo «Armar» (ver `diseno/INTEGRAR_EN_BICHO_DEV.md`).
- Elegir el caso de uso (guardián o ayuda). El borrador del pitch propone que lo central sea que aprende en vivo, con cuidar el patio como escenario: confirmar.
- **Pitch:** elegir quién presenta, opera y respalda; medir en tres ensayos cuánto tarda en aprender a hablar (hoy aprende algo nuevo en ~4 min y tiene que bajar de 2); bicho·dev en dark mode para el streaming; README para el jurado (le pregunta al repo con IA); grabar el video de 60 s. Todo en `marca/PITCH.md`.
- Corroborar que el esquemático (4 páginas) funciona con el hardware que hay.
- Revisar por qué el segundo inversor no aparece en el sistema.
- Publicar bicho·dev (lo ve quien hace los deploys) y conseguir una API key de Anthropic para el botón "Preguntar" del inventario.
- Poner la URL de deploy en `platanus-hack-project.jsonc` antes de enviar (nombre, frase y descripción ya están).

## Fechas

- **Fin del hacking:** domingo 22 a las 8:30 según el cronograma; la plataforma cierra la entrega a las 9:00. Apuntar a tener todo listo a las 8:30. Se envía con un push a `main`, que lo hace una persona cuando el equipo decide.
- Sábado: desayuno 8:30, almuerzo 13:30, charla "Cómo hacer un buen demo" 20:00, comida 21:00.
- Domingo: último bajón 4:00, desayuno 8:00, presentaciones generales 9:30, finales 12:00, premiación 14:30.
- Cronograma completo: `web/src/lib/cronograma.json` (bicho·dev muestra el próximo evento bajo el cronómetro).

# cerebro: lo que decide y aprende el bicho

Servicio aparte que le da inteligencia al bicho. Se conecta al relé ([`../rele/`](../rele/)) como un cliente más, recibe cada frase que el bicho oye (o que alguien le escribe desde bicho·dev) y deja que Claude decida:

| Decisión | Cuándo | Qué pasa |
|---|---|---|
| ignorar | No le hablan a él | Nada |
| responder | Le conversan o preguntan | La respuesta sale en bicho·dev → Cerebro |
| comando | Le piden algo que ya sabe | Manda un comando de los de `bicho/comandos.py` |
| aprender | Le piden algo que no sabe | Escribe el código, lo instala en el bicho y lo prueba |
| buscar | Le preguntan algo que no sabe o que depende de información actual | Busca en internet con Exa y responde con lo que encontró. Solo si hay `EXA_API_KEY` |
| hablar | Hay que decirlo en voz alta (saludar al dueño, advertir a un extraño) | Lo dice con una de sus voces de ElevenLabs. Solo si hay `ELEVENLABS_API_KEY` |

## Cómo aprende

1. Le pide al Pi un diagnóstico del hardware (`{"cmd":"diag"}`) y el código que está corriendo (`{"cmd":"fuente"}`).
2. Escribe o cambia archivos. No puede tocar el núcleo (`bichod.py`, `salida.py`, `oido.py`).
3. Instala la versión nueva por el relé. El Pi la prueba antes de activarla (que compile y que los módulos carguen); si falla, la rechaza y devuelve el error.
4. Si la versión se activa pero no logra reportarse en 60 s, el bicho vuelve solo a la anterior.
5. Prueba el comando nuevo y, si es una cámara, mira la imagen que llega. Corrige y reinstala si hace falta (hasta 4 veces).

Los paquetes que instala quedan en `cerebro/versiones/` (no se suben al repo).

## Correrlo

```bash
cd cerebro && npm install
```

```bash
ANTHROPIC_API_KEY=... RELE_URL=https://<relé> CLAVE_EQUIPO=... ELEVENLABS_API_KEY=... node cerebro.mjs
```

## Voz

El bicho se expresa casi siempre con sonidos y luces; la voz es especial. Tiene dos, diseñadas en ElevenLabs (los `voice_id` están en [`../bicho/lenguaje.json`](../bicho/lenguaje.json) → `voces`):

- **dueno**: grave, algo robótica, cercana y protectora. Para su dueño y la gente que conoce.
- **extrano**: demoníaca, muy grave y con eco. Para advertirle a un extraño o avisar de un peligro.

Cuando Claude elige `hablar`, el cerebro pide el audio a ElevenLabs (WAV de 16 kHz) y lo manda al bicho con `{"cmd":"hablar",...}` y a bicho·dev con `{"t":"voz",...}`. Formato en [`../PROTOCOLO.md`](../PROTOCOLO.md).

- Sin `ELEVENLABS_API_KEY` la herramienta no aparece y el bicho responde solo por escrito.
- Si el bicho todavía no sabe reproducir audio, su voz se oye solo en bicho·dev. Para que aprenda: escríbele "bicho, aprende a hablar por tu parlante".
- La clave es de la cuenta de ElevenLabs donde están las voces. Va en `cerebro/.env` o en el entorno, nunca en el repo.

| Variable | Para qué |
|---|---|
| `ANTHROPIC_API_KEY` | Clave de Anthropic, con saldo. Obligatoria. |
| `RELE_URL` | Dirección del relé. Obligatoria. |
| `CLAVE_EQUIPO` | La clave del equipo: sin ella no puede mandar comandos ni instalar. |
| `CEREBRO_MODELO` | Modelo de Claude para aprender, o sea escribir código (`claude-fable-5-2` por defecto). |
| `CEREBRO_MODELO_DECIDIR` | Modelo que decide qué hacer con cada frase (`claude-haiku-5-5` por defecto, por velocidad). |
| `EXA_API_KEY` | Clave de Exa para que busque en internet. Sin ella, responde solo con lo que sabe. |
| `CEREBRO_APRENDE` | `0` para que decida y responda, pero no modifique el bicho. |
| `CEREBRO_ESCUCHA` | Qué evalúa de lo que oye: `nombre` (por defecto: lo que dice «bicho» o sigue una conversación en voz alta), `estricto` (solo lo que dice «bicho»; para salas con mucha gente), `no` (ignora el micrófono) o `todo`. |
| `CEREBRO_MEMORIA` | Archivo donde guarda lo que recuerda (`cerebro/memoria.json` por defecto). |
| `CEREBRO_ATAJOS` | `0` para que ninguna orden se salte el modelo. Por defecto, parar, avanzar, atrás y girar se reconocen por palabras. |
| `CEREBRO_POT` | Potencia de esas órdenes cuando no se dice (`50` por defecto). |
| `CEREBRO_MIRA_S` | Cada cuántos segundos saca una foto, la describe y la guarda en su memoria de lo que ve. `0` (por defecto): no mira solo. Con `30` son unas 120 descripciones por hora. |

También se pueden poner en `cerebro/.env`, que no se sube al repo.

## Atajos: órdenes que no pasan por el modelo

Decidir con Claude tarda entre 1 y 3 segundos. Las órdenes de movimiento más comunes se reconocen por palabras ([`atajos.mjs`](atajos.mjs)) y salen hacia el bicho en el mismo instante en que llega la frase:

| Se le dice | Manda |
|---|---|
| «para», «detente», «stop», «alto», «para los motores» | `{"cmd":"motores","on":false}` |
| «avanza», «adelante», «corre» | `{"cmd":"motores","on":true,"pot":50,"seg":0}` (sigue hasta «para») |
| «atrás», «retrocede», «marcha atrás» | lo mismo con `"sentido":-1` |
| «gira a la izquierda», «dobla a la derecha», «izquierda» | `{"cmd":"motores","giro":"izquierda","pot":50}` (0,8 s; pide bicho v0.35.0) |

- Se puede agregar potencia y tiempo: «avanza al 80», «atrás por 2 segundos», «gira a la derecha sin parar», «a toda potencia».
- Solo calza si la frase entera es la orden. «Avanza hasta la puerta y vuelve» o «¿por qué no avanzas?» van al modelo.
- **«Para» corta siempre:** por voz no necesita que lo nombren ni respeta el modo del micrófono. El resto de las órdenes habladas sigue las reglas de `CEREBRO_ESCUCHA`.
- Si el bicho rechaza la orden porque el mapa de motores no está confirmado, la frase pasa al modelo, que lo resuelve.

## Conversar por voz

- **Llamarlo lo despierta.** Si alguien dice solo «Bicho» (o «oye bicho», «bicho, ¿me escuchas?»), prende la luz de «te escucha», contesta «¿Sí? Te escucho» y espera la orden durante `CEREBRO_VENTANA_S` segundos (45 por defecto). En ese rato no hace falta volver a nombrarlo, y cada orden que cumple renueva la espera.
- Si oye «Bicho, Bicho» confirma enseguida con el mismo tono, incluso si el audio llegó al tope de duración. En modo `nombre`, una comprobación breve como «¿me escuchas?» también recibe el tono mientras la conversación siga abierta. Si contesta por texto a una continuación sin nombre y sin ejecutar comandos, da un tono para que la persona sepa que recibió respuesta.
- «Bicho, gira» da el tono de escucha apenas llega la transcripción y manda el giro por el atajo. El tono de acción indica que el controlador aceptó el giro. En modo `nombre` también se puede decir «Bicho», esperar el pitido y luego «gira».
- **Órdenes largas.** El oído corta cada frase a los pocos segundos. Si una frase llegó hasta ese tope, el cerebro espera 1,6 s la continuación y las junta antes de decidir (`CEREBRO_TOPE_FRASE_S`, 3,8 por defecto, tiene que calzar con el tope del oído del bicho).
- Lo que oye sin que lo nombren y fuera de esa espera no se evalúa.

## Memoria

Cada frase es una llamada nueva a Claude, así que lo que el bicho sabe de antes hay que dárselo. Tiene tres capas ([`memoria.mjs`](memoria.mjs)):

| Capa | Qué guarda | Cuánto dura |
|---|---|---|
| Hechos | Lo que él decide guardar con la herramienta `recordar` (nombres, gustos, decisiones, cómo le conectaron algo) y borra con `olvidar`. Hasta 40. | Hasta que lo olvide |
| Resumen | Lo conversado hace rato, en un párrafo. Se actualiza solo cuando la conversación pasa de 24 turnos. | Se va reescribiendo |
| Conversación | Los últimos turnos en que le hablaron a él, tal cual. Van a Claude como mensajes de verdad, así entiende «hazlo de nuevo» o «¿y el otro?». | Hasta que pasan al resumen |

### Memoria de lo que ve

Con `CEREBRO_MIRA_S` mayor que cero, cada tantos segundos el cerebro le pide una foto al bicho (o usa la última si la cámara ya está prendida), la describe en una o dos frases con el modelo rápido y la guarda con la hora, el lugar y lo que digan sus sensores de posición (`flujo`, si lo tiene). Si la escena no cambió, no guarda nada. Es la idea de [ReMEmbR](https://arxiv.org/abs/2409.13682), de NVIDIA, en chico.

- `recordar_visto` (herramienta): busca en esas vistas por palabras, por los últimos N minutos y por lugar. Así responde «¿pasó alguien?», «¿cuándo viste al perro?» o «¿dónde quedó la mochila?», con la hora.
- `estoy_en` (herramienta): cuando alguien le dice dónde está («te dejé en el patio»), lo anota y las vistas siguientes quedan con ese lugar. No tiene GPS: el lugar se lo dice una persona.
- Guarda hasta 400 vistas (unas 3 horas mirando cada 30 s). Las tres últimas van siempre en su contexto.

### Lo demás

- Las frases que oye y decide ignorar son ruido: guarda las últimas 4 y nunca desplazan la conversación. Antes compartían 12 líneas con todo lo demás y en una sala con gente la memoria duraba menos de un minuto.
- Escribirle desde bicho·dev no abre la ventana de escucha del micrófono; solo lo que le dicen en voz alta.
- Si el bicho (la Raspberry) está desconectado, igual contesta lo que le escriben y recuerda: avisa que no puede moverse.
- Todo queda en `cerebro/memoria.json`, al lado del cerebro, y sobrevive a un reinicio. Tiene nombres y conversaciones del equipo: no se sube al repo. Para borrarle la memoria, detén el cerebro y borra ese archivo.

## Lo que anuncia

Todo lo que decide o hace lo manda al relé, que lo reparte a quienes miran bicho·dev:

```json
{"t":"cerebro","id":"…","tipo":"responde","texto":"Listo, luz prendida.","frase":"…","oido":"prende la luz","angulo":282,"ts":1795258000000}
```

`tipo` puede ser `ignora`, `responde`, `comando`, `aprende`, `paso` (avance de un aprendizaje), `aprendido` o `error`. `aprendido` trae además `version` y `habilidad` (`{"nombre":"Ver con su cámara","pidele":"bicho, ¿qué ves?","comandos":["camara"]}`), y lo aprendido queda anotado en `habilidades.json` dentro del código del bicho. bicho·dev arma con eso la sección **Habilidades** (lo último que aprendió, qué sabe hacer y el gráfico de autonomía); la lista base está en [`../bicho/habilidades.json`](../bicho/habilidades.json). Para escribirle desde la web se manda `{"t":"cerebro","tipo":"decir","texto":"…"}` (pide la clave del equipo).

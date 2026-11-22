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

También se pueden poner en `cerebro/.env`, que no se sube al repo.

## Memoria

Cada frase es una llamada nueva a Claude, así que lo que el bicho sabe de antes hay que dárselo. Tiene tres capas ([`memoria.mjs`](memoria.mjs)):

| Capa | Qué guarda | Cuánto dura |
|---|---|---|
| Hechos | Lo que él decide guardar con la herramienta `recordar` (nombres, gustos, decisiones, cómo le conectaron algo) y borra con `olvidar`. Hasta 40. | Hasta que lo olvide |
| Resumen | Lo conversado hace rato, en un párrafo. Se actualiza solo cuando la conversación pasa de 24 turnos. | Se va reescribiendo |
| Conversación | Los últimos turnos en que le hablaron a él, tal cual. Van a Claude como mensajes de verdad, así entiende «hazlo de nuevo» o «¿y el otro?». | Hasta que pasan al resumen |

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

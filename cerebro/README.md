# cerebro: lo que decide y aprende el bicho

Servicio aparte que le da inteligencia al bicho. Se conecta al relé ([`../rele/`](../rele/)) como un cliente más, recibe cada frase que el bicho oye (o que alguien le escribe desde bicho·dev) y deja que Claude decida:

| Decisión | Cuándo | Qué pasa |
|---|---|---|
| ignorar | No le hablan a él | Nada |
| responder | Le conversan o preguntan | La respuesta sale en bicho·dev → Cerebro |
| comando | Le piden algo que ya sabe | Manda un comando de los de `bicho/comandos.py` |
| aprender | Le piden algo que no sabe | Escribe el código, lo instala en el bicho y lo prueba |

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
ANTHROPIC_API_KEY=... RELE_URL=https://<relé> CLAVE_EQUIPO=... node cerebro.mjs
```

| Variable | Para qué |
|---|---|
| `ANTHROPIC_API_KEY` | Clave de Anthropic, con saldo. Obligatoria. |
| `RELE_URL` | Dirección del relé. Obligatoria. |
| `CLAVE_EQUIPO` | La clave del equipo: sin ella no puede mandar comandos ni instalar. |
| `CEREBRO_MODELO` | Modelo de Claude para aprender, o sea escribir código (`claude-fable-5-2` por defecto). |
| `CEREBRO_MODELO_DECIDIR` | Modelo que decide qué hacer con cada frase (`claude-haiku-5-5` por defecto, por velocidad). |
| `CEREBRO_APRENDE` | `0` para que decida y responda, pero no modifique el bicho. |

También se pueden poner en `cerebro/.env`, que no se sube al repo.

## Lo que anuncia

Todo lo que decide o hace lo manda al relé, que lo reparte a quienes miran bicho·dev:

```json
{"t":"cerebro","id":"…","tipo":"responde","texto":"Listo, luz prendida.","frase":"…","oido":"prende la luz","angulo":282,"ts":1795258000000}
```

`tipo` puede ser `ignora`, `responde`, `comando`, `aprende`, `paso` (avance de un aprendizaje), `aprendido` o `error`. Para escribirle desde la web se manda `{"t":"cerebro","tipo":"decir","texto":"…"}` (pide la clave del equipo).

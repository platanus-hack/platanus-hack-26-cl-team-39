"""
Comandos propios del bicho: servos, LEDs, sonido, etc.

La web (consola) y el harness mandan líneas JSON como {"cmd":"servo","i":0,"deg":90}.
manejar() recibe ese dict y devuelve un texto para la consola, o None si no conoce el comando.
Los comandos "info", "rate" y "reboot" ya los resuelve bichod.py.

Al agregar un comando nuevo, anotarlo también en herramientas.AYUDA para que "ayuda" lo cuente.
"""
from __future__ import annotations

import anillo
import camara
import descubrir
import escucha
import expresar
import flujo
import flujo2
import gesto
import gpios
import herramientas
import i2c
import luces
import luz
import motores
import oido_luz
import respeaker
import servos
import speaker
import vibrar

# El comando gesto se anota aquí en la ayuda (herramientas.py no cambió en esta versión).
herramientas.AYUDA["gesto"] = (
    '{"cmd":"gesto"}  estado  ·  "on":true mira la cámara y, si ve el dedo del medio, parpadea la luz roja'
    ' (GPIO 22) unos segundos, enojado, y toca un sonido  ·  "on":false  ·  "enojo":true prueba la luz roja'
    ' ("enojo":false la corta)  ·  "sonido":true prueba el sonido  ·  "ver":true manda a Vista la máscara de piel'
    '  ·  "parlante":"plughw:Headphones" cambia la salida de audio'
)
herramientas.AYUDA["oido"] = (
    '{"cmd":"oido"}  estado  ·  "on":true la luz del micrófono (ReSpeaker) apunta hacia donde llega la voz'
    '  ·  "on":false la apaga  ·  "modo":"chip" (el propio micrófono prende el LED de la dirección) o "suave"'
    ' (el bicho desliza un punto de luz por el anillo)  ·  "color":"verde"|"RRGGBB"  ·  "brillo":0-255'
    '  ·  en modo suave: "probar":90 apunta a ese ángulo 4 s, "offset":grados y "sentido":1|-1 para calzarla'
    '  ·  "leer":true muestra cómo están los LEDs en el chip'
)
herramientas.AYUDA["speaker"] = (
    '{"cmd":"speaker"}  estado: salida elegida, salidas que hay y última prueba  ·  "probar":true dos pitidos'
    '  ·  "tono":440,"seg":1 un tono  ·  "vol":1-100 amplitud del tono  ·  "todas":true recorre todas las salidas'
    ' (1 pitido la primera, 2 la segunda...)  ·  "salida":"audifonos"|"respeaker"|"hdmi"|"plughw:..." elige la'
    ' salida (también la del sonido del gesto; queda guardada)  ·  "on":false corta lo que suena'
    '  ·  "mezclador":true muestra el volumen de ALSA de la salida  ·  "volumen":0-100 lo fija en todos sus'
    ' controles y los saca del silencio (en el ReSpeaker, el PCM-1 que viene bajo; queda guardado y se repone'
    ' al arrancar)  ·  "tarjeta":"Array" para otra tarjeta'
)
herramientas.AYUDA["vibrar"] = (
    '{"cmd":"vibrar"}  vibra 3 s: no hay motor vibrador, así que toca pulsos de un tono grave (80 Hz) por el'
    ' parlante elegido en speaker  ·  "seg":0.3-10 cuánto dura  ·  "hz":30-250 frecuencia  ·  "vol":1-100'
    '  ·  "continuo":true un solo tono sin pulsos  ·  "on":false lo corta  ·  "estado":true dice cómo está'
)
herramientas.AYUDA["anillo"] = (
    '{"cmd":"anillo"}  estado  ·  "estado":"piensa" la luz de un estado del idioma del bicho (como el simulador)'
    '  ·  "estados":true lista de estados  ·  "patron":"gira"|"respira"|"faro"|"arcoiris"|... con "color",'
    ' "periodo" (s) e "intensidad" (0-1)  ·  "leds":["ff0000",...] un color por LED (hasta 12)  ·  "led":3,'
    '"color":"rojo" cambia uno  ·  "efecto":"respira"|"arcoiris"|"fijo"|"doa"|"apagado" efecto del chip (con'
    ' "color" y "velocidad")  ·  "brillo":0-255  ·  "seg":N cuánto dura (después vuelve a seguir la voz si'
    ' estaba en eso)  ·  "lado":grados (patrón lado; sin él mira hacia la voz)  ·  "on":false apaga  ·'
    '  "leer":true lee el chip'
)
herramientas.AYUDA["expresar"] = (
    '{"cmd":"expresar","estado":"contento"}  luz del anillo + sonido de un estado del idioma del bicho, igual'
    ' que el simulador ("seg":N cuánto dura la luz)  ·  "escena":"perro"|"persona"|"pieza"|"falla"|"dueno"'
    ' una escena completa  ·  "lista":true estados y escenas  ·  "sonido":false solo luz  ·  "luz":false solo'
    ' sonido  ·  "on":false corta todo'
)
# Escáner del bus I2C (i2c.py): trae su propia ayuda.
herramientas.AYUDA["i2c"] = i2c.AYUDA
# Motores por el PCA9685 (motores.py): trae su propia ayuda.
herramientas.AYUDA["motores"] = motores.AYUDA
herramientas.AYUDA["hablar"] = '{"cmd":"hablar","fmt":"wav","b64":"..."}  dice en voz alta un WAV (lo manda el cerebro con la voz de ElevenLabs) por el parlante elegido'
herramientas.AYUDA["servo"] = servos.AYUDA
# Descubrir el mapeo de motores midiendo con flujo y cámara (descubrir.py): trae su propia ayuda.
herramientas.AYUDA["descubrir"] = descubrir.AYUDA
# Salidas de los GPIO 23 y 24 (gpios.py): trae su propia ayuda.
herramientas.AYUDA["gpio23_24"] = gpios.AYUDA
# Turnos de escucha con pitidos de inicio y cierre (escucha.py): trae su propia ayuda.
herramientas.AYUDA["escucha"] = escucha.AYUDA
# Los comandos de respeaker.py (documentación y parámetros del ReSpeaker) traen su propia ayuda.
herramientas.AYUDA.update(respeaker.AYUDA)

_COLORES = {"verde": "verde", "rojo": "rojo", "roja": "rojo"}
_SI = ("si", "sí", "s", "yes", "true", "1", "verde")
_NO = ("no", "n", "false", "0", "rojo", "roja")


def _num(v, defecto: float, lo: float, hi: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = defecto
    if x != x:  # NaN
        x = defecto
    return max(lo, min(x, hi))


def _responder(si: bool, c: dict) -> str:
    seg = _num(c.get("seg", 2.0), 2.0, 0.2, 10.0)
    color = luces.responder(si, seg)
    palabra = "sí" if si else "no"
    nombre = "verde" if color == "verde" else "roja"
    return f"{palabra}: luz {nombre} {seg:g} s ({luces.donde(color)})"


def _flujo(mod, nombre: str, c: dict) -> str:
    """Un sensor de flujo (flujo o flujo2): nunca lanza, devuelve el error como texto."""
    try:
        if c.get("reset"):
            return mod.reiniciar()
        if "on" not in c:
            return mod.estado()
        return mod.prender() if c.get("on") else mod.apagar()
    except Exception as e:
        return f"{nombre}: falló: {type(e).__name__}: {e}"


def _gesto(c: dict) -> str:
    partes = []
    if "parlante" in c:
        partes.append(gesto.parlante(c.get("parlante")))
    if "on" in c:
        partes.append(gesto.prender() if c.get("on") else gesto.apagar())
    if "enojo" in c:
        partes.append(gesto.probar_enojo() if c.get("enojo") else gesto.calmar())
    if c.get("sonido"):
        partes.append(gesto.probar_sonido())
    if c.get("ver"):
        partes.append(gesto.ver())
    return " · ".join(partes) if partes else gesto.estado()


def _oido(c: dict) -> str:
    partes = oido_luz.configurar(c)  # modo, color, brillo, offset, sentido (si vienen)
    if "on" in c:
        if c.get("on"):
            anillo.soltar()  # el anillo y la luz del oído pelearían por los mismos LEDs
        partes.append(oido_luz.prender() if c.get("on") else oido_luz.apagar())
    if "probar" in c:
        partes.append(oido_luz.probar(c.get("probar")))
    if c.get("leer"):
        partes.append(oido_luz.leer_chip())
    return " · ".join(partes) if partes else oido_luz.estado()


def _speaker(c: dict) -> str:
    partes = []
    if "salida" in c:
        partes.append(speaker.elegir(c.get("salida")))
    if "volumen" in c:
        partes.append(speaker.volumen(c.get("volumen"), c.get("tarjeta")))
    elif c.get("mezclador"):
        partes.append(speaker.mezclador(c.get("tarjeta")))
    if ("on" in c and not c.get("on")) or c.get("parar"):
        partes.append(speaker.parar())
    elif c.get("todas"):
        partes.append(speaker.probar_todas(c.get("vol")))
    elif c.get("probar") or c.get("on") or "tono" in c or "seg" in c:
        partes.append(speaker.probar(c.get("tono"), c.get("seg"), c.get("vol")))
    return " · ".join(partes) if partes else speaker.estado()


def _vibrar(c: dict) -> str:
    if ("on" in c and not c.get("on")) or c.get("parar"):
        return vibrar.parar()
    if c.get("estado"):
        return vibrar.estado()
    return vibrar.vibrar(c.get("seg"), c.get("hz"), c.get("vol"), bool(c.get("continuo")))


def manejar(c: dict) -> str | None:
    cmd = c.get("cmd")

    if cmd == "hola":
        return "hola desde el bicho"

    # Motores (motores.py): 4 motores por el PCA9685 (I2C bus 1, 0x40), hasta 100 % y sin tope de tiempo. Sube solo el STBY de los drivers al partir.
    # Va primero para que la orden de parar nunca quede detrás de otra cosa.
    #   {"cmd":"motores","on":false}                   para todo al tiro (apaga los 16 canales)
    #   {"cmd":"motores"}                              estado: mapa, si está confirmado, cómo está el chip
    #   {"cmd":"motores","mapa":"pares"}               elige el mapa de canales (o "adafruit", o una lista)
    #   {"cmd":"motores","motor":1,"pot":12,"seg":1}   prueba un motor  ·  "canal":0 prueba un canal en crudo
    #   {"cmd":"motores","invertir":[4]}               da vuelta SOLO esos motores: los demás quedan como estaban
    #   {"cmd":"motores","invertidos":[1,4]}           fija la lista completa de invertidos ([] = ninguno)
    #   {"cmd":"motores","confirmar":true}             deja el mapa confirmado
    #   {"cmd":"motores","on":true,"pot":15,"seg":1.5} mueve los 4 (solo con el mapa confirmado)
    #   {"cmd":"motores","on":true,"pot":80,"seg":0}   corre sin límite de tiempo, hasta {"cmd":"motores","on":false}
    #   {"cmd":"motores","on":true,"sentido":-1}       hacia atrás
    #   {"cmd":"motores","giro":"izquierda","pot":50}  gira en el lugar (o "derecha"); 0,8 s si no dices "seg"
    #   {"cmd":"motores","lados":{"izq":[1,2],"der":[3,4]}}  qué motores van a cada lado (para el giro)
    # No bloquea: el movimiento corre en un hilo daemon que se apaga solo al cumplirse el tiempo.
    if cmd in ("motores", "motor"):
        try:
            if (("on" in c and not c.get("on")) or c.get("parar")) and descubrir.activa():
                return descubrir.detener()  # parar también corta el barrido de descubrir (y apaga los motores)
            return motores.manejar(c)
        except Exception as e:
            return f"motores: falló: {type(e).__name__}: {e}"

    # Servos (servos.py): hasta 16 servos en un SEGUNDO PCA9685 (I2C 0x41, a 50 Hz), aparte del de los motores.
    # Un servo no usa "potencia": se le pide un ángulo y se queda ahí sosteniendo.
    #   {"cmd":"servo"}                          estado
    #   {"cmd":"servo","i":0,"deg":90}           canal 0 a 90° (de 0 a 180)
    #   {"cmd":"servo","i":0,"us":1500}          ancho de pulso en crudo (400 a 2600 µs), para calibrar
    #   {"cmd":"servo","i":0,"barrer":true}      lo pasea 0 → 180 → 90 para probarlo
    #   {"cmd":"servo","i":0,"soltar":true}      le corta el pulso (queda suelto)  ·  sin "i" suelta todos
    if cmd in ("servo", "servos"):
        try:
            return servos.manejar(c)
        except Exception as e:
            return f"servo: falló: {type(e).__name__}: {e}"

    # Descubrir (descubrir.py): averiguar solo qué canales del PCA9685 mueven los motores, midiendo cada
    # prueba con los dos sensores de flujo óptico y con la cámara (cuadro de antes y de después).
    #   {"cmd":"descubrir","on":true}                barre los 16 canales de a uno (12 → 20 → 30 %)
    #   {"cmd":"descubrir","canal":3}                prueba medida de un canal
    #   {"cmd":"descubrir","motor":2,"sentido":-1}   prueba medida de un motor del mapa
    #   {"cmd":"descubrir","todos":true}             todos los motores del mapa (para confirmar si avanza)
    #   {"cmd":"descubrir"}  ·  "resultado":true     cómo va / tabla completa
    #   {"cmd":"descubrir","on":false}               corta y apaga los motores
    # No bloquea: todo corre en un hilo daemon; usa la maquinaria segura de motores.py.
    if cmd == "descubrir":
        try:
            return descubrir.manejar(c)
        except Exception as e:
            return f"descubrir: falló: {type(e).__name__}: {e}"

    # Herramientas de software (herramientas.py): saber qué sé hacer, buscar en mi código y crear notas.
    #   {"cmd":"ayuda"}  ·  {"cmd":"ayuda","de":"camara"}       lista de comandos / cómo se usa uno
    #   {"cmd":"archivos"}                                       archivos de mi código
    #   {"cmd":"buscar","q":"GPIO"}  ("en":"luz.py" | "notas")   busca un texto en mi código y mis notas
    #   {"cmd":"ver","archivo":"luz.py","desde":1,"n":20}        muestra líneas de un archivo de mi código
    #   {"cmd":"herramientas"}  ·  "q":"git"                     programas y módulos de Python disponibles
    #   {"cmd":"nota","nombre":"ideas","texto":"..."}            crea una nota ("agregar":true, "borrar":true)
    #   {"cmd":"notas"}                                          lista las notas
    # Todo es rápido, de solo lectura salvo las notas, y no deja nada corriendo.
    if cmd in herramientas.COMANDOS:
        try:
            return herramientas.manejar(c)
        except Exception as e:
            return f"{cmd}: falló: {type(e).__name__}: {e}"

    # ReSpeaker (respeaker.py): leer la wiki de Seeed y manejar el chip del micrófono.
    # Los comandos y su uso están en respeaker.COMANDOS / respeaker.AYUDA. No bloquea: lo lento va en hilos.
    if cmd in respeaker.COMANDOS:
        try:
            return respeaker.manejar(c)
        except Exception as e:
            return f"{cmd}: falló: {type(e).__name__}: {e}"

    # Escáner I2C (i2c.py): qué dispositivos responden en el bus 1 (pines 3 y 5), p. ej. drivers de motores.
    #   {"cmd":"i2c"}                 escanea y lista las direcciones en hexadecimal, con lo que podrían ser
    #   {"cmd":"i2c","bus":2}         otro bus (los de la cámara no se tocan)
    #   {"cmd":"i2c","ultimo":true}   repite el último resultado
    # No bloquea: el sondeo corre en un hilo daemon que termina solo; solo sondea, no mueve nada.
    if cmd == "i2c":
        try:
            return i2c.manejar(c)
        except Exception as e:
            return f"i2c: falló: {type(e).__name__}: {e}"

    # Luz en el GPIO 17:  {"cmd":"luz","on":true}  ·  {"cmd":"luz","on":false}
    # Parpadeo:           {"cmd":"luz","blink":5}  (opcional "t": periodo en segundos)
    if cmd == "luz":
        donde = f"GPIO {luz.PIN}" if luz.real else "simulada"
        if "blink" in c:
            n = max(1, min(int(c["blink"]), 100))
            t = max(0.05, min(float(c.get("t", 0.5)), 5.0))
            luz.parpadear(n, t)
            return f"luz parpadeando {n} veces ({donde})"
        if c.get("on"):
            luz.prender()
            return f"luz prendida ({donde})"
        luz.apagar()
        return f"luz apagada ({donde})"

    # Luces de colores (luces.py): verde en el GPIO 27, roja en el GPIO 22.
    #   {"cmd":"verde","on":true}  ·  {"cmd":"verde","on":false}  ·  {"cmd":"verde","blink":5,"t":0.5}
    #   {"cmd":"rojo", ...} igual (también acepta "roja")
    #   {"cmd":"verde"} sin nada más dice cómo está
    if cmd in _COLORES:
        color = _COLORES[cmd]
        nombre = "verde" if color == "verde" else "roja"
        donde = luces.donde(color)
        if "blink" in c:
            n = int(_num(c["blink"], 5, 1, 100))
            t = _num(c.get("t", 0.5), 0.5, 0.05, 5.0)
            luces.parpadear(color, n, t)
            return f"luz {nombre} parpadeando {n} veces ({donde})"
        if "on" not in c:
            return f"luz {nombre} {'prendida' if luces.prendida(color) else 'apagada'} ({donde})"
        if c.get("on"):
            luces.prender(color)
            return f"luz {nombre} prendida ({donde})"
        luces.apagar(color)
        return f"luz {nombre} apagada ({donde})"

    # Responder con luces:  {"cmd":"si"}  verde unos segundos  ·  {"cmd":"no"}  roja unos segundos
    #                       {"cmd":"responder","r":"si"}  o  "r":"no"  (opcional "seg": cuánto dura)
    # Se apagan solas; para cortarlas antes: {"cmd":"luces","on":false}
    if cmd in ("si", "sí"):
        return _responder(True, c)
    if cmd == "no":
        return _responder(False, c)
    if cmd == "responder":
        r = c.get("r")
        if r is True or str(r).strip().lower() in _SI:
            return _responder(True, c)
        if r is False or str(r).strip().lower() in _NO:
            return _responder(False, c)
        return 'responder: usa "r":"si" o "r":"no"'

    # {"cmd":"luces","on":false} apaga la verde y la roja  ·  {"cmd":"luces"} dice cómo están
    if cmd == "luces":
        if "on" in c:
            if c.get("on"):
                for color in luces.PINES:
                    luces.prender(color)
                return "luces verde y roja prendidas"
            luces.apagar_todas()
            return "luces verde y roja apagadas"
        partes = []
        for color in luces.PINES:
            nombre = "verde" if color == "verde" else "roja"
            partes.append(f"{nombre} {'prendida' if luces.prendida(color) else 'apagada'} ({luces.donde(color)})")
        return "luces: " + ", ".join(partes)

    # Salidas de los GPIO 23 y 24 (gpios.py, pines físicos 16 y 18). El 27 y el 22 siguen siendo verde y rojo.
    #   {"cmd":"gpio23_24","on":true}    prende las dos y las deja prendidas
    #   {"cmd":"gpio23_24","on":false}   las apaga
    #   {"cmd":"gpio23_24"}              cómo están  ·  "pin":23 o "pin":24 para una sola
    # No bloquea ni deja nada corriendo: los pines se toman con la primera orden de prender o apagar.
    if cmd in ("gpio23_24", "gpios"):
        try:
            return gpios.manejar(c)
        except Exception as e:
            return f"gpio23_24: falló: {type(e).__name__}: {e}"

    # Cámara CSI:  {"cmd":"camara","on":true}   manda imágenes a Vista (6 por segundo; "fps":1-15 lo cambia en vivo)
    #              {"cmd":"camara","on":false}  la apaga
    #              {"cmd":"camara"}             dice cómo está
    #              {"cmd":"foto"}               saca una sola foto
    # Nada de esto bloquea: la captura corre en un hilo aparte (camara.py).
    if cmd == "camara":
        try:
            partes = []
            if "fps" in c:
                partes.append(camara.poner_fps(c.get("fps")))
            if "on" in c:
                partes.append(camara.prender() if c.get("on") else camara.apagar())
            return " · ".join(partes) if partes else camara.estado()
        except Exception as e:
            return f"la cámara falló: {type(e).__name__}: {e}"

    # Hablar: el cerebro sintetiza la voz con ElevenLabs y manda {"cmd":"hablar","fmt":"wav","b64":"..."} (WAV de
    # 16 kHz, mono, 16 bits). Aquí solo se toca por el parlante elegido (speaker.py), en su hilo, sin bloquear.
    if cmd == "hablar":
        try:
            import base64

            data = base64.b64decode(str(c.get("b64") or ""), validate=False)
            if len(data) < 46 or data[:4] != b"RIFF":
                return 'hablar: falta el audio ("b64" con un WAV)'
            hz = int.from_bytes(data[24:28], "little") or 16000
            canales = int.from_bytes(data[22:24], "little") or 1
            bits = int.from_bytes(data[34:36], "little") or 16
            seg = max(0.3, (len(data) - 44) / (hz * canales * bits / 8))
            if speaker.sonando():
                import time

                speaker.parar()  # la voz manda: corta un pitido que estuviera sonando
                time.sleep(0.15)
            if not speaker.tocar_wav(data, seg):
                return "hablar: el parlante está ocupado, no pude decirlo"
            texto = str(c.get("texto") or "")
            return f"hablar: digo en voz alta ({seg:.1f} s, voz {c.get('voz') or 'dueno'})" + (f": «{texto[:80]}»" if texto else "")
        except Exception as e:
            return f"hablar: falló: {type(e).__name__}: {e}"

    if cmd == "foto":
        try:
            return camara.foto()
        except Exception as e:
            return f"no pude sacar la foto: {type(e).__name__}: {e}"

    # Gesto (gesto.py): mira la cámara y, cuando ve el dedo del medio, se enoja: parpadea la luz roja
    # (GPIO 22) unos 3 s y además toca un sonido.
    #   {"cmd":"gesto","on":true}     empieza a mirar (2 cuadros por segundo, aunque nadie mire la web)
    #   {"cmd":"gesto","on":false}    deja de mirar (y corta el parpadeo de enojo si estaba)
    #   {"cmd":"gesto"}               estado: qué ve y por qué descartó lo último
    #   {"cmd":"gesto","enojo":true}  parpadea la roja una vez, como si hubiera visto el gesto (prueba)
    #   {"cmd":"gesto","enojo":false} corta ese parpadeo
    #   {"cmd":"gesto","sonido":true} toca el sonido una vez (prueba del parlante)
    #   {"cmd":"gesto","ver":true}    manda a Vista la máscara de piel del próximo cuadro
    #   {"cmd":"gesto","parlante":"plughw:Headphones"}  por dónde sale el sonido
    # No bloquea: el análisis corre en el hilo de la cámara, la luz la parpadea gpiozero y el sonido va en su hilo.
    if cmd == "gesto":
        try:
            return _gesto(c)
        except Exception as e:
            return f"gesto: falló: {type(e).__name__}: {e}"

    # Speaker (speaker.py): probar el parlante y elegir la salida de audio (la misma que usa el gesto).
    #   {"cmd":"speaker"}                     estado: salida elegida, salidas que hay, última prueba
    #   {"cmd":"speaker","probar":true}       dos pitidos por la salida elegida
    #   {"cmd":"speaker","tono":440,"seg":1}  un tono (50-8000 Hz, hasta 5 s)  ·  "vol":1-100 amplitud
    #   {"cmd":"speaker","todas":true}        recorre todas las salidas: 1 pitido la primera, 2 la segunda...
    #   {"cmd":"speaker","salida":"audifonos"}  o "respeaker", "hdmi", "plughw:..." (queda guardada)
    #   {"cmd":"speaker","on":false}          corta lo que esté sonando
    #   {"cmd":"speaker","mezclador":true}    volumen de ALSA de la salida elegida (o "tarjeta":"Array")
    #   {"cmd":"speaker","volumen":100}       lo fija y saca del silencio (queda guardado, se repone al arrancar)
    # No bloquea: aplay corre en un hilo daemon con timeout. También responde a "parlante".
    if cmd in ("speaker", "parlante"):
        try:
            return _speaker(c)
        except Exception as e:
            return f"speaker: falló: {type(e).__name__}: {e}"

    # Vibrar (vibrar.py): no hay motor vibrador conectado, así que vibra con el parlante: pulsos de un tono
    # grave por la salida de audio elegida en speaker.
    #   {"cmd":"vibrar"}                    vibra 3 s (pulsos de 80 Hz)
    #   {"cmd":"vibrar","seg":5,"hz":60}    cuánto dura (0.3-10 s) y a qué frecuencia (30-250 Hz)  ·  "vol":1-100
    #   {"cmd":"vibrar","continuo":true}    un solo tono, sin pulsos
    #   {"cmd":"vibrar","on":false}         lo corta  ·  {"cmd":"vibrar","estado":true}  cómo está
    # No bloquea: lo toca el hilo daemon de speaker.py (aplay con timeout).
    if cmd == "vibrar":
        try:
            return _vibrar(c)
        except Exception as e:
            return f"vibrar: falló: {type(e).__name__}: {e}"

    # Escucha por turnos (escucha.py): pitido al empezar a escuchar y pitido al terminar la frase.
    # El Pi no reconoce palabras: el cerebro transcribe y, cuando oye "bicho", manda "inicio":true.
    #   {"cmd":"escucha","inicio":true}     pitido de inicio y abre el turno; se cierra solo, con otro pitido,
    #                                       cuando la persona habló y lleva un rato callada (voz del ReSpeaker)
    #   {"cmd":"escucha","fin":true}        cierra ahora con pitido  ·  {"cmd":"escucha"}  estado
    #   {"cmd":"escucha","on":false}        desactiva el modo y corta el turno  ·  "on":true lo activa
    #   {"cmd":"escucha","pitido":"inicio"} prueba un pitido ("fin" el otro)  ·  "vol":1-100
    #   {"cmd":"escucha","silencio":0.9,"espera":6,"max":15}   tiempos
    # No bloquea: un hilo daemon vive solo mientras el turno está abierto; sensores publica escucha.abierta.
    if cmd in ("escucha", "turno"):
        try:
            return escucha.manejar(c)
        except Exception as e:
            return f"escucha: falló: {type(e).__name__}: {e}"

    # Luz del oído (oido_luz.py): los LEDs del ReSpeaker XVF3800 apuntan hacia donde llega la voz.
    #   {"cmd":"oido","on":true}      la prende  ·  {"cmd":"oido","on":false}  la apaga (y apaga los LEDs)
    #   {"cmd":"oido"}                estado: modo, hacia dónde apunta, qué oye
    #   {"cmd":"oido","modo":"chip"}  el propio micrófono prende el LED de la dirección (por defecto)
    #   {"cmd":"oido","modo":"suave"} el bicho desliza un punto de luz hacia el ángulo de la voz
    #   {"cmd":"oido","color":"azul"} color ("RRGGBB" o un nombre)  ·  "brillo":0-255
    #   {"cmd":"oido","probar":90}    (modo suave) apunta a ese ángulo 4 s  ·  "offset":grados, "sentido":1|-1
    #   {"cmd":"oido","leer":true}    cómo están los LEDs en el chip (solo lectura)
    # No bloquea: lo que habla con el USB corre en un hilo daemon que parte con "on":true.
    # Anillo (anillo.py): control total de los 12 LEDs del ReSpeaker.
    #   {"cmd":"anillo","estado":"piensa"}          la luz de un estado de lenguaje.json (igual que el simulador)
    #   {"cmd":"anillo","patron":"gira","color":"#5ac8fa","periodo":1.1}   un patrón suelto
    #   {"cmd":"anillo","leds":["ff0000","00ff00"]} un color por LED  ·  {"cmd":"anillo","led":3,"color":"rojo"}
    #   {"cmd":"anillo","efecto":"arcoiris"}        efecto del chip  ·  "brillo":0-255  ·  "seg":N  ·  "on":false
    # No bloquea: dibuja un hilo daemon (20 cuadros por segundo, solo si el cuadro cambia).
    # Expresar (expresar.py): luz + sonido de un estado de lenguaje.json, o una escena entera.
    #   {"cmd":"expresar","estado":"contento"}  ·  {"cmd":"expresar","escena":"perro"}  ·  "on":false corta
    if cmd == "expresar":
        try:
            return expresar.manejar(c)
        except Exception as e:
            return f"expresar: falló: {type(e).__name__}: {e}"

    if cmd in ("anillo", "aro"):
        try:
            return anillo.manejar(c)
        except Exception as e:
            return f"anillo: falló: {type(e).__name__}: {e}"

    if cmd == "oido":
        try:
            return _oido(c)
        except Exception as e:
            return f"oido: falló: {type(e).__name__}: {e}"

    # Flujo óptico ADNS-3080 (flujo.py, SPI en spidev0.0). Siempre confirma primero el ID 0x17.
    #   {"cmd":"flujo"}               una lectura: movimiento, dx, dy y calidad de superficie
    #   {"cmd":"flujo","on":true}     lectura continua (sale en los gráficos como flujo.*)
    #   {"cmd":"flujo","on":false}    la apaga
    #   {"cmd":"flujo","reset":true}  pone en cero el acumulado x, y
    if cmd == "flujo":
        return _flujo(flujo, "flujo", c)

    # Segundo ADNS-3080 (flujo2.py): chip select en el pin físico 26 = GPIO 7 = CE1 = spidev0.1.
    #   {"cmd":"flujo2"}  ·  "on":true/false  ·  "reset":true   igual que flujo (gráficos flujo2.*)
    #   {"cmd":"flujo2","pines":true}  muestra, sin cambiar nada, cómo están los chip select
    if cmd == "flujo2":
        if c.get("pines"):
            try:
                return flujo2.pines()
            except Exception as e:
                return f"flujo2: falló: {type(e).__name__}: {e}"
        return _flujo(flujo2, "flujo2", c)

    # Los dos sensores a la vez:
    #   {"cmd":"flujos"}               lectura de ambos
    #   {"cmd":"flujos","on":true}     ambos en continuo  ·  "on":false  apaga ambos
    #   {"cmd":"flujos","reset":true}  ambos acumulados en cero
    if cmd == "flujos":
        return _flujo(flujo, "flujo", c) + "  ||  " + _flujo(flujo2, "flujo2", c)

    # Ejemplo con un servo en el GPIO 18 (gpiozero viene en Raspberry Pi OS):
    #   from gpiozero import AngularServo
    #   servo = AngularServo(18, min_angle=0, max_angle=180)   ← crear una vez, fuera de la función
    # if cmd == "servo":
    #     servo.angle = float(c.get("deg", 90))
    #     return f"servo en {servo.angle}°"

    return None

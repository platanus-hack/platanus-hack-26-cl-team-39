# Pitch de Bicho

_Borrador para ensayar. Lo que está entre corchetes se completa en los ensayos: un número medido, el nombre de quien habla, lo que de verdad funcione ese día. Las voces y las palabras siguen [`MARCA.md`](MARCA.md)._

**Lo que el jurado tiene que llevarse, en una frase:** _le pidieron algo que no sabía hacer y lo aprendió solo, ahí mismo._

**Cuánto dura:** [confirmar en la charla «Cómo hacer un buen demo», sáb 20:00]. Abajo hay una versión de 3 minutos y una de 1 minuto. Si son menos de 3, se corta la parte de cómo funciona, nunca la demo.

## Cómo calza con la rúbrica

| Criterio | Peso | Dónde lo ganamos |
|---|---|---|
| Técnico | 25 % | Se escribe, instala y prueba su propio código, y vuelve atrás solo si falla. Oído con el ángulo de la voz. Relé para hablarle desde cualquier red. |
| Ambición | 20 % | Un robot que nadie programa, hecho en 36 horas: el cuerpo impreso, el hardware, el panel y el cerebro. |
| Ejecución | 20 % | La demo es en vivo, con el robot de verdad. Plan B listo (video y simulador). |
| Impacto | 20 % | Cualquiera le enseña hablando. Hoy cuida un patio; mañana, lo que necesites. |
| Originalidad | 15 % | No hay robots de casa que aprendan una habilidad nueva cuando se la pides. |

## Guion de 3 minutos

Sigue el orden de la guía de entrega: problema, objeto, lo que se le dice, la reacción que se ve, una decisión técnica y una limitación honesta.

| Tiempo | Qué se ve | Qué se dice |
|---|---|---|
| 0:00 | Bicho en la mesa, anillo en reposo. Lámina de portada. | «Este es Bicho. Hace un día y medio no sabía hacer nada. Y no lo programamos nosotros: se programa solo.» |
| 0:15 | Lámina: el problema. | «Los robots hacen lo que el fabricante les programó. La aspiradora aspira, y nada más. Si quieres que haga algo nuevo, necesitas un ingeniero y semanas.» |
| 0:35 | Lámina: qué es Bicho. | «Bicho es un robot que se programa solo. Si le pides algo que no sabe hacer, escribe el código, se lo instala, lo prueba y, si falla, vuelve atrás. Es el bicho que se parcha solo.» |
| 0:50 | Lámina: «Ya aprendió solo» (la tarjeta de firmware de bicho·dev con la v0.8.0). | «Y no es teoría. El equipo publicó la 0.5.0, que solo escucha. Hoy Bicho corre la 0.8.0, que instaló su propio cerebro: ahora usa la cámara y contesta con luces.» [Confirmar con Cristian y actualizar la versión el domingo.] |
| 1:05 | **Demo.** Pantalla grande: bicho·dev, sección Cerebro. | «Bicho, [lo que se le pide].» |
| | Anillo azul, se llena. En pantalla, el parche escribiéndose. | Bicho: «Eso no lo sé hacer todavía. Dame un minuto.» Quien presenta, mientras espera: «Lo que ven es el código que se está escribiendo él mismo. Cuando termine, se lo instala por WiFi y lo prueba antes de activarlo.» |
| | Anillo arcoíris. Bicho lo hace. | Bicho: «Listo. [Ahora sé …].» Quien presenta: «Le tomó [N] segundos. Nadie del equipo escribió esa línea.» |
| 2:10 | Lámina: cómo funciona (diagrama). | «Tiene un Oído que sabe de dónde le hablan, un Cerebro que decide en un segundo si le hablan a él y qué hacer, y escribe los parches con Claude. En la Raspberry, cada parche se prueba antes de activarse; si no responde en 60 segundos, vuelve solo al anterior. Y le podemos hablar desde cualquier red.» |
| 2:30 | Lámina: limitación honesta, con la respuesta real del Cerebro del sábado a las 12:07. | «Hoy aprende cosas chicas y se puede equivocar. Pero no se rompe: cuando le pidieron un sensor y el bus estaba apagado, no instaló nada y nos dijo qué habilitar. Y si un parche falla, vuelve solo al anterior.» |
| 2:45 | Lámina: impacto. | «Hoy cuida un patio: moja al perro del vecino y avisa si entra alguien. Mañana puede aprender a regar, o a avisarte si tu abuela se cayó, sin que nadie lo programe.» |
| 2:58 | Lámina de cierre con el logo. | «Bicho. El bicho que se parcha solo.» |

## Guion de 1 minuto

«Este es Bicho, un robot que se programa solo. [Demo: se le pide algo, «Dame un minuto», lo aprende y lo hace.] Le tomó [N] segundos y nadie del equipo escribió ese código: lo escribió él, se lo instaló, lo probó y, si fallaba, volvía atrás solo. Hoy cuida un patio; mañana aprende lo que le pidas. Bicho, el bicho que se parcha solo.»

## La demo

**Qué se le pide.** Algo que Bicho no sepa hacer (que no esté en el parche base 0.5.0), que use hardware conectado ese día y que se vea desde lejos. Se elige en el ensayo según lo que funcione:

| Pedido | Usa | Riesgo | Se ve |
|---|---|---|---|
| «Bicho, mira hacia donde te hablan» | Oído (ángulo) + ruedas o brazo | Bajo | Alto: se da vuelta hacia quien habló |
| «Bicho, si ves a alguien, prende la luz» | Cámara + foco o anillo | Medio | Medio |
| «Bicho, sigue esta pelota» | Cámara + ruedas | Alto | Muy alto |

Lo recomendado: ensayar el primero como demo principal y dejar el tercero como «una más» si sale en todos los ensayos.

**Quién hace qué**

- **Presenta:** [nombre]. Habla y le habla al robot.
- **Opera:** [nombre]. bicho·dev en la pantalla grande, en la sección Cerebro. Si el Oído no entiende, le escribe el pedido desde ahí (lo escrito también le llega).
- **Respaldo:** [nombre]. Video de 60 s y Simulador listos en otro computador.

**Antes de subir**

- [ ] Batería cargada (motores y Pi). Fuente de 5 V y 2,5 A a mano.
- [ ] Hotspot de 2,4 GHz prendido; Bicho conectado al relé (bicho·dev lo muestra en línea).
- [ ] Cerebro corriendo, con la clave de Anthropic y la del equipo.
- [ ] Bicho de vuelta en el parche publicado, para que la habilidad sea nueva de verdad (bicho·dev avisa que eso borra lo aprendido).
- [ ] Un ensayo completo en el escenario, con el ruido de la sala.

**Si algo falla**

- **No aprende a tiempo** (pasa 1 minuto): «Mientras termina, les muestro uno que aprendió esta mañana», y se pasa el video.
- **El hardware no responde:** la demo sigue en el Simulador de bicho·dev con el mismo pedido.
- **Se equivoca y vuelve atrás:** se muestra como parte del show. «Ven: se equivocó y volvió solo al parche anterior. Para eso está la curita.»

## Preguntas difíciles

| Pregunta | Respuesta |
|---|---|
| ¿Y si escribe algo peligroso? | No puede tocar su núcleo (`bichod.py`, `salida.py`, `oido.py`). Cada parche se prueba antes de activarse, y si no se reporta en 60 s vuelve solo al anterior. Lo que afecta a una persona espera la decisión del dueño. |
| ¿Cuánto tarda en aprender? | [Tiempo medido en los ensayos, del pedido a la acción]. |
| ¿Qué hicieron ustedes y qué hizo la IA? | Nosotros: el cuerpo, el hardware, el protocolo, el Oído, el relé, el panel y las reglas que hacen seguro que se reprograme. Las habilidades las escribe Bicho. |
| ¿Funciona sin internet? | Los reflejos corren en la Raspberry; para aprender necesita internet, porque escribe con Claude. |
| ¿Cuánto cuesta? | Hardware: [total del inventario]. Cada parche: [costo medido de Claude por aprendizaje]. |
| ¿Por qué no programarlo directamente? | Porque así cualquiera le enseña hablando, sin saber programar. |

## Video de 60 s

Se graba apenas funcione la primera demo completa, como respaldo.

1. (0–5 s) Bicho en reposo, el anillo respira. Texto: «Bicho no sabe hacer esto.»
2. (5–15 s) Alguien le pide la habilidad. Bicho: «Eso no lo sé hacer todavía.»
3. (15–35 s) Pantalla de bicho·dev con el parche escribiéndose, acelerado. Texto en mono: «escribiendo el parche 0.6…».
4. (35–50 s) Bicho lo hace. Texto: «Aprendió en [N] s. Nadie escribió ese código.»
5. (50–60 s) Logo horizontal sobre carbón: «El bicho que se parcha solo.»

## Textos de la entrega

- **Nombre:** Bicho
- **Una línea:** Un robot que se programa solo: si le pides algo que no sabe hacer, escribe, instala y prueba su propio código en vivo.
- **Descripción:** Bicho es un robot de cuatro ruedas con un solo ojo que nadie programa. Escucha de dónde le hablan y, cuando le piden algo que no sabe hacer, escribe el código con Claude, se lo instala por WiFi y lo prueba antes de activarlo. Si un parche falla, vuelve solo al anterior. Lo hicimos en 36 horas, con el cuerpo impreso en 3D y un panel para verlo aprender en vivo.

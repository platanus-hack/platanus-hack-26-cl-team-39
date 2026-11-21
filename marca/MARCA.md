# Bicho · manual de marca

_Fuente de verdad de la marca para el equipo y sus Claude. La versión para mirar está publicada como página (link en `contexto/links.md`). Los logos están en [`logo/`](logo/) y se regeneran con `python3 marca/generar_logo.py && bash marca/exportar_png.sh`. El estilo visual es «Cristal claro», el mismo de bicho·dev: la fuente de los valores es [`web/src/index.css`](../web/src/index.css)._

## El nombre

**Bicho.** Tiene dos sentidos y una curita:

1. **Un bicho.** Chico, curioso, con un solo ojo, anda solo por el patio en sus cuatro ruedas.
2. **Un bug.** A los errores de software se les dice bichos (_bugs_). Este bicho arregla los suyos.
3. **La curita.** Se parcha solo: escribe, instala y prueba su propio código, y si un parche nuevo falla, vuelve al anterior. La curita está en el logo, encima del ojo.

En los textos de la marca va «Bicho», con mayúscula y sin artículo («Bicho aprendió»). Al hablar, «el bicho» está perfecto. En el logo va en minúsculas. El panel sigue llamándose **bicho·dev**.

## La idea

- **Frase de marca:** _El bicho que se parcha solo._
- **Frase larga:** _Lo que no sabe hacer, lo aprende en vivo._
- **Para el formulario de Platanus (una línea):** Bicho es un robot que se programa solo: si le pides algo que no sabe hacer, escribe, instala y prueba su propio código en vivo.
- **Lo que hace distinto a Bicho:** no viene con habilidades fijas. Cada cosa nueva que aprende es un parche que él mismo escribe con Claude, se instala por WiFi, se prueba y, si falla, se deshace solo.

### Caso de uso (propuesta, por confirmar con el equipo)

Lo central del pitch es que **aprende en vivo**. El escenario donde lo mostramos es **cuidar el patio**: patrulla, ve al perro del vecino y lo moja con el chorro; si entra una persona, avisa y espera que el dueño decida. Las escenas ya están en [`bicho/lenguaje.json`](../bicho/lenguaje.json). Lo de cuidar el patio es el ejemplo; lo que se lleva el jurado es que, si mañana le pides otra cosa, la aprende.

## Personalidad

| Bicho es | Bicho no es |
|---|---|
| Curioso: mira todo, pregunta | Un asistente servil que dice que sí a todo |
| Porfiado: si no le sale, prueba de nuevo | Un robot de película que lo sabe todo |
| Honesto: dice lo que no sabe y cuando se equivoca | Un juguete que repite frases |
| Buena onda, pero cuida su patio | Agresivo ni amenazante |

## Voz

Vale para lo que dice Bicho (por el parlante, en bicho·dev) y para cómo hablamos de él (pitch, README, redes).

1. **Frases cortas.** Primero lo que hace, después el porqué.
2. **Dice lo que no sabe.** «Eso no lo sé hacer todavía. Dame un minuto.»
3. **Admite los errores en voz alta.** «Me equivoqué. Vuelvo al parche anterior.»
4. **Chileno natural, sin caricatura.** Tutea. «Al tiro» sí; garabatos y chilenismos forzados, no.
5. **Nunca promete lo que no hace.** Si algo es una idea, se dice que es una idea.

Un ejemplo real, del Cerebro el sábado a las 12:07, cuando le pidieron un sensor por SPI y el bus estaba apagado: «No instalé nada: el SPI del Pi está apagado… Sigo en la 0.8.0, con todo igual que antes.» Así suena Bicho.

### Qué dice en cada estado

Los estados son los de `bicho/lenguaje.json`; las frases son ejemplos del tono, no un guion fijo.

| Estado | Bicho dice |
|---|---|
| Hola | «Hola. Te estaba esperando.» |
| Te escucha | (no habla: el anillo respira en azul) |
| No puedo | «Eso no lo sé hacer todavía.» |
| Pide una pieza | «Si me pones un sensor de luz, aprendo a usarlo.» |
| Se reprograma | «Dame un minuto. Me estoy escribiendo un parche.» |
| Prueba algo nuevo | «Probando…» |
| Aprendió algo | «Listo. Ahora sé seguir una pelota.» |
| Se equivocó | «Uy. No me resultó.» |
| Volvió atrás | «Volví al parche anterior. Sigo como antes.» |
| Algo raro | «Hay algo en el patio.» |
| Advertencia | «Este es un patio privado. Ya le avisé al dueño.» |
| Misión cumplida | «Listo. Patio tranquilo.» |

## Vocabulario

- **Bicho** es el robot.
- **Un parche** es cada versión nueva que Bicho se escribe: «Bicho se instaló el parche 0.6: seguir una pelota». En bicho·dev, la pestaña Versiones se puede llamar **Parches**.
- Las partes del cuerpo: **Ojo** (anillo + cámara), **Oído** (ReSpeaker), **Cerebro** (el servicio que decide con Claude).
- Se dice **volver atrás**, no «rollback», y **aprender**, no «deployar».

## El estilo: Cristal claro

Es el de bicho·dev, y vale para todo: el panel, las láminas, el video y la entrega.

- **Fondo:** crema cálido con manchas de color difusas (durazno, amarillo, celeste, lila). Nunca un blanco plano ni un negro.
- **Vidrio:** cada pieza de contenido es una placa de vidrio blanco translúcido, con un borde de luz arriba y sombras muy suaves en capas.
- **Tinta casi negra y un azul de acento.** El amarillo banana es el del ícono y de lo que se destaca.
- **Números gigantes y finos** (peso 200), como la versión del firmware en bicho·dev.
- **Movimiento suave:** las piezas entran subiendo y pasando de borrosas a nítidas.

## Logo

**El ojo parchado:** el anillo de 24 LEDs con la cámara al medio, tal como está en la punta del brazo del robot, con una curita que parcha el anillo. **La palabra:** «bicho» dibujada con trazos de punta redonda; la «o» es el ojo y lleva el lente al medio. **El ícono:** el ojo sobre el cuadrado amarillo de bicho·dev.

| Pieza | Archivo | Para qué |
|---|---|---|
| Ícono | `logo/bicho-icono.svg`, `bicho-icono-512.png`, `apple-touch-icon.png` | La cara de Bicho: avatar, ícono de app, sticker, el lugar del ícono en bicho·dev |
| Favicon | `logo/favicon.svg`, `favicon-32.png` | 32 px o menos: el anillo es continuo porque los puntos no se distinguen |
| Horizontal | `logo/bicho-horizontal-fondo-claro.svg` (+ PNG) | Por defecto en láminas, README y encabezados, sobre el fondo crema o el vidrio |
| Ojo solo | `logo/bicho-ojo-fondo-claro.svg` (+ PNG) | Cuando el nombre ya está escrito al lado |
| Palabra sola | `logo/bicho-palabra-fondo-claro.svg` | Cuando el ojo o el ícono ya están en la pieza |
| Cuadrado | `logo/bicho-cuadrado.svg` / `.png` y `/project-logo.png` | Entrega en Platanus: el ícono y la palabra sobre el fondo crema (1000 × 1000, 369 KB) |
| Para fondo oscuro | `logo/bicho-*-fondo-oscuro.svg` | Solo si toca una pantalla negra (por ejemplo, un video de noche) |

**Reglas**

- **Espacio libre:** alrededor del logo, al menos el ancho del lente (el círculo del medio del ojo).
- **Tamaño mínimo:** el ojo, 24 px; el horizontal, 120 px de ancho. Bajo 32 px se usa el favicon.
- **La curita va siempre arriba a la derecha y en salmón.** No se gira, no se cambia de color y no se saca.
- **La pupila menta y la curita salmón son los colores del robot** (sus piezas impresas y su parachoques) y viven solo en el logo.
- **No:** estirar, rotar, agregar sombras o contornos (el ícono trae su propia sombra en el cuadrado), cambiar la letra, ni ponerlo sobre una foto sin contraste: en ese caso, va sobre una placa de vidrio.

## Colores

Los valores son los de bicho·dev (`web/src/index.css`).

| Nombre | Valor | Uso |
|---|---|---|
| Tinta | `#1D1D1F` | Texto principal, el anillo y la palabra del logo |
| Tinta 2 | `rgba(60, 60, 67, .74)` (sobre crema se ve `#6D6B6F`, 4,7:1) · en láminas `#55545A` (6,9:1), para que se lea en el proyector | Texto secundario, bajadas |
| Tinta 3 | `rgba(60, 60, 67, .5)` (2,6:1: no alcanza para texto) | Rótulos chicos de la interfaz, como en bicho·dev; en láminas, solo en tamaños de 44 px o más |
| Línea | `rgba(60, 60, 67, .12)` | Separadores finos |
| Azul | `#007AFF` · texto chico `#0058C7` | Acento: links, foco, el estado «te escucha», la palabra que se destaca |
| Banana | degradé `#FFE46B` → `#FFC700` → `#FFAD00` · texto `#7A5600` | El ícono y lo destacado (por ejemplo, «Más nuevo que lo publicado») |
| Verde | `#34C759` · texto `#1C7A36` | Conectado, aprendió, salió bien |
| Rojo | `#FF3B30` · texto `#B3261E` | Alerta, en vivo, no puede |
| Naranja | `#FF9F0A` | Esperando, algo raro |
| Fondo | degradé `#FDF4EC` → `#F8F1F2` → `#EEF2FB` (155°) | Fondo de pantalla, láminas y portadas |
| Manchas | `#FFC6A0`, `#FFE57A`, `#B4DBFF`, `#D8C8FF`, `#FFD9BD` | Las manchas difusas sobre el fondo |
| Vidrio | blanco al 66 % arriba y 44 % abajo, borde de luz blanco | Tarjetas y paneles |
| Del robot | menta `#8FDCC4`, salmón `#F4996F`, gasa `#FFD4BF` | Solo en el logo |

**Colores de estado:** son los del anillo en `lenguaje.json` (azul escucha `#2F80FF`, celeste piensa `#5AC8FA`, verde aprendió `#34C759`, amarillo pregunta `#FFC700`, rojo alerta `#FF3B30`) y muestran lo que siente o hace Bicho. Siempre van con su nombre al lado.

## Tipografía

- **En bicho·dev:** la letra del sistema (SF Pro y SF Mono en equipos Apple), como está hoy.
- **En láminas, video y documentos:** [Inter](https://fonts.google.com/specimen/Inter) (Google Fonts, licencia OFL), lo más parecido a SF Pro, y [JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono) (OFL) para versiones, comandos y datos.
- **Títulos** en peso 650 con el espaciado apretado (−0,015 a −0,03 em). **Números grandes** en peso 200 con −0,05 em, como la versión del firmware. **Texto** en 400.
- **Escala de las láminas** (lienzo de 1920 × 1080): 240 (números), 120 (frase de impacto), 80 (título), 44 (subtítulo), 32 (texto) y 26 px (rótulos).
- El logo no usa ninguna letra: es dibujo.

## Vidrio, radios y sombras

- **Placa de vidrio:** degradé blanco del 66 % al 44 %, borde de 1 px de luz y sombras en capas, la más larga de unos 70 px de difuminado, en lila muy tenue. En bicho·dev además desenfoca lo de atrás (`backdrop-filter`).
- **Radios** (bicho·dev): ventana 30 px, tarjeta 24 px, mosaico 16 px y píldora redonda. En láminas, 44 px.
- **Píldoras** (cápsulas) para estados: un punto de color y una palabra, sobre blanco.
- **Foco:** anillo azul de 3 px al 42 %, separado 2 px.

## Movimiento

- **Curva:** `cubic-bezier(.2, .8, .2, 1)`, la de bicho·dev.
- **Entrada:** las piezas suben unos 14 px y aparecen en 0,75 s; en láminas, además pasan de borrosas a nítidas, una tras otra.
- **Conexión:** el punto verde late (se expande y se apaga cada 2,4 s).
- **El ojo** sigue los patrones del anillo: respira en reposo (4,5 s), gira cuando piensa, arcoíris cuando aprende.
- Sin movimiento cuando el sistema pide reducirlo.

## Dónde va

- **En el robot:** sticker del ícono en el pecho, junto a la matriz 8 × 8.
- **bicho·dev:** el ícono amarillo con el ojo puede reemplazar al de la barra lateral, y el favicon al actual.
- **Entrega en Platanus:** `project-logo.png` (ya reemplazado), nombre «Bicho» y la frase de una línea de arriba en `platanus-hack-project.jsonc`.
- **Deck y video:** fondo crema con manchas, placas de vidrio, el ojo animado. El deck ya está hecho así (link en `contexto/links.md`).

## La palabra para despertarlo

Sigue siendo «bicho»: el Cerebro ya la reconoce (regex `LO_NOMBRAN` en [`cerebro/cerebro.mjs`](../cerebro/cerebro.mjs)). No hay que cambiar nada.

# Bicho · estructura de 32 × 20 cm, lista para imprimir

Equipo CRBRC · Platanus Hack 26 · versión v3.2 (32 × 20 cm, placas enteras), 21-nov-2026. Cada placa es una sola pieza rígida, sin junta ni empalme.

## Qué hay en esta carpeta

| Carpeta o archivo | Qué es |
|---|---|
| `STL/` | Las 19 piezas, cada una sola, en milímetros. Ya vienen orientadas como se imprimen (la cara que va a la cama está en Z = 0). |
| `3MF_bandejas/` | 14 bandejas. **Las 3 placas (B01 a B03) necesitan una cama de 330 × 210 mm o más**, por ejemplo Bambu H2D, Prusa XL, Creality K2 Plus, Elegoo Neptune 4 Max, Anycubic Kobra 3 Max o Ender 5 Plus. El resto cabe en una cama de 220 × 220. |
| `bicho_v3_32cm.blend` | El modelo completo de Blender con las 3 versiones armadas. |
| `generar_bicho_v3.py` | El script paramétrico. Si cambia una medida, se edita aquí y Blender regenera todo en unos 20 s. |

Las 19 STL pasaron el chequeo de malla cerrada: 0 bordes abiertos y 0 aristas con más de 2 caras.

**Imprime desde los archivos de este repo (rama `dev`).** El 21-nov a las 12:15 se corrigieron B00, B06 y B07 (detalle abajo). Mientras no se actualice Drive, los archivos de allá tienen esos errores.

**Revisión del 21-nov, 12:15.** Se revisaron las 19 STL y las 14 bandejas: malla cerrada, todas las piezas apoyadas en la cama, ninguna pieza pisa a otra y todas caben en su cama. Se corrigieron estas cosas:
- **B00, prueba de tolerancia:** la cola de milano medía 20 mm de alto y dejaba las dos tiras flotando 10 mm sobre la cama. Ahora toda la pieza mide 4 mm de alto.
- **B06, parachoques (P05):** las dos orejas para atornillarlo quedaban sueltas, a 2 mm del cuerpo, porque el hueco de atrás les cortaba la unión. Ahora cruzan hasta la pared del frente y quedan en una sola pieza con el resto. Se movieron a y = ±60 mm para no tapar los ToF ni sus cables, así que se atornillan en la placa inferior en x = 140, y = ±60.
- **B07, eslabón 2 (P10):** el alojamiento del MG90S quedaba 0,5 mm sobre la cama al imprimir de canto. Ahora parte al ras de la cama y no necesita soportes.
- **Soportes:** P02, P12 y P18 sí los necesitan, aunque antes decía que no. La lista corregida está en «Qué piezas llevan soportes».
- **Tornillería:** había largos que no alcanzaban para la tuerca, y las columnas con M3×50 chocaban en el piso del medio. La tabla de «Tornillería» ya está corregida.

## Medidas de la estructura

- **Placa estándar de 320 × 200 mm.** Es igual en los tres pisos (inferior, superior y cubierta) y tiene 4 mm de espesor. Abajo lleva nervios de 6 mm: uno en todo el borde y dos transversales a ±40 mm del centro. Las esquinas son redondeadas con radio de 15 mm.
- **Rejilla de agujeros M3 de Ø3,4 mm con paso de 10 mm** de centro a centro, en toda la placa. Entre un agujero y el siguiente quedan 6,6 mm de material, que es lo que pidieron. Cualquier pieza se atornilla en cualquier punto.
- **Forma para las ruedas:** muescas de 76 × 6 mm a ±104 mm del centro. Los ejes de las ruedas quedan a 208 mm uno del otro y la trocha mide 228 mm, 24 mm más ancha que antes.
- **Altura de los pisos:** la placa inferior va a 45 mm del suelo, la superior a 89 mm y la cubierta a 133 mm. Entre placas hay 40 mm y quedan unos 34 mm libres bajo los nervios, suficiente para el portapilas de 21 mm y la Pi con disipador.
- **Cada placa es una sola pieza rígida de 320 × 200 mm**, sin junta. Pesa unos 257 g y tarda unas 9,7 h en una impresora clásica o 4 h en una rápida.
- **Cama:** la placa mide 320 mm y no entra en camas de 220 o 256 mm, ni siquiera en diagonal. Si la impresora del equipo tiene una cama más chica, la versión anterior en dos mitades sigue en Drive, en la carpeta «v3.1».

## Antes de nada: la prueba de tolerancia (20 min)

Imprime la bandeja **B00** con el mismo filamento y perfil que las placas. Es una tira con agujeros de 3,2, 3,4 y 3,6 mm. La cola de milano que trae ya no se usa en las placas; sirve igual para medir el juego de encaje de la impresora.

- Si el M3 entra justo en el de 3,4 mm, todo está bien.
- Si entra apretado, sube la compensación XY de agujeros a +0,15 mm.

Así no se pierden 10 horas de placa por una tolerancia.

## Perfiles

Los perfiles son para boquilla de 0,4 mm. Configúralos en el slicer como «proceso» y aplícalos por bandeja.

| Perfil | Material | Boquilla / cama | Capa | Paredes | Sup. / inf. | Relleno | Ventilador | Notas |
|---|---|---|---|---|---|---|---|---|
| **PLA-ESTRUCTURA** (placas y columnas) | PLA o PLA+ | 210 / 60 °C | 0,20 mm | 4 | 5 / 5 | **40 % giroide** | 100 % desde la capa 3 | Para las placas: brim de 5 mm, para que una pieza de 32 cm no se levante en las esquinas. PEI liso limpio con alcohol. Pata de elefante 0,15 mm. Agujeros +0,1 mm. |
| **PETG-MECÁNICA** (brazo, torre, cunas) | PETG | 240 / 80 °C | 0,20 mm | 4 | 5 / 5 | 40 % giroide | 40 % | Brim de 4 mm en los eslabones. Pegamento en barra si la cama es PEI liso. |
| **PLA-SOPORTES** (cámaras, flujo, cara, anillo) | PLA | 210 / 60 °C | 0,20 mm | 3 | 4 / 4 | 25 % giroide | 100 % | Soportes solo en las piezas de la lista de abajo. |
| **TPU-PARACHOQUES** | TPU 95A | 225 / 45 °C | 0,24 mm | 3 | 4 / 4 | 30 % giroide | 50 % | Todo a 25 mm/s. Retracción de 0,8 mm o ninguna. Si no hay TPU, usa PETG con el perfil mecánico. |

**Por qué las placas van en PLA y no en PETG.** El PLA es casi el doble de rígido (unos 3,5 GPa contra 2,1 GPa del PETG), y en una placa larga lo que importa es que no se flexione. El 40 % de giroide con 4 paredes y 5 capas arriba y abajo, más los nervios, deja una flecha menor a 0,1 mm con 2 kg encima. Las piezas que reciben golpes o torque (brazo y cunas de motor) van en PETG porque es más tenaz.

**Orientación.** Ya viene resuelta en las STL:
- Las placas se imprimen con la cara superior contra la cama, nervios hacia arriba, sin soportes.
- Los eslabones del brazo van de canto, para que las capas sigan el largo.
- La torre (V2) va acostada, para que aguante un vuelco.

**Qué piezas llevan soportes.** Todas las demás van sin soportes: desactívalos o usa «solo desde la cama».

| Pieza | Bandeja | Soporte | Dónde |
|---|---|---|---|
| P14 · Cabeza de muñeca | B08-V1 | Árbol | Bajo el disco de la cara, que queda a 44 mm de la cama. |
| P02 · Torre | B08-V2 | Normal | Bajo el tubo: acostada, queda a 14 mm de la cama. |
| P03 · Cara en la torre | B09-V2 | Árbol | Bajo el disco. |
| P12 · Anillo del parlante | B09-V2 | Árbol | Bajo el disco de 100 mm, que queda a 16 mm de la cama y solo se apoya en el cubo central. |
| P18 · Cara frontal | B09-V3 | Árbol | Bajo el disco, que queda a 26 mm de la cama. |

Dos zonas que **no** necesitan soporte:
- **P06**, el soporte de flujo óptico: tiene un puente de 31 mm.
- **P07**, la torreta: por dentro, el marco del servo vuela 7 mm. Puede colgar un poco, pero no se ve ni afecta el calce.

**Al abrir una bandeja:** si el slicer avisa que alguna pieza se sale de la cama, o si el brim queda afuera, usa «Ordenar» (tecla A). Las piezas vienen a 3 o 6 mm de la esquina.

## Imprimir en el evento: Bambu Lab A2L

En la sala hay varias **Bambu Lab A2L**, con cama de **330 × 320 mm** y placa de PEI texturada. Las placas enteras de 320 × 200 caben, así que no hace falta la versión en dos mitades. También hay una Creality cerrada: si es una K1 Max (cama de 300 × 300), las placas no entran; si es una K2 Plus (350 × 350), sí. El modelo se ve en su pantalla. Mientras no se sepa, úsala solo para piezas chicas.

**Reparto con 2 A2L:**
- **A2L n.º 1:** B00 y después las placas B01, B02 y B03, una por trabajo.
- **A2L n.º 2:** el brazo (B07), las cunas (B05), las columnas (B04) y los soportes (B09).

**Pasos en Bambu Studio:**
1. Elige la impresora **Bambu Lab A2L**, con boquilla de 0,4 y placa **Textured PEI Plate**.
2. Abre el `.3mf` de `3MF_bandejas/`.
3. Elige el filamento y el proceso **0.20 mm Standard**. Después cambia lo que dice la tabla de perfiles: paredes, capas arriba y abajo, y relleno.
4. **Placas:** el lado de 320 mm va en el eje de 330, de izquierda a derecha. Usa un **brim de 4 mm**: con 5 mm llega justo al borde de la cama. En PEI texturada no se usa pegamento, ni con PETG.
5. Soportes apagados, salvo en las piezas de la tabla de soportes.
6. Aprieta **Slice** y revisa la vista previa capa por capa.
7. Para mandarlo, hay dos formas:
   - por WiFi, con **Print**, si la impresora está vinculada;
   - con **Export plate sliced file** (`.gcode.3mf`), copiándolo a un pendrive o microSD que se conecta a la impresora y se elige en su pantalla.

**Cuidados:**
- La A2L es abierta y mueve la cama en el eje Y. Déjala lejos del aire acondicionado y de la ventana para que no se levanten las esquinas.
- Mira la primera capa de cada placa antes de dejarla sola.

## Bandejas y tiempos

Los tiempos son estimados a partir del volumen extruido:
- **Clásica:** Ender 3 o Prusa MK3, a unos 6 mm³/s.
- **Rápida:** Bambu P1S/X1/A1 o Prusa MK4/Core One, a unos 15 mm³/s.

| Bandeja | Qué lleva | Perfil | g | h clásica | h rápida |
|---|---|---|---|---|---|
| B00 | Prueba de tolerancia | PLA-ESTRUCTURA | 6 | 0,3 | 0,2 |
| B01 | Placa inferior (entera) | PLA-ESTRUCTURA | 257 | 9,7 | 4,0 |
| B02 | Placa superior (entera) | PLA-ESTRUCTURA | 257 | 9,7 | 4,0 |
| B03 | Cubierta (entera) | PLA-ESTRUCTURA | 257 | 9,7 | 4,0 |
| B04 | 16 columnas de 40 mm | PLA-ESTRUCTURA | 37 | 3,3 | 2,5 |
| B05 | 4 cunas de motor TT | PETG-MECÁNICA | 48 | 2,2 | 1,2 |
| B06 | Parachoques | TPU | 41 | 1,6 | 0,7 |
| B07 | Brazo: torreta, horquilla, eslabón 1, eslabón 2, dedo | PETG-MECÁNICA | 102 | 4,3 | 2,1 |
| B08-V1 / V2 / V3 | Muñeca (V1 con cara; V2 con la torre; V3 con el barredor) | PETG-MECÁNICA | 32 / 59 / 22 | 1,3 / 2,4 / 1,0 | 0,6 / 1,1 / 0,6 |
| B09-V1 / V2 / V3 | Soportes de cámara, de flujo óptico y de la cara | PLA-SOPORTES | 59 / 109 / 70 | 2,8 / 4,8 / 3,2 | 1,5 / 2,3 / 1,6 |

Para **un robot V1 completo** se imprimen B00 a B07, más B08-V1 y B09-V1. Son unos 45 h en una impresora clásica o 21 h en una rápida, y gastan cerca de 0,87 kg de PLA, 0,18 kg de PETG y 0,04 kg de TPU.

## Orden si el tiempo no alcanza

La entrega cierra el domingo a las 9:00.

1. **B00** (20 min) y después **B07, el brazo**. Es lo que se ve en el demo y se puede probar sobre la mesa sin chasis.
2. **B01, la placa inferior**, más **B05, las cunas de motor**. Con eso el robot ya anda.
3. **B04**, las columnas. Se pueden reemplazar por separadores de latón del kit (ítem 11) que sumen 40 mm.
4. **B03, la cubierta**, y **B09**, los soportes de sensores.
5. **B02, la placa superior.** Si no alcanza, se puede usar una placa acrílica del kit de 4WD como piso del medio, apoyada en las mismas columnas.
6. **B06**, el parachoques.

Con dos impresoras: la de cama grande saca las 3 placas y la otra todo lo demás.

## Tornillería (M3 salvo donde se indique)

| Uso | Cantidad |
|---|---|
| Columnas entre pisos | 8 varillas roscadas M3 × 100 mm, o tornillos M3×100, que atraviesan los 3 pisos (92 mm), con una tuerca en cada punta: 16 tuercas, o 32 con contratuerca. **No sirven 16 M3×50:** la tuerca del piso de abajo quedaría justo bajo la columna del piso de arriba, porque las columnas de los dos pisos van en el mismo punto. |
| Cunas de motor a la placa | 16 M3×10 + 16 tuercas |
| Motores TT a la cuna (por las ranuras) | 8 **M3×35** + 8 tuercas. De pared a pared la cuna mide 28,8 mm, así que un M3×30 deja solo 1,2 mm para la tuerca. |
| Torreta del brazo | 4 M3×10 + 4 tuercas |
| Soportes de cámara | 2 **M3×10** + 2 tuercas por soporte. La base de 3 mm más la placa de 4 mm suman 7 mm, así que un M3×8 no alcanza para la tuerca. |
| Soportes de flujo óptico | 4 **M3×10** + 4 tuercas por soporte, por lo mismo. |
| Parachoques | 2 **M3×12** + 2 tuercas, en la placa inferior en x = 140, y = ±60. La oreja de 4 mm más la placa de 4 mm suman 8 mm. |
| Raspberry Pi 3B | 4 M2,5×16 + 4 tuercas + 4 separadores de 5 mm. **Ojo:** los agujeros de la Pi forman un rectángulo de 58 × 49 mm y no calzan con la rejilla de 10 mm. Abre 2 agujeros con broca o fíjala con 2 tornillos y una amarra. |
| Servos (MG995 y MG90S) | Los tornillos del horn y de las orejas que trae cada servo (ítem 127). Se autoroscan en agujeros de 2,2 a 2,8 mm. |

## Armado

1. **Placas:** saca el brim y repasa los agujeros con una broca de 3,4 mm a mano si alguno quedó cerrado.
2. **Placa inferior:** atornilla las 4 cunas P24 por abajo, a ±80 mm en X y ±80 mm en Y. Mete cada motor TT con el eje hacia afuera y pasa 2 M3×35 por las ranuras y los agujeros del motor. Las ranuras tienen ±7 mm de juego para calzar donde caigan los agujeros. Después van las ruedas.
3. **Sensores de flujo:** los dos ADNS-3080 van en sus soportes P06, bajo la placa, a ±100 mm del centro. Desenrosca cada lente M12 unos 3 mm para que enfoque el suelo a unos 28 mm.
4. **Piso 1:** los dos portapilas de 4×18650, el fusible y el interruptor. Pon las columnas de 40 mm en las 8 posiciones (±130 y ±20 en X, ±80 en Y) y encima la placa superior.
5. **Piso 2:** la Pi junto al centro, para que el cable de la cámara de 1 m llegue al brazo. También van los PCA9685, los TB6612, el LM2596, el convertidor de servos, los ADS1115 y la MPU-6050 al centro. Después la segunda tanda de columnas y la cubierta.
6. **Cubierta:** la torreta del brazo va en el centro con 4 M3 a la rejilla. Después la UPS, el parlante, los soportes de las ESP32-CAM y, en V2, la torre, o en V3, la cara frontal y el barredor.
7. **Brazo:** centra cada servo en 90° con el tester (ítem 129) antes de atornillar los horns. Así el cero mecánico coincide con el cero del firmware.

## Lo que hay que medir antes de imprimir

- **Agujeros de montaje del motor TT:** el modelo supone dos agujeros pasantes de 3 mm, paralelos al eje. Las ranuras de la cuna cubren entre 9 y 25 mm del eje del motor. Si tus motores tienen otro patrón, avisa y se regenera la cuna.
- **Diámetro del parlante omnidireccional:** se supuso de 90 mm (anillo P12, solo en V2). El parlante del inventario (#130) es cuadrado, de 40 a 50 mm: si se elige V2, hay que regenerar P12.
- **Alto del portapilas de 4 celdas:** se supuso de 21 mm. Hay 34 mm libres.

# Brazo v4 de Bicho: piezas definitivas para imprimir

21-nov-2026 · Equipo CRBRC · Platanus Hack 26. **Reemplaza al brazo de la bandeja B07** (P07-P11, P14, P15 de la v3): no imprimir B07 ni B08.

## ✅ PLAN VIGENTE: 3 impresoras en paralelo, ~3 h 35 min (21-nov, 18:00)

Están ya laminadas en [`SD_3_impresoras/`](SD_3_impresoras/). Hay que lanzar las 3 al mismo tiempo:

| Impresora | Archivo | Piezas | Tiempo |
|---|---|---|---|
| **Creality CR-3040 Pro** (300 × 300 × 400, Bowden, BLTouch, firmware V0.09) | `BRAZO_CR3040.gcode` | P09B, P10A, P10B, 2 × P36, P37: planas y tubos, sin soportes | **3 h 11 min** · 47 g |
| **Bambu A1 n.º 1** | `T2_A1n1_torreta_dedos_bujes.gcode.3mf` | P07 (soporte árbol interior), P31, P32, P33, P34, P41 | **3 h 34 min** · 102 g |
| **Bambu A1 n.º 2** | `T3_A1n2_cunas_plataforma_palma.gcode.3mf` | P35, P08, P30, P09A, P40 | **3 h 21 min** · 110 g |

**Por qué este reparto.** La CR-3040 Pro es grande, pero lenta con soportes: es Bowden con Marlin, y la torreta con soporte árbol tardaba 4,7 h en ella. Por eso le tocan las piezas planas y los tubos, que imprime bien en su cama de vidrio, y la torreta va en una A1. Así las 3 terminan casi juntas.

**Perfil de la CR.** No hay un perfil oficial de la CR-3040 Pro en Bambu Studio. Se usó el de la **Creality CR-10 V2**, que tiene el mismo volumen y la misma arquitectura, con estos ajustes:
- retracción Bowden de 5 mm;
- G29 con BLTouch;
- velocidades de 50 a 100 mm/s;
- aceleración de 1000;
- sin skirt;
- ascenso recto al terminar.

El G-code de la CR quedó solo con comandos Marlin estándar y todo dentro de la cama (X 2-295, Y 2-190).

**Antes de lanzar la CR:**
- Limpia el vidrio con alcohol.
- Pon PLA a 210 °C con la cama a 60 °C.
- Mira la primera capa: si no pega, sube la cama a 65 °C o usa pegamento en barra.

**Copia en Drive:** https://drive.google.com/drive/folders/1tgVAXhTr5cy_0PL6q8t-ZDHyu3ACUdJh (carpeta «3_IMPRESORAS_YA»).

## (Plan anterior) Archivos para la SD: 2 bandejas de menos de 5 h, en paralelo ✅

**Plan rápido** (21-nov, 17:30): todo el brazo y los soportes de sensores se imprimen en **2 bandejas, una por impresora y al mismo tiempo**. Están ya laminadas en [`SD/`](SD/) y se terminan en unas **4 h 20 min**.

| Bandeja | Qué lleva | A1 · PLA | A2L · PLA |
|---|---|---|---|
| **R1** · `R1_brazo_placas_cunas_y_sensores` | P09A, P09B, P10A, P10B, P35, P30, P34, 2 × P36, P37, P40, P41 | **4 h 19 min · 131 g** | 4 h 26 min · 133 g |
| **R2** · `R2_torreta_plataforma_y_dedos` | P07, P08, P31, P32, P33 | **4 h 10 min · 130 g** | 4 h 20 min · 132 g |

**Reparto confirmado (21-nov, 17:45): 2 Bambu Lab A1 libres** (identificadas en video por la etiqueta «A1» del cabezal y el pórtico doble; cama de 256 × 256).
- **A1 n.º 1 → R1** (`SD/A1_PLA/R1_…`): 4 h 19 min.
- **A1 n.º 2 → R2** (`SD/A1_PLA/R2_…`): 4 h 10 min.
- Las dos terminan en **unas 4 h 20 min**, contando calentamiento y nivelación.

**Cómo se imprime:**
1. Copia a la SD la carpeta de tu impresora (`SD/A1_PLA` o `SD/A2L_PLA`).
2. Pon **R1 en una impresora y R2 en otra al mismo tiempo**.
3. Si solo hay una libre, empieza con R1 (el brazo) y deja R2 para la siguiente que se libere.
4. Para liberar una A2L, la placa de arriba (B02) puede cambiarse por la placa acrílica del kit 4WD: la guía general ya lo dice.

**Perfil rápido, aplicado a todo:**
- **PLA Basic.** Imprime más rápido que el PETG y en el cálculo es más resistente y más rígido; solo es más frágil ante golpes.
- **Capa de 0,28 mm.**
- **3 paredes y 3/3 capas arriba y abajo.** Las placas de 5 mm quedan casi macizas.
- **15 % de relleno giroide.**
- **Brim de 2 mm.**
- **Soporte árbol solo en R2**, dentro de la torreta.

Todo sigue por sobre el torque de bloqueo de los servos: el servo sigue siendo el fusible. Las carpetas `SD/A1_PETG` y `SD/A2L_PETG` existen por si acaso, pero tardan 4,5-4,9 h.

**Torreta v4.1:** para bajar tiempo, la torreta perdió la base entera de 100 × 100 mm y ahora tiene 4 orejas (los mismos M3 en ±30, ±40), con pared de 2,5 mm. El vuelco lo resiste el anillo, y las tensiones de la pared quedan bajo 1 MPa.

Avisos de Bambu en R1 («floating cantilever» en P35) y R2 («unsupported overhangs» en P08): son los puentes del asiento del horn y de las ventanas de las cunas. Se imprimen bien sin soporte.

**Copia en Drive:** https://drive.google.com/drive/folders/1tgVAXhTr5cy_0PL6q8t-ZDHyu3ACUdJh (carpeta «RAPIDO_5h»). Las bandejas B10-B15 de calidad (16,6 h) siguen en `3MF_bandejas/` y en Drive, por si después hay tiempo.

## Por qué cambió

Dos análisis estructurales independientes (Opus 5.5 y Fable 5.2, agente ORBI · Ingeniero Estructural) revisaron el brazo v3 y llegaron a lo mismo: **no se podía armar y no tenía carga admisible.** Lo confirmamos midiendo el script y las STL:

- **Giro:** el servo quedaba descentrado y 2 de sus 4 orejas caían fuera de la torreta.
- **Hombro:** las orejas del servo no tocaban ninguna pared, y el horn quedaba dentro de la pared de 4 mm, así que no alcanzaba al eslabón.
- **Codo:** el servo no tenía ventana para su cuerpo.
- **Ejes:** los tres servos cargaban el brazo en voladizo sobre su propio eje.

## Cómo está hecho el v4 (criterio estructural)

- **Cada servo va en una cuna** y se aperna por sus 4 orejas con M3 y tuerca. No hay autorroscantes en las orejas.
- **Hombro y codo tienen apoyo doble.** Cada eslabón son 2 placas que abrazan al servo: una va al horn y la otra gira sobre un buje (P33) y un M3 coaxial del lado opuesto. Así el eje del servo ya no carga el brazo en voladizo.
- **Las placas se imprimen planas**, con las capas a lo largo, que es donde trabaja la flexión. Los separadores quedan comprimidos por una varilla M3, sin tracción entre capas.
- **La torreta va centrada en el eje del giro** y lleva un anillo anti-vuelco a 1 mm de la plataforma. Si el brazo cabecea, se apoya en el anillo y no en el servo.
- **Pinza:**
  - engranajes de módulo 1,5, z = 16, con cara de 10 mm;
  - dedo conducido en corte doble (palma abajo, contraplaca arriba);
  - el dedo motriz apoya arriba en la contraplaca, así el MG90S no carga de lado;
  - cada dedo tiene un **cuello fusible de 6 × 7 mm a 26 mm del eje**: si alguien tira fuerte del peluche, se dobla ese cuello (PETG, cede sin romperse) y no el brazo.
- **El servo es el fusible.** Ninguna pieza impresa falla antes que el torque de bloqueo de su servo.
- **Carga recomendada en la pinza:**
  - 80 g a 5 V y 100 g a 6 V con MG995;
  - hasta 130 g con MG996R a 6 V.
  - El límite lo pone el torque del hombro, no las piezas. Con más peso el servo se trabaja, pero no se rompe nada.
- **Choques revisados** en 40 poses (hombro 15-165°, codo 50-180°, pinza abierta y cerrada): 0 choques entre piezas impresas. Las 14 STL tienen malla cerrada, con 0 bordes abiertos y 0 aristas no manifold.

## Bandejas (PETG, boquilla 0,4, capa 0,20 mm)

| Bandeja | Piezas | g | Perfil |
|---|---|---|---|
| **B10** Torreta | P07 | 90 | 4 paredes, 40 % giroide. **Soportes árbol solo dentro, bajo la placa del servo.** |
| **B11** Plataforma | P08 (plataforma y cuna del hombro) | 52 | 4 paredes, 40 % giroide, sin soportes |
| **B12** Placas | P09A, P09B, P10A, P10B | 68 | 4 paredes, 5/5 capas, 40 % giroide, brim de 4 mm |
| **B13** Cunas y pinza | P35 (cuna del codo), P30 (palma), P34 (contraplaca), P36 ×2, P37 | 97 | 4 paredes, 40 % giroide, sin soportes |
| **B14** Dedos y bujes | P31, P32, P33 | 26 | **100 % de relleno** |

Son unos 342 g de PETG, según el cálculo de Bambu Studio.

**Con 2 impresoras:**
- A2L n.º 1: B12 → B13.
- A2L n.º 2: B10 → B11 → B14.

**PETG:** boquilla a 240 °C, cama a 80 °C, ventilador al 40 %. En PEI texturada no se usa pegamento. Si no hay PETG, usa PLA+ con el mismo perfil, pero no dejes el robot al sol.

## Tornillería

| Dónde | Qué |
|---|---|
| Orejas de los 3 MG995 | 12 × M3×12 + 12 tuercas (las tuercas van en los bolsillos hexagonales) |
| Torreta a la cubierta | 4 × M3×12 + 4 tuercas, en x = ±30, y = ±40 desde el centro de la cubierta |
| Eje loco del hombro | 1 × M3×16 + arandela; enrosca en la tuerca del bolsillo de la cuna |
| Eje loco del codo | 1 × M3×25 + arandela; enrosca en la tuerca de la cuna del codo |
| Eslabón 1: 2 separadores + 4 varillas de la cuna del codo | 6 varillas roscadas M3 de 70 mm (o M3×70) + 12 tuercas |
| Eslabón 2: 1 separador + 2 varillas de la palma | 3 varillas M3 de 82 mm (o M3×80) + 6 tuercas |
| Contraplaca a la palma | 2 × M3×30 + 2 tuercas |
| Pivote del dedo conducido | 1 × M3×30 + 1 tuerca, pasando por el buje Ø6 |
| Horns | Los que traen los servos: **horn redondo** en los MG995 (4 tornillos a r = 7 mm) y horn de un brazo en el MG90S |

## Armado (en este orden)

1. **Calibrar:** pon cada servo en 90° con el tester antes de montar su horn. La pinza va en 60°, con los dedos tocándose.
2. **Torreta:**
   1. Mete las 4 tuercas por abajo.
   2. Baja el servo del giro por la ventana y apernalo por las orejas.
   3. Atornilla la torreta a la cubierta.
3. **Plataforma:**
   1. Atornilla el horn redondo del giro a la cara de abajo de P08: 4 tornillos en el rebaje Ø25.
   2. Calza la plataforma en el eje.
   3. Pon el tornillo central por el agujero Ø7. **Este paso va antes de meter el servo del hombro**, porque después el servo tapa el tornillo.
4. **Hombro:**
   1. Pon la tuerca en el bolsillo de la placa trasera.
   2. Mete el servo del hombro en la cuna desde el lado del horn y apernalo por las orejas.
   3. Atornilla el horn a P09A, por la cara interior y dentro del rebaje.
   4. Calza P09A en el eje del servo.
5. **Eslabón 1:**
   1. Mete el servo del codo en P35 y apernalo por las orejas.
   2. Arma P09A + P35 + 2 separadores P36 + P09B con las 6 varillas.
   3. Pasa el buje Ø8 de P33 por P09B, y después el M3×16 al eje loco del hombro.
6. **Eslabón 2:**
   1. Pon el horn del codo en P10A.
   2. Arma P10A + P37 + palma P30 + P10B con 3 varillas.
   3. Pasa el buje Ø8 por P10B y el M3×25 al eje loco del codo.
7. **Pinza:**
   1. Atornilla el MG90S por abajo de la palma, con los tornillos de sus orejas.
   2. Pon el horn en el rebaje de P31, con el tornillo central por el agujero de arriba.
   3. Monta P32 con el buje Ø6 y el M3×30.
   4. Cierra con la contraplaca P34.
   5. Forra las mordazas con elástico o silicona caliente.

## Antes de imprimir todo (10 min)

**Mide un MG995 con pie de metro.** Comprueba:
- la distancia entre los agujeros de las orejas: 49 × 10 mm;
- el alto de la oreja desde la base: 26,3 mm;
- el diámetro del horn redondo: hasta 25 mm.

Si alguna medida no coincide, se cambia en `diseno/blender/generar_brazo_v4.py` y se regenera en 40 s.

## Firmware

En el robot real, cierra la pinza **hasta el contacto + 10°**, no hasta los 60° fijos: si el MG90S se queda empujando, se calienta. Usa rampa de aceleración en el giro y en el hombro.

Regenerar: `Blender -b -P diseno/blender/generar_brazo_v4.py -- <salida>` y `python3 -I diseno/blender/empaquetar_brazo_v4.py <salida> diseno/imprimir/brazo_v4`.

## Soportes del LiDAR y de la cámara frontal (bandeja B15)

| Pieza | Qué lleva | Dónde va en la cubierta |
|---|---|---|
| **P40 · Soporte del LiDAR** | Dos ranuras. Adelante va el módulo S850, de pie, con el sensor al frente y el conector de 4 hilos arriba. Atrás, a 14 mm, va la placa Radar_Con con el USB-C arriba. | Proa izquierda: centro en x = 145, y = −45, mirando a +X. Los 4 M3 caen en la rejilla. |
| **P41 · Soporte de la cámara frontal** | La Pi Camera v1.3 entra desde arriba con la lente al frente, inclinada 12° hacia arriba para ver personas y manos a 1-2 m. La cinta baja por la ventana de la base. | Proa al centro: x = 146, y = 0, justo sobre el pasacables delantero (x = 130). La cinta baja doblada en diagonal hasta la Pi. |

- **Material:** PETG o PLA, 4 paredes, 40 % giroide, sin soportes, con la base en la cama.
- **Fijación:** se pegan a la cubierta (cianoacrilato o silicona caliente) o se apernan con M3×12 en la rejilla. Los muros quedan perpendiculares a la base y llevan cartelas.
- **Antes de imprimir, mide el S850 y la Radar_Con con pie de metro.** Sus medidas salieron de la foto (sensor de unos 20 × 25 mm, adaptadora de unos 25 × 31 mm, ±1 mm). Si no coinciden, cambia `W_LIDAR`, `H_LIDAR`, `W_ADAPT` o `H_ADAPT` al inicio de `diseno/blender/generar_soportes_sensores.py` y regenera.
- **Cámara:** sus medidas son las del plano oficial de la v1.3 (25 × 24 mm). Si se quiere otra inclinación, se cambia `TILT_CAM`.
- **Si usan los ESP32-CAM de V1 o V2 en (130, ±50),** muévanlos a x = 100: el soporte del LiDAR ocupa esa esquina.

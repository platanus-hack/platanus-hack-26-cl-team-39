# Paneles laterales de Bicho (modelo de 2 placas)

Cierran los 4 costados del piso que queda entre la placa de abajo y la de arriba. Son 6 piezas en una sola impresión.

![Bicho con los paneles](render_frente.png)

| Impresora | Archivo (copiar a la microSD) | Tiempo | PLA |
|---|---|---|---|
| **Bambu A1** | [`SD/A1_PANELES.gcode.3mf`](SD/A1_PANELES.gcode.3mf) | **46 min** | 16 g |
| Bambu A2L | [`SD/A2L_PANELES.gcode.3mf`](SD/A2L_PANELES.gcode.3mf) | 46 min | 16 g |

**Son una hoja:** 3 capas en total, 0,6 mm. La lámina es de 2 capas (0,4 mm) y el texto y el ojo van en una tercera capa de 0,2 mm. Tiene que ser liviana; no sostiene nada.

Se imprime **uno de los dos**, no ambos. Ya van laminados y marcados para su impresora: placa Textured PEI, boquilla de 0,4 y capa de 0,2 mm. Van sin brim, porque una hoja tan delgada se rompería al sacarlo. Para sacar las piezas, espera a que la cama se enfríe y dobla la lámina de la cama: salen solas.

## Piezas
- **P60 a P63:** costados de 146 mm, dos por lado. Llevan relieve: «bicho» en un costado y el ojo con la curita en el otro.
- **P64:** panel frontal de 174 mm.
- **P65:** panel trasero de 174 mm.

Los dos de 174 mm tienen una ventana abajo para que pasen los cables.

## Cómo se ponen (sin tornillos)
- Cada panel tiene **pestañas planas de 3 mm**, del mismo espesor de la hoja, abajo y arriba. Entran en los agujeros de la rejilla como lengüetas de papel.
  - Los costados van en la fila **y = ±90**, a 10 mm del borde.
  - El frontal y el trasero van en la fila **x = ±150**.
- Primero se calzan las pestañas de abajo en la placa de abajo. Después se curva la hoja para meter las de arriba. Si alguna se dobla, basta un punto de silicona caliente.
- Los costados tienen una **muesca en x = ±40** para el nervio transversal de la placa de arriba. Quedan 12 mm hacia adentro del borde, así que no tocan las ruedas.

Se regeneran con `Blender -b -P diseno/blender/generar_paneles_laterales.py -- <salida>`.

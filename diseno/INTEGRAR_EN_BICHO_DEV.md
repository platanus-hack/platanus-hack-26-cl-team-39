# Llevar el taller 3D a bicho·dev

Guía para quien siga con el front de bicho·dev (`web/`), sobre todo Guty.

La idea es que el **Simulador** de bicho·dev use el robot real que se va a imprimir, y no solo el modelo hecho a mano en `web/src/sim/escena.ts`. Además, que se pueda manipular cada pieza como en el taller ([`taller3d/index.html`](taller3d/index.html)).

## Qué trae el GLB

`diseno/modelos/bicho_V1.glb`, `bicho_V2.glb` y `bicho_V3.glb` salen de Blender con nombres y datos que el código puede leer. Los datos van en `userData`, que el GLTFLoader llena con los *extras* del glTF.

| Nombre del nodo | Qué es | `userData` |
|---|---|---|
| `R_V1`, `R_V2`, `R_V3` | Raíz del robot | `version`, `titulo` |
| `G_<id>` (por ejemplo `G_pi`, `G_ups`, `G_bat1`, `G_brazo`, `G_esp1`) | Grupo que se puede mover: una pieza con todo lo que lleva encima | `movible: true`, `superficie: 'cubierta' \| 'piso1' \| 'piso2' \| 'bajo' \| 'frente'`, `etiqueta`, `item` (id del inventario en Neon) |
| `J_giro`, `J_hombro`, `J_codo`, `J_muneca`, `J_pinza`, `J_barrido` | Articulaciones del brazo y del barredor | — |
| `W_*` | Ruedas, para hacerlas girar | `rueda: true` |
| `CELL_*` | Celdas 18650 | `celda: 1..8` |
| `S_cam_pi`, `S_cam_esp1`… | Cámaras | `sensor: 'camara'`, `fov_h`, `fov_v` |
| `S_lidar`, `S_lidar_rayo` | El LiDAR y el empty que marca la dirección del rayo (su eje local **+Y**) | `sensor: 'lidar'`, `rayo: true` |
| Mallas o grupos con masa | Cualquier pieza | `masa_g`, `tipo: 'impreso' \| 'componente' \| 'chasis'`, `etiqueta`, `pieza` (P01…P24) |

Si una malla tiene varios materiales, el GLTFLoader la convierte en un `Group` con hijos. Los `userData` quedan en ese grupo.

### Ejes

- **Unidades:** metros.
- **Altura:** +Y es hacia arriba.
- **Dirección:** el robot mira hacia **+X**. En `escena.ts` el bicho mira hacia +z, así que para usar el GLB hay que rotar la raíz `R_*` con `rotation.y = -Math.PI / 2`.
- **Articulaciones de cabeceo** (`J_hombro`, `J_codo`, `J_muneca`, `J_pinza`): giran en su **Z local**. Las de giro (`J_giro`, `J_barrido`) giran en su **Y local**.

```ts
j.quaternion.setFromAxisAngle(new THREE.Vector3(0, 0, 1), THREE.MathUtils.degToRad(grados))
```

- **Pose por defecto:** hombro 55°, codo −85°, muñeca 20°. Es la pose «Mirar al frente».

## Plan sugerido (de menos a más)

1. **Cargar el robot real en el Simulador.**
   - Copiar `diseno/modelos/*.glb` a `web/public/modelos/`.
   - En `escena.ts`, crear un `cargarBichoReal(version)` con `GLTFLoader` de `three/examples/jsm/loaders/GLTFLoader.js` (three 0.170, el mismo que ya usa la web).
   - Mantener el modelo hecho a mano como respaldo mientras carga.
2. **Mover el brazo con el idioma del bicho.**
   - Los gestos de `bicho/lenguaje.json` («mira alrededor», «saluda», etc.) se traducen a ángulos de `J_giro`, `J_hombro`, `J_codo` y `J_muneca`.
   - Las poses del taller sirven de punto de partida: frente, suelo, arriba, plegado, escanear y saludar. Están en `POSES` dentro de `taller3d/index.html`.
3. **Modo taller dentro del Simulador**, una pestaña «Armar» al lado de las visitas:
   - `TransformControls` (de `three/examples/jsm/controls/TransformControls.js`) sobre los `G_*` con `movible`. Con `showY = false` y `setTranslationSnap(0.010)`, el arrastre avanza de 10 mm en 10 mm, igual que la rejilla de las placas.
   - Recalcular la masa, el centro de gravedad y el ángulo de vuelco con `userData.masa_g` (función `stats()` del taller).
   - Choques con `OBB` (de `three/examples/jsm/math/OBB.js`) entre las mallas del brazo y el resto (función `collisions()`).
   - Torque en vivo por servo (función `torques()`), con el límite de ⅔ del torque de bloqueo: MG995 0,98 N·m y MG90S 0,216 N·m a 6 V.
4. **Que el diseño quede guardado.** Guardar las posiciones movidas (`G_*`: `x`, `z` y rotación) en Neon, igual que el inventario, para que lo que alguien acomoda lo vea el resto. Exportarlas a JSON permite volver a Blender y regenerar las STL con las piezas en su nuevo lugar.
5. **Conectar el inventario.** Cada `G_*` trae `item`, el id del inventario. Al pasar el mouse sobre una pieza se puede mostrar su ficha de Neon, y marcar en rojo si el inventario dice que esa pieza no está disponible.

Las funciones del taller (`stats`, `torques`, `collisions`, `lidarTick`, `driveTick`, `applyExplode` y `buildFov`) son JavaScript plano sobre three.js. Se pueden pasar casi tal cual a un `taller.ts` dentro de `web/src/sim/`.

## Ojo

- Cada GLB pesa unos 4,4 MB, por la rejilla de agujeros de las placas. Si molesta en la web, se puede bajar el detalle en `generar_bicho_v3.py`: `seg=12` en `holes()` de la placa, o una versión «web» sin agujeros.
- El repo es público: los GLB y las STL no tienen nada privado.

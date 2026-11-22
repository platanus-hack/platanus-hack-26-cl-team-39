# Por desarrollar

Lo que dejamos diseñado o empezado durante las 36 horas, pero que **no es parte de lo que Bicho hace hoy**. Cada feature dice en qué estado quedó, dónde está y qué falta para terminarla.

| Feature | Estado | Dónde está |
|---|---|---|
| [Brazo de 4 servos](#brazo-de-4-servos) | Diseño final, archivos para imprimir y vista en bicho·dev. Sin montar. | `diseno/imprimir/brazo_v4/`, `web/src/brazo/`, `web/public/bim/` |
| [LiDAR 2D](#lidar-2d) | Soporte impreso. Sin módulo en el Pi. | `diseno/imprimir/soportes/` |
| [Señas con la mano](#señas-con-la-mano) | Servicio probado contra el relé con un bicho de prueba. Falta la prueba con el robot real. | `handtracking/tracker/senas.py` |
| [Manejar con las manos (Unity)](#manejar-con-las-manos-unity) | App que compila y entra por el relé. Sin probar con motores. | `handtracking/unity/BichoHands/` |
| [Gemelo digital](#gemelo-digital) | Pestaña en bicho·dev con sensores en vivo. Sin desplegar. | `web/src/gemelo/`, `web/public/manos/` |
| [Simulador con el cuerpo real](#simulador-con-el-cuerpo-real) | Plan escrito. | `diseno/INTEGRAR_EN_BICHO_DEV.md` |
| [Botón «Preguntar» del inventario](#botón-preguntar-del-inventario) | Código listo. Falta la API key en el deploy. | `web/api/preguntar.ts` |

## Brazo de 4 servos

**Por qué quedó fuera:** decidimos que Bicho anduviera sin brazo para llegar con el robot entero a la demo. La decisión del 21 de noviembre está en [`contexto/decisiones.md`](../contexto/decisiones.md).

**Qué hay:**
- **Diseño:** el brazo v4 tiene giro, hombro y codo con MG995, y una pinza con MG90S. Es un rediseño estructural con cunas de 4 orejas apernadas y apoyo doble, revisado con dos modelos.
- **Para imprimir:** STL, G-code para Bambu A1 y A2L y para Creality CR-3040 Pro, y el reparto en tres impresoras para terminar en unas 3 h 45 min. Está en [`diseno/imprimir/brazo_v4/`](../diseno/imprimir/brazo_v4/).
- **Modelo BIM:** [`web/public/bim/registro.json`](../web/public/bim/registro.json) registra las piezas, las revisiones, los planos y la calibración de cada servo.
- **En bicho·dev:** la vista **Brazo** tiene el árbol de piezas, el visor 3D y sliders que mandan `{"cmd":"servo"}`. El firmware ya tiene ese comando: `bicho/servos.py` usa un segundo PCA9685 en 0x41, a 50 Hz.

**Qué alcanzó a imprimirse:** las placas P09B, P10A y P10B y los separadores, en la CR-3040 (aviso en el Discord del equipo, sábado 21 a las 22:43). El resto del brazo se canceló.

**Qué falta:**
1. Imprimir las piezas que faltan y montar el brazo en la torreta.
2. Calibrar el cero de cada servo con el tester. La calibración se corrige en el registro, no en el firmware.
3. Probar el torque real del hombro con la pinza cargada. El cálculo estático está en la vista Brazo.

## LiDAR 2D

**Qué hay:** el YDLIDAR/EAI S850 tiene su soporte impreso que encaja desde arriba (bandeja B15).

**Qué falta:**
1. Un módulo `bicho/lidar.py` que lea el sensor por USB y publique la distancia por ángulo en los sensores.
2. Mostrar el barrido en bicho·dev. El Taller 3D ya simula el rayo y el mapa.

## Señas con la mano

**La idea:** le muestras la mano a la cámara del bicho y le dices «esta seña significa para». La aprende en ese momento y, cuando la vuelve a ver, se detiene.

**Qué hay:**
- [`handtracking/tracker/senas.py`](../handtracking/tracker/senas.py) toma las imágenes de la cámara y lo que oye el bicho desde el relé, detecta la mano con MediaPipe y guarda la «huella» de la seña. También anuncia lo aprendido en bicho·dev.
- Lo probamos con el relé corriendo en local y un bicho de prueba que mandaba imágenes de los videos del proceso. Aprendió «para» con la palma, no la confundió con el puño y mandó `stop`.

**Qué falta:**
1. Correrlo con la clave del equipo frente al robot real.
2. Que el Cerebro ignore las frases que dicen «seña», para que no intente aprenderlas por su lado.
3. Con motores en el robot real, comprobar que `stop` frena.

## Manejar con las manos (Unity)

**Qué hay:** la app Unity en [`handtracking/unity/BichoHands/`](../handtracking/unity/BichoHands/) hace todo esto:
- reconoce gestos (palma, puño, índice, V, pulgar, pinza);
- usa la palma como joystick;
- se detiene sola si deja de ver la mano y tiene parada de emergencia;
- maneja un gemelo virtual del robot y entra por el relé con la clave.

Los gestos ya prenden las luces del bicho. Tiene 10 tests.

**Qué falta:** probar `drive` contra los motores reales. Viene apagado por defecto.

## Gemelo digital

**Qué hay:** las pestañas **Gemelo 3D** y **Manos** de bicho·dev:
- el chasis con el brazo v4 montado, pieza por pieza;
- sobre el modelo, las luces, la temperatura de la Pi, el ángulo de la voz y la imagen de la cámara en vivo;
- la demo de las señas.

**Qué falta:** el deploy de bicho·dev y mover el gemelo con la odometría de los sensores de flujo óptico.

## Simulador con el cuerpo real

**Qué falta:** cargar el GLB del robot en el Simulador de bicho·dev y agregar el modo «Armar». El plan está en [`diseno/INTEGRAR_EN_BICHO_DEV.md`](../diseno/INTEGRAR_EN_BICHO_DEV.md).

## Botón «Preguntar» del inventario

**Qué falta:** una API key de Anthropic en el entorno del deploy. El código ya está en [`web/api/preguntar.ts`](../web/api/preguntar.ts).

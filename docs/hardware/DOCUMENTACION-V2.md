> **Documentación inicial, no final.** Explica la propuesta v2 del esquemático (archivo en esta carpeta: [`esquematico-conexiones-v2.pdf`](esquematico-conexiones-v2.pdf)). El script `hardware/esquematico.py` que menciona no está en este repo. El robot que se armó no usa el NodeMCU vigilante ni el Arduino Uno: ver [`README.md`](README.md).

# Hardware del bicho: documentación del esquemático v2

Este documento explica el esquemático `esquematico-conexiones.pdf` (5 hojas), que se regenera con
`python hardware/esquematico.py`. Es una **propuesta sin probar en hardware**: lo marcado como
*por confirmar* hay que medirlo o leerlo en la placa antes de cablear.

## 1. La idea en una página

```
                  Servidor IA
                       │ WiFi (HTTPS, API key)
              ┌────────┴─────────┐
              │  Raspberry Pi 3B │  supervisor (fijo) + comportamiento (lo cambia la IA)
              └┬──────┬────────┬─┘
     I2C 3,3 V │      │ USB    │ latido (1 GPIO)
   ┌───────────┴──┐ ┌─┴──────┐ ┌┴──────────────────┐
   │ PCA9685 ×2   │ │Arduino │ │ NodeMCU vigilante │ firmware fijo
   │ ADS1115 ×4   │ │  Uno   │ └┬──────────────────┘
   │ MPU-6050     │ │ (5 V)  │  │ OE y STBY: corta motores y servos
   └──┬───────────┘ └─┬──────┘  │
      │ PWM           │ mux #2 y #3
   TB6612 ×4 ◄────────┼─────────┘
      │            HC-SR04 ×8, WS2812, sensores de 5 V
   4 motores TT
```

Tres dominios, cada uno con un dueño:

| Dominio | Dueño | Qué cuelga | Voltaje |
|---|---|---|---|
| Control principal | Raspberry Pi 3B | motores, servos, analógico lento, IMU, ToF | 3,3 V |
| Tiempo real y 5 V | Arduino Uno | ultrasonidos, LEDs WS2812, analógico de 5 V, encoders | 5 V |
| Seguridad | NodeMCU ESP8266 | corte de motores y servos | 3,3 V |

Los dominios solo se tocan por USB (Pi↔Uno) y por dos líneas de 3,3 V (Pi↔NodeMCU), por eso no hace
falta conversor de nivel.

## 2. Cómo leer el esquemático

- **Hoja 1**: control principal. **Hoja 2**: Arduino Uno. **Hoja 3**: alimentación.
  **Hoja 4**: tabla cable por cable. **Hoja 5**: recursos libres, actualización, API key, pendientes.
- **Etiquetas con borde** (`+3V3`, `+5V`, `GND`, `+VBAT`, `+VSERVO`, `OE`, `STBY`, `S0–S3`): todos los
  puntos con el mismo nombre van unidos, aunque no haya línea dibujada.
- **Verde** = recurso libre para sensores o actuadores nuevos.
- Una **línea gruesa** es un grupo de cables (4 u 8 hilos), no uno solo.
- Dos líneas que se cruzan **sin punto** no están conectadas.

## 3. Bus I2C del control principal

### Qué es

Dos cables compartidos por todos los módulos: **SDA** (datos, GPIO2, pin físico 3) y **SCL** (reloj,
GPIO3, pin físico 5). La Pi es el único maestro: ella inicia cada conversación nombrando al módulo por
su **dirección**. Los pines no tienen memoria; lo que existe es un espacio de direcciones.

### ¿Alcanzan las direcciones?

Sí, con mucho margen. Una dirección I2C tiene 7 bits: 128 valores, de los que 112 son utilizables
(0x08 a 0x77). El diseño ocupa 8 hoy y 14 con los seis sensores ToF.

| Dirección | Módulo | Cómo se fija |
|---|---|---|
| 0x40 | PCA9685 #1 (motores) | sin puentes |
| 0x41 | PCA9685 #2 (servos) | puente A0 soldado |
| 0x70 | «all call» de los PCA9685 | reservada: responde cualquier PCA9685 |
| 0x48 | ADS1115 #1 | ADDR a GND |
| 0x49 | ADS1115 #2 | ADDR a VDD |
| 0x4A | ADS1115 #3 | ADDR a SDA |
| 0x4B | ADS1115 #4 | ADDR a SCL |
| 0x68 | MPU-6050 | AD0 a GND (0x69 con AD0 a +3V3) |
| 0x29 → 0x30–0x35 | VL53L3CX ×6 (futuro) | se reasignan por software en cada arranque |

### Lo que sí limita al bus

Las direcciones no son el problema. Los límites reales son estos cuatro:

1. **Módulos iguales con la misma dirección.** Un MPU-6050 solo admite 0x68 o 0x69: caben dos, no
   los cinco del inventario. Los seis VL53L3CX nacen todos en 0x29 y se resuelven con XSHUT
   (sección 6). Para más IMU iguales hace falta un multiplexor I2C TCA9548A, que no está en el
   inventario, o un segundo bus.
2. **Resistencias pull-up acumuladas.** La Pi trae 1,8 kΩ fijas en SDA y SCL, y cada módulo suma
   las suyas en paralelo. La norma I2C pide que un módulo no tenga que absorber más de 3 mA, lo que
   equivale a unos 970 Ω en total a 3,3 V. Con módulos de 10 kΩ ese valor se cruza al quinto
   módulo, y el diseño base ya tiene siete. **Hay que quitar las pull-up de los módulos** (suelen
   ser dos resistencias junto a SDA/SCL, o un puente que se corta) y dejar solo las de la Pi.
   *Por confirmar:* el valor que trae cada placa.
3. **Velocidad.** La Pi arranca a 100 kHz, unos 11.000 bytes por segundo. El tráfico estimado
   (motores a 50 Hz, IMU a 100 Hz, cuatro ADS1115 leyendo seguido) ronda esa misma cifra, así que
   a 100 kHz el bus queda saturado. A 400 kHz usa cerca de un cuarto. Configurar en
   `/boot/firmware/config.txt`: `dtparam=i2c_arm=on,i2c_arm_baudrate=400000`. Son estimaciones, no
   mediciones.
4. **Es un punto único de falla.** Si un módulo se cuelga con SDA en bajo, o el ruido de los
   motores corrompe el bus, la Pi no puede mandar ninguna orden, tampoco la de frenar. Por eso el
   corte de motores **no pasa por I2C**: lo hace el vigilante con las líneas OE y STBY.

### Reglas de cableado

- Cables de SDA y SCL cortos (menos de 30 cm en total si se puede) y lejos de los cables de motor.
- GND de cada módulo al punto común, no en cadena a través de otros módulos.
- No colgar microcontroladores como esclavos de este bus: el controlador I2C de la Pi falla con
  esclavos que estiran el reloj. El Uno va por USB.

### Si el bus se queda corto

Sin comprar nada se puede abrir un **segundo bus por software** en la Pi con dos GPIO libres:
`dtoverlay=i2c-gpio,bus=3,i2c_gpio_sda=22,i2c_gpio_scl=26` (necesita sus propias pull-up de 2,2 a
4,7 kΩ a +3V3). Lo recomendable al crecer es dejar los PCA9685 solos en el bus principal y pasar los
sensores al bus 3: así un sensor colgado no deja al robot sin control de motores. El Uno ofrece
además un tercer bus a 5 V en A4/A5.

## 4. Actuadores

### Motores: PCA9685 #1 → TB6612FNG ×4

- El PCA9685 genera 16 señales PWM de 12 bits (0 a 4095), todas a la misma frecuencia. Aquí va a
  **1 kHz** (registro de prescala = 5).
- Cada motor usa tres canales: uno de **velocidad** (PWM) y dos de **sentido** (IN1, IN2, puestos en
  todo o nada).
- Cada TB6612FNG trae dos puentes H. Se usa **una placa por motor con los dos puentes en paralelo**
  (PWMA con PWMB, AIN1 con BIN1, AIN2 con BIN2, AO1 con BO1, AO2 con BO2), porque un motor TT
  trabado pide 1,5 A y un puente solo aguanta cerca de 1 A continuo.

| IN1 | IN2 | PWM | Resultado |
|---|---|---|---|
| 1 | 0 | 0–100 % | adelante, velocidad según PWM |
| 0 | 1 | 0–100 % | atrás |
| 1 | 1 | — | freno |
| 0 | 0 | — | rueda libre |

- Los motores se alimentan directo del pack (6,0 a 8,4 V). El supervisor limita el PWM al **70 %**
  para no pasar de unos 6 V medios en un motor de 3 a 6 V.
- `STBY` en bajo apaga los cuatro puentes. `OE` en alto deja todas las salidas del PCA9685 en 0.

### Servos: PCA9685 #2

- Va a **50 Hz** (prescala = 121). Un servo espera un pulso de 1 a 2 ms cada 20 ms: en cuentas de
  12 bits, de 205 a 410 aproximadamente. Cada servo se calibra por separado.
- La potencia de los servos entra por el borne `V+` (5,0 V del LM2596), no por la lógica.
- Los canales sin servo sirven como salidas todo o nada de 3,3 V (máximo 10 mA: para un relé, láser
  o LED de 1 W hace falta un transistor, o un TB6612 de los 13 que sobran).

## 5. Seguridad: el vigilante

El NodeMCU corre un firmware fijo que nadie más toca. Hace una sola cosa:

1. Lee el **latido**: una onda cuadrada que el supervisor de la Pi genera en GPIO17.
2. Si pasan 300 ms sin un cambio en esa línea, pone `OE` en alto y `STBY` en bajo.
3. También corta si se aprieta el pulsador de paro.
4. Informa su estado a la Pi por GPIO27.

Resistencias de reposo: `OE` con 1 kΩ a +3V3 y `STBY` con 10 kΩ a GND. Si el NodeMCU no está o se
está reiniciando, el robot queda apagado. *Por confirmar:* si las placas PCA9685 traen una
resistencia propia en OE hacia GND; el valor de 1 kΩ asume que sí.

Por qué existe: el PCA9685 **recuerda la última orden** aunque la Pi se cuelgue. Sin vigilante, un
fallo del código de la IA dejaría los motores girando.

## 6. Sensores: cómo funciona y cómo se lee cada uno

| Sensor (cant.) | Interfaz | Va conectado a | Modo de lectura |
|---|---|---|---|
| Cámara Pi v1.3 (1–2) | CSI | conector de cámara de la Pi | video o fotos con `libcamera`/`picamera2` |
| ESP32-CAM (3) | WiFi | solo alimentación | la Pi pide imágenes JPEG por HTTP |
| YDLIDAR 2D (1) | USB serie | USB de la Pi | flujo continuo de ángulo y distancia; SDK del fabricante |
| MPU-6050 (5) | I2C 0x68/0x69 | bus de la Pi | lectura por registros |
| L3GD20H + LSM303 (4) | I2C | bus de la Pi | lectura por registros |
| MMA845x (3) | I2C 0x1C/0x1D | bus de la Pi | lectura por registros |
| VL53L3CX (6) | I2C 0x29 | bus de la Pi + XSHUT | medición de distancia por tiempo de vuelo |
| HC-SR04 (8) | pulso digital, 5 V | Uno, por mux #2 y #3 | pulso de disparo y ancho del eco |
| Barras IR de 8 canales (3) | analógica o por tiempo | mux #1 o mux #2 | un valor de reflectancia por canal |
| QTR-1A (2) e IR sueltos (18) | analógica | mux #1 o mux #2 | voltaje proporcional a la reflectancia |
| ADNS-3080 flujo óptico (4) | SPI | SPI0 de la Pi | desplazamiento X/Y acumulado |
| Presión diferencial Honeywell (1) | analógica | Uno (A1–A3) | voltaje proporcional a la presión |
| Joystick (1) | 2 analógicas + 1 digital | mux #1 | posición X, Y y botón |
| Sensor de sonido (1) | digital (umbral) | mux #2 o GPIO | 1 si el ruido supera el umbral del potenciómetro |
| Botón táctil (1) | digital | GPIO de la Pi o mux #2 | 1 mientras se toca |
| Receptor IR + control (1) | digital modulada | Uno D2 o D3 | códigos del control remoto |
| Batería | analógica | ADS1115 #1, canal A1 | voltaje del pack por divisor |

### Detalle por tipo

**Analógicos lentos (ADS1115).** Cada ADS1115 tiene 4 entradas de 16 bits (15 útiles midiendo contra
GND). Modo recomendado: **disparo único** con ganancia ±4,096 V (125 µV por paso): se escribe el
registro de configuración eligiendo el canal, se espera la conversión y se lee el resultado. La
velocidad se elige entre 8 y 860 muestras por segundo por chip, repartidas entre sus canales. La
entrada nunca puede pasar de 3,6 V.

**Multiplexor #1 (16 analógicos por un canal).** Para leer el canal *n*: la Pi pone el número *n* en
binario en S0–S3 (GPIO5, 6, 13, 19), espera alrededor de 1 ms a que la señal se asiente y lee el
canal A0 del ADS1115 #1. Barrer los 16 canales da unas 50 lecturas por segundo de cada uno como
máximo. No sirve para audio ni para señales rápidas.

**MPU-6050.** Acelerómetro y giroscopio de 3 ejes. Arranca dormido: hay que escribir 0 en el
registro `PWR_MGMT_1` (0x6B). Luego se leen 14 bytes desde 0x3B (aceleración, temperatura, giro).
Rangos por defecto ±2 g y ±250 °/s. Alimentarlo a 3,3 V en este bus.

**L3GD20H + LSM303, MMA845x, «mpu6295».** Mismo patrón: despertar, configurar rango y leer registros.
*Por confirmar:* el modelo exacto y las direcciones con un escaneo (`i2cdetect -y 1`); varían según
la versión de la placa, y «mpu6295» no corresponde a un modelo conocido.

**VL53L3CX.** Mide distancia por tiempo de vuelo de un láser infrarrojo, hasta unos 3 m. Todos nacen
en 0x29, así que al arrancar: (1) la Pi mantiene los seis apagados con XSHUT en bajo; (2) suelta uno
(GPIO como entrada); (3) le asigna una dirección nueva; (4) repite con el siguiente. La dirección se
pierde al apagar. XSHUT no tolera 5 V: solo bajo o entrada. Usa el controlador de ST, que es pesado;
por eso va en la Pi y no en el Uno.

**HC-SR04.** Ultrasonido de 2 a 400 cm con un cono de unos 15°. Ciclo: el Uno pone el número del
sensor en S0–S3, manda un pulso de 10 µs por D13 (TRIG), y mide por A0 cuánto dura en alto el ECHO.
Distancia en cm ≈ microsegundos / 58. Hay que esperar unos 60 ms entre disparos, así que los 8 se
recorren unas 2 veces por segundo. Cada TRIG lleva 10 kΩ a GND para no dispararse solo cuando el
multiplexor no lo tiene elegido.

**Sensores de reflectancia (QTR e IR).** Un LED infrarrojo y un fototransistor: el voltaje baja
cuanto más refleja la superficie. Los analógicos van directo a un canal de multiplexor. *Por
confirmar:* si las barras de 8 canales son la versión analógica o la de tiempo de descarga («RC»);
la segunda se lee midiendo un tiempo y debe ir en el Uno.

**ADNS-3080.** Sensor de ratón óptico: entrega cuánto se movió la imagen en X e Y desde la última
lectura. Se lee por SPI (registro de movimiento y luego los deltas). *Por confirmar:* el voltaje de
la placa antes de conectarlo al SPI de 3,3 V de la Pi.

**Presión diferencial Honeywell 163PC01D36.** Salida analógica. *Por confirmar:* voltaje de
alimentación y rango de salida en su hoja de datos; si pasa de 3,3 V debe ir al Uno o con divisor.

**Receptor IR.** Entrega la señal del control ya demodulada. Decodificarla requiere medir tiempos
con precisión: va en un pin con interrupción del Uno (D2 o D3).

## 7. Dominio de 5 V: Arduino Uno

- La Pi lo alimenta, le habla y lo regraba por el mismo cable USB.
- Protocolo: el mismo JSON por línea a 115200 baudios de `PROTOCOLO.md`.
- Los multiplexores #2 (entradas) y #3 (salidas de pulso) comparten las líneas de selección: el
  número de canal elige a la vez el TRIG y el ECHO del mismo sensor.
- Un multiplexor **no retiene estado**: sirve para leer muchas entradas o mandar un pulso a una
  salida por vez. No sirve para PWM, servos ni relés.
- Límite del Uno: 32 KB de programa y 2 KB de RAM.

## 8. Alimentación

| Riel | Origen | Alimenta |
|---|---|---|
| `+VBAT` 6,0–8,4 V | pack de 2 celdas 18650 en serie, tras fusible de 5 A e interruptor | VM de los TB6612 |
| `+VSERVO` 5,0 V | LM2596 desde `+VBAT` | servos (borne V+ del PCA9685 #2) |
| `+5V` | UPS LX-2BUPS | Pi; de ahí el Uno (USB) y el NodeMCU (pin 2) |
| `+3V3` | pin 1 de la Pi | lógica de PCA9685, TB6612, ADS1115, mux #1, IMU |
| `GND` | — | todo, unido en un solo punto |

El pack no tiene protección propia: el supervisor mide la batería (ADS1115 #1, A1, divisor
100 kΩ / 33 kΩ) y detiene el robot bajo 6,6 V.

## 9. Orden de armado y prueba

1. Alimentación sola: ajustar el LM2596 a 5,0 V con multímetro, sin cargas.
2. Pi + bus I2C con un módulo a la vez; tras cada uno, `i2cdetect -y 1` debe mostrar su dirección.
3. Quitar las pull-up de los módulos antes de conectar el quinto.
4. Vigilante: comprobar con multímetro que sin latido `OE` está en alto y `STBY` en bajo.
5. Un motor con las ruedas en el aire; luego los cuatro.
6. Arduino Uno y un HC-SR04; luego el resto.

## 10. Sin verificar

- Cantidad real de PCA9685 (hacen falta dos) y resistencias que traen en OE, SDA y SCL.
- Serigrafía de los TB6612FNG y que sus canales se puedan puentear.
- Que el UPS sostenga la Pi, el Uno y los sensores (3 A es justo).
- Modelos exactos de las IMU y de las barras IR; voltajes del ADNS-3080 y del sensor de presión.
- Cable micro-USB de datos para grabar el NodeMCU (no figura en el inventario).
- Todas las cifras de velocidad y tráfico del bus son estimaciones.

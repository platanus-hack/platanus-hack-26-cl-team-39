# Bitácora del proceso · Platanus Hack 26 · Equipo 39

Horas en Chile (UTC-3). Fotos y videos (privados, del equipo) en Drive: https://drive.google.com/drive/folders/1-Ze_hGI7VpxI-U5A6CU_j8Gqs-QH9ReH. Sirven para el video del proceso, el deck y el README.

| Hora | Archivo | Qué se ve |
|---|---|---|
| Vie 20 · 23:59 | IMG_7990, IMG_7991 | Primeras fotos de la mesa con todo el inventario |
| Sáb 21 · 00:14 | WhatsApp Video 12.14.09 | Recorrido de 3:25 nombrando piezas (base del inventario de Carlos) |
| Sáb 21 · 00:35 | C1BBED67…JPG | Foto general del equipo trabajando con la mesa llena |
| Sáb 21 · 01:25–01:27 | IMG_7993 a IMG_7997 | Mesa, chasis de orugas, anillo LED y Raspberry Pi sobre la caja; prueba de cámara saludando |
| Sáb 21 · 01:59 | IMG_7998 | Raspberry Pi con red por cable sobre la caja |
| Sáb 21 · 02:13 | IMG_7999, IMG_8001, IMG_8002, IMG_8003 | Panel web «Sin bicho» (conectar por WiFi, simulador, Sensores, Consola, Versiones); Raspberry Pi OS 64-bit arrancando; dos chasis 4WD de ruedas amarillas armados |
| Sáb 21 · 02:26–02:27 | IMG_8004 a IMG_8007 | Escritorio de la Pi con usuario team39; terminal con `hostname` configurando la red; cambio a cable USB-C; conexión de cables de red |
| Sáb 21 · 02:33 | IMG_8008 | Micrófono-parlante omnidireccional sobre la caja de la Pi (la caja pasa a ser el cuerpo); se enciende pero aún no responde («prende y no hace nada»). Panel web abierto; chasis 4WD y anillo LED en espera |

Las copias «IMG_7996 2», «IMG_7997 2» e «IMG_7998 2» de Descargas son idénticas a las originales y no se duplicaron aquí.
| Sáb 21 · 03:11 | IMG_8011 | Chasis 4WD de doble piso armado: placas acrílicas, 4 motores TT y ruedas amarillas |
| Sáb 21 · 03:26 | IMG_8012 | **«¡El bicho está vivo!»**: el panel muestra el firmware v0.2.0 en la Pi 3B (temperatura de CPU en vivo, luz en GPIO17) |
| Sáb 21 · 03:43 | IMG_8013–14 | Soldando el cable del parlante, con tercera mano y termorretráctil |
| Sáb 21 · 04:13 | esquematico-conexiones.pdf | Esquemático de 4 hojas: Pi 3B + ESP32-CAM reflasheable, 2 PCA9685, 2 TB6612, 2 ADS1115, MPU-6050, dos fuentes |
| Sáb 21 · 04:22 | 21-11-2026.glb | Escaneo 3D por fotogrametría del chasis armado |
| Sáb 21 · 04:23 | IMG_8015–16 | Módulo dToF EAI «S850» con adaptador Radar_Con V1.4 USB‑C (probable SDM18) |
| Sáb 21 · 04:45 | robot/salida | Blender: 3 prototipos (A 4WD, B orugas, C torre), 13 STL y análisis de fuerzas. Taller 3D: diseno/taller3d/ |
| Sáb 21 · 05:40 | handtracking/ | Hand tracking: tracker MediaPipe (cámara → UDP) + app Unity 2022.3 «BichoHands» (palma = joystick, puño = stop, pinza = servos, gemelo virtual) + bicho simulado + firmware ESP32 con watchdog 500 ms. Probado con el video IMG_7996 del equipo; 10/10 tests |
| Sáb 21 · 05:30 | robot/salida_v2 | v2 según la reunión: 3 distribuciones (V1 brazo-cuello, V2 brazo + torre, V3 barredor), 8 celdas en el piso 1, LiDAR fijo en el brazo, 2 ADNS, Pi junto al brazo. Taller 3D interactivo en el mismo artifact |
| Sáb 21 · 05:55 | robot/imprimir_40cm | v3: estructura impresa de 40 cm (placa estándar 400×180 con rejilla M3 cada 10 mm, 3 pisos), 21 STL cerradas y 17 bandejas .3mf para cama de 220 |
| Sáb 21 · 06:10 | robot/imprimir_32cm | v3.1: estructura de 32 × 20 cm (más corta y ancha a pedido del equipo); 21 STL cerradas + 17 bandejas .3mf |
| Sáb 21 · 06:20 | robot/imprimir_32cm_entera | v3.2: placas de una sola pieza (sin junta), a pedido del equipo; 19 STL + 14 bandejas |

// bicho · comandos de manejo por manos (referencia para el ESP32-CAM)
// -------------------------------------------------------------------
// Recibe por UART (desde la Pi, que reenvía lo que llega por ws://<pi>:8080/ws) una línea JSON por comando:
//   {"cmd":"drive","l":0.42,"r":0.31}   velocidades -1..1 por lado (tracción diferencial)
//   {"cmd":"stop"}
//   {"cmd":"servo","i":0,"deg":90}      servo i (0..15) en PCA9685 #2
//   {"cmd":"gesto","g":"victoria","mano":"izq"}   evento libre: hagan lo que quieran
// WATCHDOG: si no llega drive/stop en 500 ms, los motores se apagan solos (la app manda 15 Hz mientras maneja).
//
// Pines según esquematico-conexiones.pdf (21-nov 04:13):
//   I2C: GPIO14 = SDA, GPIO15 = SCL · STBY de ambos TB6612 = GPIO13 (10k a GND)
//   PCA9685 #1 0x40 @1 kHz: M1 del.izq CH0-2 · M2 tras.izq CH3-5 · M3 del.der CH6-8 · M4 tras.der CH9-11 (PWM, IN1, IN2)
//   PCA9685 #2 0x41 @50 Hz: servos CH0..CH15
// OJO: en el esquemático GPIO14/15 del ESP32 son I2C, así que el UART con la Pi va por U0R/U0T (Serial).
//
// Librerías: Adafruit PWM Servo Driver, ArduinoJson (v7).
// Si los motores giran al revés, cambien el signo en INVERT[].

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <ArduinoJson.h>

static const int PIN_SDA = 14, PIN_SCL = 15, PIN_STBY = 13;
static const uint32_t WATCHDOG_MS = 500;
static const float MIN_DUTY = 0.25f;   // los TT no arrancan con menos; bajo |v|<0.05 se apaga

Adafruit_PWMServoDriver motores(0x40);
Adafruit_PWMServoDriver servos(0x41);

struct Motor { uint8_t pwm, in1, in2; };
static const Motor M[4] = { {0, 1, 2}, {3, 4, 5}, {6, 7, 8}, {9, 10, 11} };  // M1..M4
static const int8_t INVERT[4] = { 1, 1, 1, 1 };
static uint32_t lastDriveMs = 0;
static bool moving = false;
String linea;

void digital(uint8_t ch, bool on) { on ? motores.setPWM(ch, 4096, 0) : motores.setPWM(ch, 0, 4096); }

void motor(int i, float v) {
  v *= INVERT[i];
  if (fabsf(v) < 0.05f) { digital(M[i].in1, false); digital(M[i].in2, false); motores.setPWM(M[i].pwm, 0, 4096); return; }
  float duty = MIN_DUTY + (1.0f - MIN_DUTY) * fminf(1.0f, fabsf(v));
  digital(M[i].in1, v > 0);
  digital(M[i].in2, v < 0);
  motores.setPWM(M[i].pwm, 0, (uint16_t)(duty * 4095));
}

void drive(float l, float r) {
  motor(0, l); motor(1, l);   // izquierda: M1 + M2
  motor(2, r); motor(3, r);   // derecha:   M3 + M4
  moving = fabsf(l) > 0.05f || fabsf(r) > 0.05f;
  digitalWrite(PIN_STBY, moving ? HIGH : LOW);
}

void servo(int i, int deg) {
  deg = constrain(deg, 0, 180);
  // 50 Hz: 1 tick = 4,88 µs. 500..2500 µs → 102..512
  servos.setPWM(i, 0, map(deg, 0, 180, 102, 512));
}

void comando(const String& s) {
  JsonDocument doc;
  if (deserializeJson(doc, s)) return;               // no era JSON: ignorar
  const char* cmd = doc["cmd"] | "";
  if (!strcmp(cmd, "drive")) { drive(doc["l"] | 0.0f, doc["r"] | 0.0f); lastDriveMs = millis(); }
  else if (!strcmp(cmd, "stop")) { drive(0, 0); lastDriveMs = millis(); }
  else if (!strcmp(cmd, "servo")) servo(doc["i"] | 0, doc["deg"] | 90);
  else if (!strcmp(cmd, "gesto")) {
    const char* g = doc["g"] | "";
    // Ideas: "victoria" → baile de servos, "pulgar_arriba" → anillo LED verde, "puno" → ya frena por drive/stop.
    Serial.printf("{\"t\":\"log\",\"msg\":\"gesto %s\"}\n", g);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_STBY, OUTPUT); digitalWrite(PIN_STBY, LOW);
  Wire.begin(PIN_SDA, PIN_SCL);
  motores.begin(); motores.setPWMFreq(1000);
  servos.begin();  servos.setPWMFreq(50);
  drive(0, 0);
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { comando(linea); linea = ""; }
    else if (linea.length() < 256) linea += c;
  }
  if (moving && millis() - lastDriveMs > WATCHDOG_MS) drive(0, 0);  // hombre muerto
}

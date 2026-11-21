// bicho.ino: firmware base del bicho (ESP32 con Arduino core 3.x).
//
// Habla el protocolo de PROTOCOLO.md:
//   - Manda líneas JSON por Serial (115200) y por WebSocket (puerto 81).
//   - {"t":"info",...} al arrancar, cuando se conecta alguien y cada 10 s.
//   - {"t":"s","ms":...,"d":{...}} con los sensores a 20 Hz (configurable).
//   - Acepta OTA en POST http://<bicho>/update (lo usa la web bicho-dev).
//
// Requisitos:
//   - Placa ESP32 (clásico, S3 o C3) con un esquema de particiones con OTA (el "Default" sirve).
//   - Librería "WebSockets" de Markus Sattler (links2004), desde el Library Manager.
//   - Copiar secrets.example.h a secrets.h con la red WiFi. Si no conecta, levanta un AP propio.

#include <WiFi.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <Update.h>
#include <WebSocketsServer.h>

#if __has_include("secrets.h")
#include "secrets.h"
#endif
#ifndef WIFI_SSID
#define WIFI_SSID ""
#define WIFI_PASS ""
#endif

// ================== CAMBIAR EN CADA VERSIÓN ==================
// Sube FW_VERSION antes de compilar: la web compara contra esto.
// FW_DESC es el "qué hace" que se ve en la web (sin comillas dobles).
#define FW_NAME    "bicho"
#define FW_VERSION "0.1.0"
#define FW_DESC    "Firmware base: manda sensores por Serial y WiFi, y acepta actualizaciones OTA."
// =============================================================

#define AP_PASS "bicho1234"   // clave del AP de respaldo (mínimo 8 caracteres)

#if CONFIG_IDF_TARGET_ESP32
#define SENSOR_PIN 34          // ADC1 en ESP32 clásico
#else
#define SENSOR_PIN 1           // ADC1_CH0 en S2/S3/C3
#endif

WebServer http(80);
WebSocketsServer ws(81);

uint32_t periodMs = 50;        // 20 Hz
bool netUp = false;            // hay WiFi (STA o AP) y servidores corriendo
bool staUp = false;            // conectado a la red del venue
String serialBuf;

// ================== TUS SENSORES ACÁ ==================
// Agrega pares "nombre":valor separados por coma. La web grafica sola todo lo numérico.
// Se puede anidar: "imu":{"ax":1.2,"ay":0.1}  y usar arrays: "servo":[90,45,10]
void readSensors(String &d) {
  d += "\"pot\":";        d += analogRead(SENSOR_PIN);
  d += ",\"temp_chip\":"; d += String(temperatureRead(), 1);
  d += ",\"rssi\":";      d += staUp ? (int)WiFi.RSSI() : 0;
  d += ",\"heap\":";      d += ESP.getFreeHeap();
}

// ================== TUS COMANDOS ACÁ ==================
// Llega la línea completa, p. ej. {"cmd":"servo","i":0,"deg":90}. Devuelve true si la manejaste.
bool handleCustomCmd(const String &c) {
  (void)c;
  return false;
}
// =======================================================

String ipStr() {
  return WiFi.getMode() == WIFI_AP ? WiFi.softAPIP().toString() : WiFi.localIP().toString();
}

String infoJson() {
  String s;
  s.reserve(360);
  s += "{\"t\":\"info\",\"name\":\"" FW_NAME "\",\"fw\":\"" FW_VERSION "\",\"desc\":\"" FW_DESC "\"";
  s += ",\"chip\":\"";  s += ESP.getChipModel();  s += "\"";
  s += ",\"build\":\"" __DATE__ " " __TIME__ "\"";
  s += ",\"ip\":\"";    s += ipStr();             s += "\"";
  s += ",\"mac\":\"";   s += WiFi.macAddress();   s += "\"";
  s += ",\"uptime\":";  s += millis() / 1000;
  s += ",\"heap\":";    s += ESP.getFreeHeap();
  s += "}";
  return s;
}

void emit(const String &line) {
  Serial.println(line);
  if (netUp) ws.broadcastTXT(line.c_str(), line.length());
}

void emitLog(const String &msg) {
  String m = msg;
  m.replace("\"", "'");
  emit("{\"t\":\"log\",\"lvl\":\"info\",\"msg\":\"" + m + "\"}");
}

void handleCmd(String c) {
  c.trim();
  if (!c.length()) return;
  if (handleCustomCmd(c)) return;

  if (c.indexOf("\"info\"") >= 0) {
    emit(infoJson());
  } else if (c.indexOf("\"rate\"") >= 0) {
    int i = c.indexOf("\"hz\"");
    int hz = i >= 0 ? c.substring(c.indexOf(':', i) + 1).toInt() : 0;
    if (hz > 0 && hz <= 100) {
      periodMs = 1000 / hz;
      emitLog("tasa de sensores: " + String(hz) + " Hz");
    }
  } else if (c.indexOf("\"reboot\"") >= 0) {
    emitLog("reiniciando");
    delay(100);
    ESP.restart();
  } else {
    emitLog("comando desconocido: " + c);
  }
}

void readSerial() {
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\n') {
      handleCmd(serialBuf);
      serialBuf = "";
    } else if (serialBuf.length() < 512) {
      serialBuf += ch;
    }
  }
}

void onWs(uint8_t num, WStype_t type, uint8_t *payload, size_t len) {
  if (type == WStype_CONNECTED) {
    String i = infoJson();
    ws.sendTXT(num, i);
  } else if (type == WStype_TEXT) {
    String c;
    c.concat((const char *)payload, len);
    handleCmd(c);
  }
}

void cors() {
  http.sendHeader("Access-Control-Allow-Origin", "*");
  http.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  http.sendHeader("Access-Control-Allow-Headers", "*");
  http.sendHeader("Access-Control-Allow-Private-Network", "true");
}

void setupHttp() {
  http.on("/info", HTTP_GET, []() {
    cors();
    http.send(200, "application/json", infoJson());
  });
  http.on("/update", HTTP_OPTIONS, []() {
    cors();
    http.send(204);
  });
  http.on(
    "/update", HTTP_POST,
    []() {  // al terminar la subida
      cors();
      bool ok = !Update.hasError();
      http.send(ok ? 200 : 500, "text/plain", ok ? String("OK, reiniciando") : String("FALLO: ") + Update.errorString());
      if (ok) {
        delay(300);
        ESP.restart();
      }
    },
    []() {  // por cada pedazo del archivo
      HTTPUpload &up = http.upload();
      if (up.status == UPLOAD_FILE_START) {
        emitLog("OTA: recibiendo " + up.filename);
        if (!Update.begin(UPDATE_SIZE_UNKNOWN)) Update.printError(Serial);
      } else if (up.status == UPLOAD_FILE_WRITE) {
        if (Update.write(up.buf, up.currentSize) != up.currentSize) Update.printError(Serial);
      } else if (up.status == UPLOAD_FILE_END) {
        if (Update.end(true)) emitLog("OTA: " + String(up.totalSize) + " bytes OK");
        else Update.printError(Serial);
      } else if (up.status == UPLOAD_FILE_ABORTED) {
        Update.abort();
        emitLog("OTA: subida cancelada");
      }
    });
  http.onNotFound([]() {
    cors();
    http.send(404, "text/plain", "bicho: no existe");
  });
  http.begin();
}

void setupWifi() {
  WiFi.setHostname(FW_NAME);
  if (strlen(WIFI_SSID)) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    uint32_t t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 10000) {
      delay(200);
      readSerial();
    }
  }
  if (WiFi.status() == WL_CONNECTED) {
    staUp = true;
    WiFi.setSleep(false);  // menos latencia en el WebSocket
  } else {
    char ap[24];
    snprintf(ap, sizeof(ap), FW_NAME "-%04X", (uint16_t)(ESP.getEfuseMac() >> 32));
    WiFi.mode(WIFI_AP);
    WiFi.softAP(ap, AP_PASS);
  }
  MDNS.begin(FW_NAME);  // http://bicho.local
  MDNS.addService("http", "tcp", 80);
  setupHttp();
  ws.begin();
  ws.onEvent(onWs);
  netUp = true;
}

void setup() {
  Serial.begin(115200);
  delay(200);
  emit(infoJson());  // por USB se ve la versión altiro, antes de conectar WiFi
  setupWifi();
  emitLog(staUp ? "WiFi conectado: " + ipStr() : "Sin red: AP propio en " + ipStr());
  emit(infoJson());
}

void loop() {
  http.handleClient();
  ws.loop();
  readSerial();

  uint32_t now = millis();
  static uint32_t lastSample = 0;
  if (now - lastSample >= periodMs) {
    lastSample = now;
    String d;
    d.reserve(256);
    readSensors(d);
    emit("{\"t\":\"s\",\"ms\":" + String(now) + ",\"d\":{" + d + "}}");
  }

  static uint32_t lastInfo = 0;
  if (now - lastInfo >= 10000) {
    lastInfo = now;
    emit(infoJson());
  }
}

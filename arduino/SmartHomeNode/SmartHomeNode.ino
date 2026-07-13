/*
 * SmartHome IoT — Nó Arduino / ESP32
 * Publica sensores e recebe comandos via MQTT.
 *
 * Bibliotecas: WiFi (ESP32), PubSubClient, DHT sensor library, ESP32Servo
 * Ajuste WIFI_SSID, WIFI_PASS e MQTT_HOST antes de gravar.
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ESP32Servo.h>

// ====== CONFIG ======
const char* WIFI_SSID = "SUA_REDE";
const char* WIFI_PASS = "SUA_SENHA";
const char* MQTT_HOST = "192.168.1.10";
const uint16_t MQTT_PORT = 1883;
const char* DEVICE_ID = "arduino-sala";

#define PIN_DHT        4
#define PIN_LDR        34
#define PIN_PIR        27
#define PIN_LED        2
#define PIN_BUZZER     25
#define PIN_RELAY1     26
#define PIN_RELAY2     33
#define PIN_SERVO1     18
#define PIN_SERVO2     19
#define PIN_SERVO_ARM  21
#define DHTTYPE        DHT22

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
DHT dht(PIN_DHT, DHTTYPE);
Servo servoPorta1;
Servo servoPorta2;
Servo servoArm;

unsigned long lastSensors = 0;
unsigned long lastHeartbeat = 0;

void publishJson(const char* topic, const String& payload) {
  mqtt.publish(topic, payload.c_str());
}

void setLed(bool on) { digitalWrite(PIN_LED, on ? HIGH : LOW); }
void setBuzzer(bool on) { digitalWrite(PIN_BUZZER, on ? HIGH : LOW); }
void setRelay(uint8_t ch, bool on) {
  if (ch == 1) digitalWrite(PIN_RELAY1, on ? LOW : HIGH); // relé ativo em LOW
  if (ch == 2) digitalWrite(PIN_RELAY2, on ? LOW : HIGH);
}

void applyServo(const String& id, int angle) {
  angle = constrain(angle, 0, 180);
  if (id == "porta-1") servoPorta1.write(angle);
  else if (id == "porta-2") servoPorta2.write(angle);
  else if (id == "arm") servoArm.write(angle);
}

void onMessage(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];

  if (String(topic) == "house/led") {
    setLed(msg.indexOf("true") >= 0 || msg.indexOf("\"on\": true") >= 0 || msg.indexOf("\"on\":true") >= 0);
  } else if (String(topic) == "house/buzzer") {
    setBuzzer(msg.indexOf("true") >= 0 || msg.indexOf("\"on\":true") >= 0 || msg.indexOf("\"on\": true") >= 0);
  } else if (String(topic) == "house/relay") {
    int ch = 1;
    if (msg.indexOf("\"channel\":\"2\"") >= 0 || msg.indexOf("\"channel\": \"2\"") >= 0) ch = 2;
    bool on = msg.indexOf("\"on\":true") >= 0 || msg.indexOf("\"on\": true") >= 0;
    setRelay(ch, on);
  } else if (String(topic) == "house/servo") {
    String id = "porta-1";
    if (msg.indexOf("porta-2") >= 0) id = "porta-2";
    if (msg.indexOf("\"arm\"") >= 0) id = "arm";
    int angle = 0;
    int idx = msg.indexOf("\"angle\"");
    if (idx >= 0) {
      int colon = msg.indexOf(':', idx);
      angle = msg.substring(colon + 1).toInt();
    }
    applyServo(id, angle);
  } else if (String(topic) == "house/door") {
    bool openDoor = msg.indexOf("\"open\":true") >= 0 || msg.indexOf("\"open\": true") >= 0;
    if (msg.indexOf("garage") >= 0) applyServo("porta-2", openDoor ? 90 : 0);
    else applyServo("porta-1", openDoor ? 90 : 0);
  }
}

void ensureMqtt() {
  while (!mqtt.connected()) {
    String clientId = String("arduino-") + DEVICE_ID;
    if (mqtt.connect(clientId.c_str())) {
      mqtt.subscribe("house/led");
      mqtt.subscribe("house/buzzer");
      mqtt.subscribe("house/relay");
      mqtt.subscribe("house/servo");
      mqtt.subscribe("house/door");
      publishJson("house/status", String("{\"board\":\"arduino\",\"online\":true,\"id\":\"") + DEVICE_ID + "\"}");
    } else {
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_RELAY1, OUTPUT);
  pinMode(PIN_RELAY2, OUTPUT);
  pinMode(PIN_PIR, INPUT);
  setRelay(1, false);
  setRelay(2, false);

  dht.begin();
  servoPorta1.attach(PIN_SERVO1);
  servoPorta2.attach(PIN_SERVO2);
  servoArm.attach(PIN_SERVO_ARM);
  servoPorta1.write(0);
  servoPorta2.write(0);
  servoArm.write(45);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.println("\nWiFi OK");

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
}

void loop() {
  ensureMqtt();
  mqtt.loop();

  unsigned long now = millis();
  if (now - lastSensors > 2000) {
    lastSensors = now;
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    int ldr = analogRead(PIN_LDR);
    float light = map(ldr, 0, 4095, 0, 100);
    bool motion = digitalRead(PIN_PIR) == HIGH;

    if (!isnan(t)) publishJson("house/temp", String("{\"value\":") + String(t, 1) + "}");
    if (!isnan(h)) publishJson("house/humidity", String("{\"value\":") + String(h, 1) + "}");
    publishJson("house/light", String("{\"value\":") + String(light, 1) + "}");
    publishJson("house/motion", String("{\"value\":") + (motion ? "true" : "false") + "}");
  }

  if (now - lastHeartbeat > 1500) {
    lastHeartbeat = now;
    publishJson("house/sync", "{\"board\":\"arduino\",\"ok\":true}");
  }
}

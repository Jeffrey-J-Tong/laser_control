// ===== Laser TTL Debug Sketch =====
// Commands (case-insensitive, newline optional):
//   "pulse"  -> start 0.5s ON / 0.5s OFF square wave
//   "steady" -> TTL held HIGH continuously
//   "stop"   -> stop output, pull TTL LOW
// Pin assignments: TTL_PIN = 8, baud = 115200

const uint8_t       TTL_PIN     = 8;
const uint8_t       LED_PIN     = 13;
const unsigned long SERIAL_BAUD = 115200;
const unsigned long HALF_PERIOD = 500;  // ms per half-cycle in pulse mode

enum class Mode { IDLE, PULSE, STEADY };

Mode          mode       = Mode::IDLE;
bool          ttlState   = false;
unsigned long lastToggle = 0;

String cmdBuf = "";  // accumulate serial characters into a command line

// ---- helpers ----------------------------------------------------------------

void setOutput(bool high) {
  ttlState = high;
  digitalWrite(TTL_PIN, high ? HIGH : LOW);
  digitalWrite(LED_PIN, high ? HIGH : LOW);
}

void enterIdle() {
  mode = Mode::IDLE;
  setOutput(false);
  Serial.println(F("STOP"));
}

void enterPulse() {
  mode       = Mode::PULSE;
  lastToggle = millis();
  setOutput(true);
  Serial.println(F("PULSE"));
}

void enterSteady() {
  mode = Mode::STEADY;
  setOutput(true);
  Serial.println(F("STEADY"));
}

void handleCommand(const String& cmd) {
  // Trim and convert to lower-case for case-insensitive matching
  String c = cmd;
  c.trim();
  c.toLowerCase();

  if (c == "pulse") {
    enterPulse();
  } else if (c == "steady") {
    enterSteady();
  } else if (c == "stop") {
    enterIdle();
  } else if (c.length() > 0) {
    // Echo back unknown commands so the user knows what was received
    Serial.print(F("UNKNOWN: "));
    Serial.println(c);
  }
}

// ---- Arduino lifecycle ------------------------------------------------------

void setup() {
  pinMode(TTL_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  setOutput(false);

  Serial.begin(SERIAL_BAUD);
  Serial.println(F("READY  commands: pulse | steady | stop"));
}

void loop() {
  // 1) Read serial into line buffer; dispatch on newline or CR
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\n' || ch == '\r') {
      handleCommand(cmdBuf);
      cmdBuf = "";
    } else {
      cmdBuf += ch;
    }
  }

  // 2) Non-blocking square-wave toggle (only active in PULSE mode)
  if (mode == Mode::PULSE && (millis() - lastToggle >= HALF_PERIOD)) {
    lastToggle += HALF_PERIOD;
    setOutput(!ttlState);
    Serial.print(F("T,"));
    Serial.println(ttlState ? 1 : 0);
  }
}
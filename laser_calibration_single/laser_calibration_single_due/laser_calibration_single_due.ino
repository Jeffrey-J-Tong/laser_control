// ===== Laser Analog Output Debug Sketch (Arduino Due) =====
// Commands (case-insensitive, newline optional):
//   "pulse"  -> start 0.5s ON / 0.5s OFF square wave
//   "steady" -> output held HIGH (3.3V) continuously
//   "stop"   -> stop output, pull output LOW (0V)
// Pin assignments: DAC0 (analog out), LED_PIN = 13, baud = 115200

const uint8_t       DAC_PIN     = DAC0;   // Due 模拟输出引脚
const uint8_t       LED_PIN     = 13;
const unsigned long SERIAL_BAUD = 115200;
const unsigned long HALF_PERIOD = 500;  // ms per half-cycle in pulse mode
const int           DAC_MAX     = 4095;  // 12-bit 满量程 (约3.3V)
const int           DAC_MIN     = 0;     // 0V

enum class Mode { IDLE, PULSE, STEADY };

Mode          mode       = Mode::IDLE;
bool          ttlState   = false;
unsigned long lastToggle = 0;

String cmdBuf = "";  // accumulate serial characters into a command line

// ---- helpers ----------------------------------------------------------------

void setOutput(bool high) {
  ttlState = high;
  analogWrite(DAC_PIN, high ? DAC_MAX : DAC_MIN);
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
  analogWriteResolution(12);  // 设置 DAC 为 12-bit 分辨率 (0-4095)
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
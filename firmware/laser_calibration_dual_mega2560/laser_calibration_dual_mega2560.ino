// ===== Dual-Channel Laser TTL Debug Sketch =====
// Commands (case-insensitive, newline optional):
//   "red"    -> select the RED channel for subsequent steady/pulse/stop commands
//   "blue"   -> select the BLUE channel for subsequent steady/pulse/stop commands
//   "pulse"  -> start 0.5s ON / 0.5s OFF square wave on the selected channel
//   "steady" -> hold the selected channel's TTL HIGH continuously
//   "stop"   -> stop output on the selected channel, pull its TTL LOW
//
// Each channel runs its own independent state machine, so switching the
// selected channel never affects the other channel's current output.
//
// Pin assignments:
//   BLUE laser signal = PIN8
//   RED  laser signal = PIN9
//   baud = 115200
//
// Note: sync signals for the external recording system are now split off
// the BLUE/RED TTL lines in hardware (passive splitter), so no separate
// sync pins are driven from the firmware.

const uint8_t       BLUE_TTL_PIN = 8;
const uint8_t       RED_TTL_PIN  = 9;
const uint8_t       LED_PIN      = 13;
const unsigned long SERIAL_BAUD  = 115200;
const unsigned long HALF_PERIOD  = 500;  // ms per half-cycle in pulse mode, shared by both channels

enum class Mode { IDLE, PULSE, STEADY };

struct Channel {
  const char*   name;
  uint8_t       ttlPin;
  Mode          mode;
  bool          ttlState;
  unsigned long lastToggle;

  Channel(const char* n, uint8_t ttl)
    : name(n), ttlPin(ttl),
      mode(Mode::IDLE), ttlState(false), lastToggle(0) {}
};

Channel blueCh("BLUE", BLUE_TTL_PIN);
Channel redCh ("RED",  RED_TTL_PIN);
Channel* selected = &blueCh;  // default-selected channel at power-up

String cmdBuf = "";  // accumulate serial characters into a command line

// ---- helpers ----------------------------------------------------------------

// Any channel non-idle keeps the onboard LED lit
void updateLed() {
  bool anyActive = (blueCh.mode != Mode::IDLE) || (redCh.mode != Mode::IDLE);
  digitalWrite(LED_PIN, anyActive ? HIGH : LOW);
}

void setOutput(Channel& ch, bool high) {
  ch.ttlState = high;
  digitalWrite(ch.ttlPin, high ? HIGH : LOW);
  updateLed();
}

void enterIdle(Channel& ch) {
  ch.mode = Mode::IDLE;
  setOutput(ch, false);
  Serial.print(ch.name);
  Serial.println(F(" STOP"));
}

void enterPulse(Channel& ch) {
  ch.mode       = Mode::PULSE;
  ch.lastToggle = millis();
  setOutput(ch, true);
  Serial.print(ch.name);
  Serial.println(F(" PULSE"));
}

void enterSteady(Channel& ch) {
  ch.mode = Mode::STEADY;
  setOutput(ch, true);
  Serial.print(ch.name);
  Serial.println(F(" STEADY"));
}

void tickPulse(Channel& ch) {
  if (ch.mode == Mode::PULSE && (millis() - ch.lastToggle >= HALF_PERIOD)) {
    ch.lastToggle += HALF_PERIOD;
    setOutput(ch, !ch.ttlState);
    Serial.print(ch.name);
    Serial.print(F(" T,"));
    Serial.println(ch.ttlState ? 1 : 0);
  }
}

void handleCommand(const String& cmd) {
  // Trim and convert to lower-case for case-insensitive matching
  String c = cmd;
  c.trim();
  c.toLowerCase();

  if (c == "red") {
    selected = &redCh;
    Serial.println(F("SELECTED: RED"));
  } else if (c == "blue") {
    selected = &blueCh;
    Serial.println(F("SELECTED: BLUE"));
  } else if (c == "pulse") {
    enterPulse(*selected);
  } else if (c == "steady") {
    enterSteady(*selected);
  } else if (c == "stop") {
    enterIdle(*selected);
  } else if (c.length() > 0) {
    // Echo back unknown commands so the user knows what was received
    Serial.print(F("UNKNOWN: "));
    Serial.println(c);
  }
}

// ---- Arduino lifecycle ------------------------------------------------------

void setup() {
  pinMode(BLUE_TTL_PIN, OUTPUT);
  pinMode(RED_TTL_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  setOutput(blueCh, false);
  setOutput(redCh, false);

  Serial.begin(SERIAL_BAUD);
  Serial.println(F("READY  commands: red | blue (select channel), then pulse | steady | stop"));
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

  // 2) Non-blocking square-wave toggle for each channel independently
  //    (only active in PULSE mode; switching selection never pauses either channel)
  tickPulse(blueCh);
  tickPulse(redCh);
}

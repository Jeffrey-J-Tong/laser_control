// ===== Dual-Channel Laser TTL Pulse Controller (Mega 2560) =====
// Input format: color,pulseWidth_ms,frequency_Hz,count\n
// Example: blue,10,2,50\n  -> BLUE channel, pulse width 10 ms, 2 Hz, 50 pulses
//          red,20,5,20\n   -> RED  channel, pulse width 20 ms, 5 Hz, 20 pulses
//
// Communication protocol with Python host:
//   Startup          Arduino -> PC : "Ready."
//   Receive params   PC -> Arduino : "{color},{width},{freq},{count}\n"
//   Acknowledge      Arduino -> PC : "ACK,color=...,pw=...,f=...,n=..."
//   Pulse start      Arduino -> PC : "START,{color},{millis}"
//   Each pulse       Arduino -> PC : "P,{color},{index},{elapsed_ms}"
//   Round complete   Arduino -> PC : "Ready."   <- PC waits for this before next round
//
// Pin assignments:
//   BLUE laser signal = PIN8
//   RED  laser signal = PIN9
//   baud = 115200
//
// Only one pulse train runs at a time (this sketch blocks for the duration of
// each train), matching the sequential, round-by-round control from the
// Python host: blue and red trains never overlap even though both channels
// live on the same board.

const uint8_t  BLUE_TTL_PIN     = 8;
const uint8_t  RED_TTL_PIN      = 9;
const uint8_t  LED_PIN          = 13;      // Onboard LED for visual indication
const uint32_t SERIAL_BAUD      = 115200;
const uint8_t  MAX_CMD_LEN      = 64;

char    cmdBuf[MAX_CMD_LEN];
uint8_t cmdLen = 0;

void setup() {
  pinMode(BLUE_TTL_PIN, OUTPUT);
  pinMode(RED_TTL_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(BLUE_TTL_PIN, LOW);
  digitalWrite(RED_TTL_PIN, LOW);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(SERIAL_BAUD);

  // Signal to Python that Arduino is ready to receive the first command.
  // Python will wait for this before sending the first parameter set.
  Serial.println(F("Ready."));
}

void loop() {
  // Line-buffered serial reading; process when '\n' is received
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      cmdBuf[cmdLen] = '\0';
      if (cmdLen > 0) processCommand(cmdBuf);
      cmdLen = 0;
    } else if (c == '\r') {
      // Ignore carriage return
    } else if (cmdLen < MAX_CMD_LEN - 1) {
      cmdBuf[cmdLen++] = c;
    } else {
      cmdLen = 0;
      Serial.println(F("ERR:overflow"));
    }
  }
}

void processCommand(char* cmd) {
  char* p0 = strtok(cmd, ",");   // color
  char* p1 = strtok(NULL, ","); // pulse width
  char* p2 = strtok(NULL, ","); // frequency
  char* p3 = strtok(NULL, ","); // count
  if (!p0 || !p1 || !p2 || !p3) { Serial.println(F("ERR:format")); return; }

  String colorArg = String(p0);
  colorArg.trim();
  colorArg.toLowerCase();

  uint8_t     ttlPin;
  const char* colorName;
  if (colorArg == "blue") {
    ttlPin    = BLUE_TTL_PIN;
    colorName = "BLUE";
  } else if (colorArg == "red") {
    ttlPin    = RED_TTL_PIN;
    colorName = "RED";
  } else {
    Serial.println(F("ERR:color"));
    return;
  }

  long   pulseWidth = atol(p1);   // ms
  double frequency  = atof(p2);   // Hz, supports decimal values
  long   count      = atol(p3);

  if (pulseWidth <= 0 || frequency <= 0 || count <= 0) {
    Serial.println(F("ERR:value")); return;
  }
  double periodMs = 1000.0 / frequency;
  if ((double)pulseWidth >= periodMs) {
    Serial.println(F("ERR:pw>=period")); return;
  }

  // 1) Acknowledge received parameters
  Serial.print(F("ACK,color=")); Serial.print(colorName);
  Serial.print(F(",pw="));       Serial.print(pulseWidth);
  Serial.print(F(",f="));        Serial.print(frequency, 3);
  Serial.print(F(",n="));        Serial.println(count);

  // 2) Generate pulse train
  //    Use millis() to anchor each pulse start time — prevents drift accumulation
  unsigned long trainStart = millis();
  Serial.print(F("START,"));
  Serial.print(colorName);
  Serial.print(F(","));
  Serial.println(trainStart);

  for (long i = 0; i < count; i++) {
    unsigned long target = trainStart + (unsigned long)((double)i * periodMs);
    while ((long)(millis() - target) < 0) { /* busy-wait for precise timing */ }

    digitalWrite(ttlPin, HIGH);
    digitalWrite(LED_PIN, HIGH);
    delay(pulseWidth);
    digitalWrite(ttlPin, LOW);
    digitalWrite(LED_PIN, LOW);

    // Report channel, pulse index and elapsed time since train start
    Serial.print(F("P,"));
    Serial.print(colorName);
    Serial.print(F(","));
    Serial.print(i + 1);
    Serial.print(F(","));
    Serial.println(millis() - trainStart);
  }

  // 3) Signal Python that this round is complete and Arduino is ready for next command.
  //    Python will apply its latency delay *before* sending the next parameter set,
  //    so no delay is needed here.
  Serial.println(F("Ready."));
}

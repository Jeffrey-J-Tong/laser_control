// ===== Laser TTL Pulse Controller (Mega 2560) =====
// Input format: pulseWidth_ms,frequency_Hz,count\n
// Example: 10,2,50\n  -> pulse width 10 ms, 2 Hz, 50 pulses
//
// Communication protocol with Python host:
//   Startup          Arduino → PC : "Ready."
//   Receive params   PC → Arduino : "{width},{freq},{count}\n"
//   Acknowledge      Arduino → PC : "ACK,pw=...,f=...,n=..."
//   Pulse start      Arduino → PC : "START,{millis}"
//   Each pulse       Arduino → PC : "P,{index},{elapsed_ms}"
//   Round complete   Arduino → PC : "Ready."   ← PC waits for this before next round

const uint8_t  TTL_PIN          = 8;       // TTL output (connected to laser external trigger)
const uint8_t  LED_PIN          = 13;      // Onboard LED for visual indication
const uint32_t SERIAL_BAUD      = 115200;
const uint8_t  MAX_CMD_LEN      = 64;

char    cmdBuf[MAX_CMD_LEN];
uint8_t cmdLen = 0;

void setup() {
  pinMode(TTL_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(TTL_PIN, LOW);
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
  char* p1 = strtok(cmd, ",");
  char* p2 = strtok(NULL, ",");
  char* p3 = strtok(NULL, ",");
  if (!p1 || !p2 || !p3) { Serial.println(F("ERR:format")); return; }

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
  Serial.print(F("ACK,pw=")); Serial.print(pulseWidth);
  Serial.print(F(",f="));     Serial.print(frequency, 3);
  Serial.print(F(",n="));     Serial.println(count);

  // 2) Generate pulse train
  //    Use millis() to anchor each pulse start time — prevents drift accumulation
  unsigned long trainStart = millis();
  Serial.print(F("START,")); Serial.println(trainStart);

  for (long i = 0; i < count; i++) {
    unsigned long target = trainStart + (unsigned long)((double)i * periodMs);
    while ((long)(millis() - target) < 0) { /* busy-wait for precise timing */ }

    digitalWrite(TTL_PIN, HIGH);
    digitalWrite(LED_PIN, HIGH);
    delay(pulseWidth);
    digitalWrite(TTL_PIN, LOW);
    digitalWrite(LED_PIN, LOW);

    // Report pulse index and elapsed time since train start
    Serial.print(F("P,"));
    Serial.print(i + 1);
    Serial.print(F(","));
    Serial.println(millis() - trainStart);
  }

  // 3) Signal Python that this round is complete and Arduino is ready for next command.
  //    Python will apply its latency delay *before* sending the next parameter set,
  //    so no delay is needed here.
  Serial.println(F("Ready."));
}

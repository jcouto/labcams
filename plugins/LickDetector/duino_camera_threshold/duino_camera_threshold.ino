const byte PIN0 = 1;
const byte PIN1 = 2;

void setup() {
  // put youZr setup code here, to run once:
  pinMode(PIN0, OUTPUT);
  pinMode(PIN1, OUTPUT);
  digitalWriteFast(PIN0, LOW);
  digitalWriteFast(PIN1, LOW);
  Serial.begin(2000000);

}

void loop() {
  // put your main code here, to run repeatedly:

}


#define UP_MSG 'U'
#define DOWN_MSG 'D'

char msg[256];
int p_msg = -1;
#define STX '@'
#define ETX '\n'
void serialEvent() {
  while (Serial.available()) {
    char ch = Serial.read();
    switch (ch) {
      case STX:
        // message start
        p_msg = 0;
        for (unsigned int i=0; i < 256; i++) { // clear the message...
          msg[i] = (char) NULL;
        }
        break;
      case ETX:
        // end
        p_msg = -1; 
        _parse_message();
        break;
      default:
        if (p_msg == -1) {
          // something wrong
          break;
        }
        msg[p_msg] = ch;
        p_msg++;
        break;
    }
  }
}

void _parse_message() {
  int value;
  switch (msg[0]) {
    case UP_MSG:
      Serial.println(msg);
      value = atoi(&msg[1]); // read the motor
      switch (value) {
      case 1:
        digitalWrite(PIN1, HIGH);
        break;
      default:
        digitalWrite(PIN0, HIGH);
       break;
      }
      break;
   case DOWN_MSG:
      value = atoi(&msg[1]); // read the motor
      switch (value) {
      case 1:
        digitalWrite(PIN1, LOW);
        break;
      default:
        digitalWrite(PIN0, LOW);
       break;
      }
      break;
  }
}

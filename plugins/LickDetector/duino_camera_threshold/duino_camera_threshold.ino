const byte PIN0 = 1;
const byte PIN1 = 2;
#define USE_CAPACITIVE
#define LICK0 22
#define LICK1 23
float lick0_value = 0.0;
float lick1_value = 0.0;
float lick0_lpass = 0.0;
float lick1_lpass = 0.0;


float lick0_threshold = 15;
float lick1_threshold = 15;
float threshold_offset = 7;
constexpr float k = 0.1; //0.2
constexpr float klpass = 0.9; //0.999

short lickon0 = 0;
short lickon1 = 0;

#define LISTEN_MSG

void setup() {
  // put youZr setup code here, to run once:
  pinMode(PIN0, OUTPUT);
  pinMode(PIN1, OUTPUT);
  digitalWriteFast(PIN0, LOW);
  digitalWriteFast(PIN1, LOW);
  Serial.begin(2000000);
  #ifdef USE_CAPACITIVE
  pinMode(LICK0, OUTPUT);
  pinMode(LICK1, OUTPUT);
  digitalWriteFast(LICK0, LOW);
  digitalWriteFast(LICK1, LOW);
  #endif
}

void loop() {
  #ifdef USE_CAPACITIVE
   float l0 = touchRead(LICK0);
   float l1 = touchRead(LICK1);

//    Serial.print(',');
   if (l0 < 60000.) // this to prevent some strange behaviour on movement
        lick0_value = (k * l0 + (1 - k) * lick0_value); //k * l0 + (1 - k) * lick0_value;
   lick0_lpass = lick0_lpass*klpass + (1-klpass)*lick0_value;
   if (l1 < 60000.) // this to prevent some strange behaviour on movement
        lick1_value =  (k * l1 + (1 - k) * lick1_value); //k * l0 + (1 - k) * lick0_value;
   lick1_lpass = lick1_lpass*klpass + (1-klpass)*lick1_value;
   
   if (((lick0_value - lick0_lpass) >= lick0_threshold) and (lickon0 == 0)) {
     lickon0 = 1;
     digitalWriteFast(PIN0,HIGH);
   }
   else if (((lick0_value - lick0_lpass) < (lick0_threshold-threshold_offset)) and (lickon0 == 1)) {
      lickon0 = 0;
      digitalWriteFast(PIN0,LOW);
   }
   if (((lick1_value - lick1_lpass) >= lick1_threshold) and (lickon1 == 0)) {
     lickon1 = 1;
     digitalWriteFast(PIN1,HIGH);
   }
   else if (((lick1_value - lick1_lpass) < (lick1_threshold-threshold_offset)) and (lickon1 == 1)) {
      lickon1 = 0;
      digitalWriteFast(PIN1,LOW);
   }

    Serial.print((lick0_value - lick0_lpass));
    Serial.print(',');
    Serial.print((lick1_value  - lick1_lpass));
    Serial.print(',');
    if (lickon0 == 1) Serial.print(45); else Serial.print(30);
    Serial.print(','); 
    if (lickon1 == 1) Serial.println(46); else Serial.println(31); 

   #endif
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

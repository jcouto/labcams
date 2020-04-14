// WARNING: The teensy will become unresponsive if you use a pulse width longer than the exposure time.

const byte PIN_CAM_EXPOSURE = 2;
const byte PIN_CAM_TRIGGER = 3;
const byte PIN_LED0_TRIGGER = 4;
const byte PIN_LED1_TRIGGER = 5;

volatile long current_time = 0;
volatile long start_time = 0;
volatile long last_pulse_count = -1;
volatile long last_rise = -1;
volatile byte last_led = 0;

volatile long pulse_count = 0; // number of pulses to trigger
volatile int pulse_width = 15000; // width of the stimulation pulse (us)
volatile int pulse_delay = 1000; // delay of the stimulation in us
volatile byte mode = 3;       // mode 0 : trigger the camera only
                              // mode 1 : LED0
                              // mode 2 : LED1
                              // mode 3 : LEDs alternate
volatile byte armed = 0;      // whether the triggers are armed  

// Serial communication
#define STX '@'
#define ETX '\n'
#define SEP "_"

#define START_LEDS 'N'
#define STOP_LEDS 'S'
#define SET_PARAMETERS 'P' // set the width and the delay
#define SET_MODE 'M' // set the width and the delay
#define FRAME 'F' // signal the frame time

// Serial communication "receive"
# define MSGSIZE 64
char msg[MSGSIZE];
int cnt = 0;
/* // This can be used to control how much the LEDs are ON (at the expense of a delay in the interrupt)
void camera_triggered() {
  
  pulse_count++;
  if (armed) {
    // set the time of the next pulse
    byte pin;
    switch (mode) {
      case 1:
          pin = PIN_LED0_TRIGGER;
          break;
      case 2:
          pin = PIN_LED1_TRIGGER;
          break;
      case 3:
        int tmp = pulse_count % 2;
        if (tmp == 0)
          pin = PIN_LED1_TRIGGER;
        else
          pin = PIN_LED0_TRIGGER;
        break;
      default:
          pin = PIN_LED0_TRIGGER;
    }
    delayMicroseconds(pulse_delay);
    digitalWriteFast(pin, HIGH);
    delayMicroseconds(pulse_width);
    digitalWriteFast(pin, LOW);    
    last_rise = millis() - start_time;
    last_led = pin;
    last_pulse_count = pulse_count;
    
  }
}
*/
void camera_triggered() {
  if (digitalReadFast(PIN_CAM_EXPOSURE) == LOW) {
        digitalWriteFast(PIN_LED0_TRIGGER, LOW);
      digitalWriteFast(PIN_LED1_TRIGGER, LOW);  
  } else {
    
  if (armed) {
    pulse_count++;
    // set the time of the next pulse
    byte pin;
    switch (mode) {
      case 1:
          pin = PIN_LED0_TRIGGER;
          break;
      case 2:
          pin = PIN_LED1_TRIGGER;
          break;
      case 3:
        int tmp = pulse_count % 2;
        if (tmp == 0)
          pin = PIN_LED1_TRIGGER;
        else
          pin = PIN_LED0_TRIGGER;
        break;
      default:
          pin = PIN_LED0_TRIGGER;
    }
    digitalWriteFast(pin, HIGH);
    last_rise = millis() - start_time;
    last_led = pin;
    last_pulse_count = pulse_count;    
  }
}
}

void setup() {
  pinMode(PIN_LED0_TRIGGER, OUTPUT);
  pinMode(PIN_LED1_TRIGGER, OUTPUT);
  pinMode(PIN_CAM_TRIGGER, OUTPUT);
  pinMode(PIN_CAM_EXPOSURE, INPUT);

  digitalWriteFast(PIN_LED0_TRIGGER, LOW);
  digitalWriteFast(PIN_LED1_TRIGGER, LOW);
  digitalWriteFast(PIN_CAM_TRIGGER, LOW);

  Serial.begin(115200);
  attachInterrupt(digitalPinToInterrupt(PIN_CAM_EXPOSURE), camera_triggered, CHANGE);
  start_time = millis();
}

void loop() {
  //current_time = millis() - start_time;
  if (last_rise > 0) {
    Serial.print(STX);
    Serial.print(FRAME);
    Serial.print(SEP);
    Serial.print(last_led);
    Serial.print(SEP);
    Serial.print(last_pulse_count);
    Serial.print(SEP);
    Serial.print(last_rise);
    Serial.print(ETX);
    last_rise = -1;
  }
  if (armed)
      digitalWriteFast(PIN_CAM_TRIGGER, HIGH);
  else
      digitalWriteFast(PIN_CAM_TRIGGER, LOW);
  
//  if (((next_rise - current_time) <= 0) & ((next_rise + pulse_width - current_time) >= 0)) {
//    digitalWriteFast(PIN_LED0_TRIGGER, HIGH);
//  }
//  else {
//    digitalWriteFast(PIN_LED0_TRIGGER, LOW);
//  }
}


void serialEvent()
{
  while (Serial.available()) {
    char ch = Serial.read();
    char* token;
    if (ch == STX || cnt > 0) {
      msg[cnt] = ch;
      cnt++;
      if (ch == ETX) {
        cnt = 0;
        String reply = String(STX);
        switch (msg[1]) {
          case START_LEDS:
            // @N
            pulse_count = 0;
            armed = 1;
            reply += START_LEDS;
            Serial.print(reply);
            Serial.print(SEP);
            Serial.print(current_time);
            Serial.print(ETX);
            break;
        case STOP_LEDS:
            // @S
            armed = 0;
            reply += STOP_LEDS;
            Serial.print(reply);
            Serial.print(SEP);
            Serial.print(current_time);
            Serial.print(ETX);
            break;
        case SET_MODE:
            // @M
            token = strtok(msg, SEP);
            token = strtok(NULL, SEP);
            mode = atoi(token);
            reply += SET_MODE;
            Serial.print(reply);
            Serial.print(SEP);
            Serial.print(mode);
            Serial.print(ETX);
            break;
          case SET_PARAMETERS:
            setParameters(msg);
            reply += SET_PARAMETERS;
            Serial.print(reply);
            Serial.print(SEP);
            Serial.print(pulse_width);
            Serial.print(SEP);
            Serial.print(pulse_delay);
            Serial.print(ETX);
            break;
          default:
            reply += "E";
            reply += 1;
            reply += ETX;
            Serial.print(reply);
            break;
        }
      }
    }
  }
  Serial.flush();
}

void setParameters(char* msg)
{
  // parameters are formated like: WIDTH_MARGIN
  char* token;
  // Parse string using a (destructive method) 
  token = strtok(msg, SEP);
  token = strtok(NULL, SEP);
  pulse_width = atoi(token);
  token = strtok(NULL, SEP); 
  pulse_delay = atoi(token);
  // need to acknowledge that this was set
}

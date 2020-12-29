
const byte PIN_CAM_EXPOSURE = 2;
const byte PIN_SYNC = 3;
const byte PIN_LED0_TRIGGER = 4;
const byte PIN_LED1_TRIGGER = 5;

volatile long current_time = 0;
volatile long start_time = 0;
volatile long last_pulse_count = 0;
volatile long last_rise = -1;
volatile byte last_led = 0;

//sync counts
volatile long last_sync_rise = -1;
volatile long sync_count = 0;
volatile long sync_frame_count = 0;

volatile long pulse_count = 0; // number of pulses to trigger
volatile byte mode = 3;       // mode 0 : trigger the camera only
                              // mode 1 : LED0
                              // mode 2 : LED1
                              // mode 3 : LEDs alternate
volatile byte armed = 0;      // whether the triggers are armed  

// Serial communication
#define STX '@'
#define ETX '\n'
#define SEP "_"
#define CAP "NCHANNELS_2_MODES_470nm:405nm:both" // capabilities for interfacing with labcams

#define QUERY_CAP 'Q'
#define START_LEDS 'N'
#define STOP_LEDS 'S'
#define FRAME 'F' // signal the frame time
#define SYNC 'T' // signal the sync time

//#define SET_PARAMETERS 'P' // placeholder
#define SET_MODE 'M' // set the width and the delay

// Serial communication "receive"
# define MSGSIZE 64
char msg[MSGSIZE];
int cnt = 0;

// interrupt to handle flipping the LEDS
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
      {
        int tmp = pulse_count % 2;
        if (tmp == 0)
          pin = PIN_LED1_TRIGGER;
        else
          pin = PIN_LED0_TRIGGER;
      }
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

void sync_received() {
  if (digitalReadFast(PIN_SYNC) == HIGH)
    sync_count++;
  sync_frame_count = pulse_count;
  last_sync_rise = millis() - start_time;
  }


void setup() {
  pinMode(PIN_LED0_TRIGGER, OUTPUT);
  pinMode(PIN_LED1_TRIGGER, OUTPUT);
  pinMode(PIN_SYNC, INPUT);
  pinMode(PIN_CAM_EXPOSURE, INPUT);

  digitalWriteFast(PIN_LED0_TRIGGER, LOW);
  digitalWriteFast(PIN_LED1_TRIGGER, LOW);

  Serial.begin(2000000);
  attachInterrupt(digitalPinToInterrupt(PIN_CAM_EXPOSURE), camera_triggered, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_SYNC), sync_received, CHANGE);
  start_time = millis(); // use micros if more precision needed
}

void loop() {
  current_time = millis() - start_time;
  if ((last_rise > 0) & (abs(current_time - last_rise)> 10)) { // this is limited to 10ms
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
  if (last_sync_rise > 0){ // this is limited to 10ms
    Serial.print(STX);
    Serial.print(SYNC);
    Serial.print(SEP);
    Serial.print(sync_frame_count);
    Serial.print(SEP);
    Serial.print(sync_count);
    Serial.print(SEP);
    Serial.print(last_sync_rise);
    Serial.print(ETX);
    last_sync_rise = -1;
}
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
            last_sync_rise = -1;
            last_rise = -1;
            start_time = millis();
            pulse_count = 0;
            sync_frame_count = 0;
            sync_count = 0;
	    last_pulse_count = 0;
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
        case QUERY_CAP:
            // @Q
            reply += QUERY_CAP;
            Serial.print(reply);
            Serial.print(SEP);
            Serial.print(CAP);
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

          /*case SET_PARAMETERS:
            setParameters(msg);
            reply += SET_PARAMETERS;
            Serial.print(reply);
            Serial.print(SEP);
            Serial.print(pulse_width);
            Serial.print(SEP);
            Serial.print(pulse_delay);
            Serial.print(ETX);
            break;*/

/*void setParameters(char* msg)
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
*/


/*
>> Pulse Sensor Amped 1.2 <<
This code is for Pulse Sensor Amped by Joel Murphy and Yury Gitman
    www.pulsesensor.com 
    >>> Pulse Sensor purple wire goes to Analog Pin 0 <<<
Pulse Sensor sample aquisition and processing happens in the background via Timer 2 interrupt. 2mS sample rate.
PWM on pins 3 and 11 will not work when using this code, because we are using Timer 2!
The following variables are automatically updated:
Signal :    int that holds the analog signal data straight from the sensor. updated every 2mS.
IBI  :      int that holds the time interval between beats. 2mS resolution.
BPM  :      int that holds the heart rate value, derived every beat, from averaging previous 10 IBI values.
QS  :       boolean that is made true whenever Pulse is found and BPM is updated. User must reset.
Pulse :     boolean that is true when a heartbeat is sensed then false in time with pin13 LED going out.

This code is designed with output serial data to Processing sketch "PulseSensorAmped_Processing-xx"
The Processing sketch is a simple data visualizer. 
All the work to find the heartbeat and determine the heartrate happens in the code below.
Pin 13 LED will blink with heartbeat.
If you want to use pin 13 for something else, adjust the interrupt handler
It will also fade an LED on pin fadePin with every beat. Put an LED and series resistor from fadePin to GND.
Check here for detailed code walkthrough:
http://pulsesensor.myshopify.com/pages/pulse-sensor-amped-arduino-v1dot1

Code Version 1.2 by Joel Murphy & Yury Gitman  Spring 2013
This update fixes the firstBeat and secondBeat flag usage so that realistic BPM is reported.



Adapted by A. Riss, 2015: handling of button (so that you need to press a button to turn on the LED)
*/


//  VARIABLES
int pulsePin = 0;                 // Pulse Sensor purple wire connected to analog pin 0
int blinkPin = 13;                // pin to blink led at each beat
int fadePin = 5;                  // pin to do fancy classy fading blink at each beat
int fadeRate = 0;                 // used to fade LED on with PWM on fadePin
int sensorpowerPin = 6;           // pin to switch on to power the sensor
int buttonPin = 10;               // pin for the on/off button

int longpress_len = 3;           // length for long-pressing button


// these variables are volatile because they are used during the interrupt service routine!
volatile int BPM;                   // used to hold the pulse rate
volatile int Signal;                // holds the incoming raw data
volatile int IBI = 600;             // holds the time between beats, must be seeded! 
volatile boolean Pulse = false;     // true when pulse wave is high, false when it's low
volatile boolean QS = false;        // becomes true when Arduoino finds a beat.

// for switching on/off via button
enum { EV_NONE=0, EV_SHORTPRESS, EV_LONGPRESS };
boolean button_was_pressed; // previous state
int button_pressed_counter; // press running duration
boolean sensor_is_running;  // sensor on?


void setup(){
  pinMode(blinkPin,OUTPUT);         // pin that will blink to your heartbeat!
  pinMode(fadePin,OUTPUT);          // pin that will fade to your heartbeat!
  
  pinMode(sensorpowerPin,OUTPUT);   // pin that will provide power for the sensor
  digitalWrite(sensorpowerPin, LOW);
  sensor_is_running = false;
  pinMode(buttonPin, INPUT);
  digitalWrite(buttonPin, HIGH); // connect internal pull-up
  button_was_pressed = false;
  button_pressed_counter = 0;
  
  Serial.begin(115200);             // we agree to talk fast!
  interruptSetup();                 // sets up to read Pulse Sensor signal every 2mS 
   // UN-COMMENT THE NEXT LINE IF YOU ARE POWERING The Pulse Sensor AT LOW VOLTAGE, 
   // AND APPLY THAT VOLTAGE TO THE A-REF PIN
   //analogReference(EXTERNAL);   
}



int handle_button()
{
  int event;
  int button_now_pressed = !digitalRead(buttonPin); // pin low -> pressed

  if (!button_now_pressed && button_was_pressed) {
    if (button_pressed_counter < longpress_len)
      event = EV_SHORTPRESS;
    else
      event = EV_LONGPRESS;
  }
  else
    event = EV_NONE;

  if (button_now_pressed)
    ++button_pressed_counter;
  else
    button_pressed_counter = 0;

  button_was_pressed = button_now_pressed;
  return event;
}



void loop(){
  if (sensor_is_running) {
    sendDataToProcessing('S', Signal);     // send Processing the raw Pulse Sensor data
    if (QS == true){                       // Quantified Self flag is true when arduino finds a heartbeat
          fadeRate = 255;                  // Set 'fadeRate' Variable to 255 to fade LED with pulse
          sendDataToProcessing('B',BPM);   // send heart rate with a 'B' prefix
          sendDataToProcessing('Q',IBI);   // send time between beats with a 'Q' prefix
          QS = false;                      // reset the Quantified Self flag for next time    
       }
    
    ledFadeToBeat();
  }
  
  boolean event = handle_button();
  if (event==EV_LONGPRESS) {  // toggle state of 
    if (sensor_is_running) {
      digitalWrite(sensorpowerPin, LOW);
      sensor_is_running = false;
    }
    else {
      digitalWrite(sensorpowerPin, HIGH);      
      sensor_is_running = true;
    }
  }
  
  delay(20);                             //  take a break
}


void ledFadeToBeat(){
    fadeRate -= 15;                         //  set LED fade value
    fadeRate = constrain(fadeRate,0,255);   //  keep LED fade value from going into negative numbers!
    analogWrite(fadePin,fadeRate);          //  fade LED
  }


void sendDataToProcessing(char symbol, int data ){
    Serial.print(symbol);                // symbol prefix tells Processing what type of data is coming
    Serial.println(data);                // the data to send culminating in a carriage return
  }








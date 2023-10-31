#define BLYNK_PRINT Serial
#define BLYNK_TEMPLATE_ID "TMPL6TYKNSw6S"
#define BLYNK_TEMPLATE_NAME "iot"
#define BLYNK_AUTH_TOKEN "B12tYldtWxLOf832hI2CmjYC8hB7QJFl"

#include <Servo.h>
#include <ESP8266WiFi.h>
#include <BlynkSimpleEsp8266.h>
char auth[] = BLYNK_AUTH_TOKEN;
char ssid[] = "FS040W_1988338";
char pass[] = "27956119";
int smokeA0 = A0;
int data = 0;
int sensorThres = 100;

BlynkTimer timer;

void sendSensor(){
 
 int data = analogRead(smokeA0);
 Blynk.virtualWrite(V1, data);
  Serial.print("Pin A0: ");
  Serial.println(data);


  if(data > 200)     // Change the Trashold value
  {
    //Blynk.email("paca0118@gmail.com", "kinki", "Gas Leakage Detected!");
    Blynk.logEvent("gas_alert","Gas Leakage Detected");
  }
}

Servo servo;

void setup()
{
   Serial.begin(9600);
  Blynk.begin(auth, ssid, pass);

  servo.attach(2); // nodemcu D4 pin
  servo.write(0); // move to 0•
  
 }
 void setup1(){
  pinMode(smokeA0, INPUT);
   Serial.begin(9600);
  Blynk.begin(auth, ssid, pass);
  //dht.begin();
  timer.setInterval(2500L, sendSensor);
}
  
void loop()
{
  
  Blynk.run();
}

void loop2()
{
  
  Blynk.run();
  timer.run();
}
BLYNK_WRITE(V2) // virtual pin 2 on blynk app
{
    int pinValue = param.asInt();
         if (pinValue == 1) //if button on
 { servo.write(60);// move servo to 58•
    }
           else // if button off
            
  servo.write(0); // move servo to 0•
}

#define BLYNK_PRINT Serial
#define BLYNK_TEMPLATE_ID "TMPL6TYKNSw6S"
#define BLYNK_TEMPLATE_NAME "iot"
#define BLYNK_AUTH_TOKEN "B12tYldtWxLOf832hI2CmjYC8hB7QJFl"


#include <WiFiClient.h>
#include <BlynkSimpleEsp32.h>

//#include <ESP8266WiFi.h>
//#include <BlynkSimpleEsp8266.h>

 
char auth[] = BLYNK_AUTH_TOKEN;
char ssid[] = "auhikari-iZzNzk-g";
char pass[] = "TMhVWwgjZwEm5";
 
int M1PWM = 33;
//int M2PWM = D6;
int M1F = 25; //GPIO5
int M1R = 26; //GPIO4
//int M2F = D3; //GPIO0
//int M2R = D4; //GPIO2

int pinValue1;
int pinValue2;

BLYNK_WRITE(V3)
{
  int pinValue1 = param.asInt();
  analogWrite(M1PWM,pinValue1);
  Blynk.virtualWrite(V3,pinValue1);
  Serial.print("V3 Slider Value is ");
  Serial.println(pinValue1);
}

BLYNK_WRITE(V4)
{
  int pinValue2 = param.asInt();
  analogWrite(M1PWM,pinValue2);
  Blynk.virtualWrite(V3,pinValue2);
  Serial.print("V4 Slider Value is ");
  Serial.println(pinValue2);
}
 

void setup(){
  pinMode(M1PWM, OUTPUT);
  //pinMode(M2PWM, OUTPUT);
  pinMode(M1F, OUTPUT);
  pinMode(M1R, OUTPUT);
  //pinMode(M2F, OUTPUT);
  //pinMode(M2R, OUTPUT);
  Serial.begin(9600);
  Blynk.begin(auth,ssid,pass);
  
}

void loop(){
  Blynk.run();
 
}
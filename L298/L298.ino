#define BLYNK_TEMPLATE_ID "TMPL6H_5FLP1m"
#define BLYNK_TEMPLATE_NAME "iot2"
#define BLYNK_AUTH_TOKEN "369IdGIIcev3MxvB97bb-kZHoQpS6Bla"

// Comment this out to disable prints and save space
#define BLYNK_PRINT Serial

#include <WiFi.h>
#include <WiFiClient.h>
#include <BlynkSimpleEsp32.h>

char auth[] = BLYNK_AUTH_TOKEN;

// Your WiFi credentials.
// Set password to "" for open networks.
char ssid[] = "auhikari-iZzNzk-g";
char pass[] = "TMhVWwgjZwEm5";

int IN1 = 4;
int IN2 = 5;



BLYNK_WRITE(V1) {   
  digitalWrite(IN2, param.asInt());
  
}

BLYNK_WRITE(V2) { 
  digitalWrite(IN1, param.asInt());
 
}

void setup()
{
  Serial.begin(9600);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);

  Blynk.begin(auth, ssid, pass, "blynk.cloud", 8080);

}

void loop()
{
  Blynk.run();

}


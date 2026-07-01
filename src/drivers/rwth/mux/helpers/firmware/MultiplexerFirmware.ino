#include "Arduino.h"
// NOTE: Vrekrer uses SCPI_ARRAY_SYZE (typo is in the library API)
#define SCPI_ARRAY_SYZE     150   // must be >= 97 for SETFULL
#define SCPI_MAX_TOKENS     600   // headroom for long commands / commas
#define SCPI_BUFFER_LENGTH  6000   // needs to fit full command string comfortably
#include "Vrekrer_scpi_parser.h"
#include "Wire.h"

#define I2CMUXADDR 0x70 // fixed address of 4 channel i2c multiplexer

uint8_t ShutDownPins[] = {54, 55, 56, 57, 58, 59, 2, 3, 4, 5, 6, 7}; // for IC1, IC2, ... IC12
uint8_t ICStatus[] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0}; // keeps track of which ICs are on/off, 0:OFF 1:ON

bool ShutDownChip(int chip);
// Function definition
bool ShutDownChip(int chip) {
  if (chip >= 1 && chip <= 12) {
    digitalWrite(ShutDownPins[chip - 1], LOW); // Active low shutdown
    ICStatus[chip - 1] = 0; // Update the status to OFF
    return true;
  } else {
    return false;
  }
}

SCPI_Parser my_instrument;

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; } // Wait for Serial to initialize

  my_instrument.RegisterCommand(F("*IDN?"), &Identify);
  my_instrument.RegisterCommand(F("*RST"), &Reset);

  my_instrument.SetCommandTreeBase(F("MUX"));
  my_instrument.RegisterCommand(F(":STATus?"), &GetStatus); // get status of individual connections
  my_instrument.RegisterCommand(F(":SWITch:ON"), &SetStatus); // switch on/off individual connections
  my_instrument.RegisterCommand(F(":SWITch:OFF"), &SetStatus);

  // get all inputs connected to one output
  my_instrument.RegisterCommand(F(":FULLstatus:OUTPut?"), &FullGetOutput);
  //usage MUX:FULLSTATUS:OUTPUT? Channel # (=1,2,3,4)

  // get all outputs connected to one input
  my_instrument.RegisterCommand(F(":FULLstatus:INPUt?"), &FullGetInput);
  //usage MUX:FULLSTATUS:INPUT? Input # (=1,2,...48,51,,98)

  // connect multiple inputs to one output
  my_instrument.RegisterCommand(F(":SETFull:OUTPut"), &FullSetOutput);
  my_instrument.RegisterCommand(F(":SBIT"), &SetBitsOutput); // faster and more stable than setfull command

  // connect multiple outputs to one input
  my_instrument.RegisterCommand(F(":SETFull:INPUt"), &FullSetInput);

  my_instrument.SetCommandTreeBase(F("DAC"));
  my_instrument.RegisterCommand(F(":SETV"), &SetDACVoltage);
  my_instrument.RegisterCommand(F(":GETV?"), &GetDACVoltage);

  my_instrument.SetCommandTreeBase(F("ADC"));
  my_instrument.RegisterCommand(F(":GETV?"), &GetADCVoltage);
  //  my_instrument.RegisterCommand(F(":AVERAGE?"), &GetADCVoltageAveraged);

  my_instrument.SetCommandTreeBase(F("LINEPROBE"));
  my_instrument.RegisterCommand(F(":RUN"), &LineProber);

  // define shutdown pins as digital output and turns off all MAX14661 chips
  for (int i = 1; i <= 12; i++) {
    pinMode(ShutDownPins[i - 1], OUTPUT);
    digitalWrite(ShutDownPins[i - 1], LOW); // active low shut down // turning all OFF initially
  }
  analogWriteResolution(12);  
  analogReadResolution(12);
//  pinMode(A1, INPUT);
  pinMode(A6, INPUT);
  Wire.begin(); // initiate Arduino as master on I2C bus
}

void loop()
{
  my_instrument.ProcessInput(Serial, "\n");
}

void Identify(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  interface.println(F("AG-BLUHM , Arduino Multiplexer v1.0 , 123, V 1.0"));
}

// open all switches by shutting down all ICs
void Reset(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  bool success = true;
  for (int i = 1; i <= 12; i++) {
    if (!ShutDownChip(i)) {
      success = false;
    }
    dynamicDelay(ShutDownPins[i - 1]); // delay to ensure hardware processing
  }
  //EnsureClearChipConnections();
  if (success) {
    interface.println(F("Multiplexer reset."));
  } else {
    interface.println(F("Multiplexer reset with errors."));
  }
}

void dynamicDelay(uint8_t pin) { 
  unsigned long startTime = millis(); 
  while (millis() - startTime < 200) { // Max delay of 200 ms 
  if (digitalRead(pin) == LOW) { // Check if the pin has gone low (shutdown complete) 
  break; } 
  delay(10); // Check every 10 ms 
  }
}

/**
void EnsureClearChipConnections(){
  for (int PIN =1; PIN <= 16; PIN++){
    PINtoM(PIN, 3, 0);
    delay(50);
    PINtoM(PIN, 4, 0);
    delay(50);
  }
}
*/

void GetStatus(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  if (parameters.Size() == 2) { // param1 is PIN, param2 is OUT
    uint8_t PIN = String(parameters[0]).toInt();
    uint8_t OUT = String(parameters[1]).toInt();

    int status = PINtoMStatus(PIN, OUT);
    interface.println(status); // connected:1, disconnected: 0, invalid input: 128, communication error: 255
  } else {
    interface.println("Usage: MUX:STAT? PIN, OUT");
  }
}

void SetStatus(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  if (parameters.Size() == 2) { // param1 is PIN, param2 is OUT
    uint8_t PIN = String(parameters[0]).toInt();
    uint8_t OUT = String(parameters[1]).toInt();

    String last_header = String(commands.Last());
    last_header.toUpperCase();

    if (last_header.compareTo("ON") == 0) {
      interface.println(PINtoM(PIN, OUT, 1)); // successful:0 , not successful otherwise
    } else if (last_header.compareTo("OFF") == 0) {
      interface.println(PINtoM(PIN, OUT, 0));
    } else {
      interface.println("Usage: MUX:SWITCH:ON/OFF PIN, OUT");
    }
  } else {
    interface.println("Usage: MUX:SWITCH:ON/OFF PIN, OUT");
  }
}

void FullGetOutput(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  uint8_t OUT = String(parameters[0]).toInt();
  String channel_status = "";
  for (int PIN = 1; PIN <= 48; PIN++) {
    channel_status = channel_status + PINtoMStatus(PIN, OUT) + ", ";
  }

  for (int PIN = 51; PIN <= 98; PIN++) {
    channel_status = channel_status + PINtoMStatus(PIN, OUT) + ", ";
  }

  interface.println(channel_status);
}

void FullSetOutput(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  int OUT = String(parameters[0]).toInt();
  if (parameters.Size() == 97) {
    for (int PIN = 1; PIN <= 48; PIN++) {
      PINtoM((uint8_t)PIN, (uint8_t)OUT, (uint8_t)String(parameters[PIN]).toInt());
      delay(5); // Adding delay between each command
    }

    for (int PIN = 51; PIN <= 98; PIN++) {
      PINtoM(PIN, OUT,  String(parameters[PIN - 2]).toInt());
      delay(5); // Adding delay between each command
    }
    //interface.println("OK");
  } else {
    interface.println("Usage: MUX::SETFull:OUTPut OUT, PIN1_status(=0/1), PIN2_status, ... PIN48_status, PIN51_status, ... PIN98_status");
  }
}

void SetBitsOutput(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  if (parameters.Size() != 2) {
    interface.println("ERR:PARAMS");
    return;
  }

  int OUT = String(parameters[0]).toInt();
  String bits = String(parameters[1]);
  bits.trim();

  if (bits.length() != 96) {
    interface.println("ERR:BITLEN");
    return;
  }

  for (int i = 0; i < 96; i++) {
    if (bits[i] != '0' && bits[i] != '1') {
      interface.println("ERR:BITCHAR");
      return;
    }
  }

  for (int i = 0; i < 48; i++) {
    uint8_t PIN = i + 1;
    uint8_t target = (bits[i] == '1') ? 1 : 0;
    if (PINtoMStatus(PIN, OUT) != target) {
      PINtoM(PIN, OUT, target);
      delay(1);
    }
  }

  for (int i = 48; i < 96; i++) {
    uint8_t PIN = 51 + (i - 48);
    uint8_t target = (bits[i] == '1') ? 1 : 0;
    if (PINtoMStatus(PIN, OUT) != target) {
      PINtoM(PIN, OUT, target);
      delay(1);
    }
  }

  interface.println("OK");
  interface.flush();

}

void FullGetInput(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  uint8_t PIN = String(parameters[0]).toInt();
  String channel_status = "";
  for (int OUT = 1; OUT <= 4; OUT++) {
    channel_status = channel_status + PINtoMStatus(PIN, OUT) + ", ";
  }

  interface.println(channel_status);
}

void FullSetInput(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  uint8_t PIN = String(parameters[0]).toInt();
  if (parameters.Size() == 5) {
    for (int OUT = 1; OUT <= 4; OUT++) {
      PINtoM(PIN, OUT, String(parameters[OUT]).toInt());
      delay(100); // Adding delay between each command
    }
  } else {
    interface.println("Usage: MUX::SETFull:INPUt PIN, OUT1_status(=0/1), OUT2_status, OUT3_status, OUT4_status ");
  }
}

void SetDACVoltage(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  if (parameters.Size() == 1) {
    float voltage = String(parameters[0]).toFloat();
    if (voltage < 0.55 || voltage > 2.75) {
      interface.println("0.55V < voltage < 2.75V");
    } else {
      interface.println(SetDAC(voltage));
    }
  } else {
    interface.println("Usage: DAC:SETV Voltage");
  }
}

void GetDACVoltage(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  if (parameters.Size() == 0) {
    interface.println(GetDAC());
  } else {
    interface.println("Usage: DAC:GETV");
  }
}

void GetADCVoltage(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  if (parameters.Size() == 0) {
    interface.println(GetADC());
  } else {
    interface.println("Usage: ADC:GETV?");
  }
}

void LineProber(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  // usage GND, V_DAC ,R_fix
  uint8_t GND = String(parameters[0]).toInt(); // OUT channel with ground cap

  SetDAC(String(parameters[1]).toFloat());

  float R_fix = String(parameters[2]).toFloat();

  int Samples = 1000; // for averaging ADC readout

  String inter_line_resistance = "";
  // iterate over all inputs
  //  for (int PIN = 1; PIN <= 98; PIN++)
  for (int PIN = 1; PIN <= 2; PIN++) {
    // open circuit voltage
    // measure voltage at probe wrt ground
    float sum = 0;
    for (int i = 0; i < Samples; i++) sum += GetADC();
    float V_DAC = sum / (float) Samples;

    interface.println(PIN);
    interface.println(V_DAC);

    // connect input terminal to gnd to measure resistance between pin and probe
    PINtoM(PIN, GND, 1);

    sum = 0;
    for (int i = 0; i < Samples; i++) sum += GetADC();

    float V_ADC = sum / (float) Samples;

    interface.println(V_ADC);

    PINtoM(PIN, GND, 0);

    float rounded_V_ADC = V_ADC; //roundtoN(V_ADC, 2);

    // calculate resistance based on measurements
    float R =  R_fix / (V_DAC / rounded_V_ADC - 1);

    if (R > 100000) R = 100000000; // fixed value for open circuit
    if (R < 0) R = 100000000; // fixed value for open circuit, R < 0 happens in open circuit case sometimes due to finite precision of ADC/DAC

    // only report back for valid pins
    if (PIN != 49 &&  PIN != 50)  inter_line_resistance = inter_line_resistance + R + ", ";
  }
  // report back as string of 96 resistances
  interface.println(inter_line_resistance);
}

void GetADCVoltageAveraged(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  if (parameters.Size() == 1) {
    int samples = String(parameters[0]).toInt();
    float sum = 0;
    for (int i = 0; i < samples; i++) {
      sum +=   GetADC();
    }
    float voltage = sum / float(samples);
    interface.println(voltage);
  } else {
    interface.println("Usage: ADC:AVERAGE? N_samples");
  }
}

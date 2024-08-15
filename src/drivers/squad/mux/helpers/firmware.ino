#include "Arduino.h"
#include "Vrekrer_scpi_parser.h"
#include "AD75019_24.h"
#include "AD75019.h"

// Pin definitions for AD75019 control lines (shared)
const uint8_t pclkPin = 52;
const uint8_t sclkPin = 21;
const uint8_t sinPin = 20;

// Instantiate objects for both matrices
AD75019_24 cpSwitch32(pclkPin, sclkPin, sinPin); // 32x32 matrix
AD75019 cpSwitch16(pclkPin, sclkPin, sinPin);    // 16x16 matrix

// SCPI Parser instance
SCPI_Parser my_instrument;

void setup() {
    Serial.begin(9600);

    // Initialize the 16x16 matrix
    if (!cpSwitch16.begin()) {
        Serial.println("16x16 init failed");
        while (1);
    }

    // Initialize the 32x32 matrix
    if (!cpSwitch32.begin()) {
        Serial.println("32x32 init failed");
        while (1);
    }

    // Register SCPI commands
    my_instrument.RegisterCommand(F("*IDN?"), &Identify);
    my_instrument.RegisterCommand(F("*RST"), &Reset);
    my_instrument.RegisterCommand(F("STAT?"), &GetStatus);
    my_instrument.RegisterCommand(F("SWITCH16"), &Switch16);
    my_instrument.RegisterCommand(F("SWITCH32"), &Switch32);
    my_instrument.RegisterCommand(F("CLEAR"), &Clear);
    my_instrument.RegisterCommand(F("PRINT"), &Print);
}

void loop() {
    my_instrument.ProcessInput(Serial, "\n");
}

void Identify(SCPI_C commands, SCPI_P parameters, Stream& interface) {
    interface.println("SQUAD, Arduino AD75019 Switch, 1.0, 1.0");
}

void Reset(SCPI_C commands, SCPI_P parameters, Stream& interface) {
    Clear(commands, parameters, interface);
    cpSwitch16.flush();
    cpSwitch32.flush();
    interface.println("Reset complete");
}

void Switch16(SCPI_C commands, SCPI_P parameters, Stream& interface) {
    if (parameters.Size() == 2) {
        uint8_t x = String(parameters[0]).toInt();
        uint8_t y = String(parameters[1]).toInt();

        cpSwitch16.addRoute(x, y);
        cpSwitch16.flush();
        interface.println("Route added 16x16");
    } else {
        interface.println("Usage: SWITCH16 x,y");
    }
}

void Switch32(SCPI_C commands, SCPI_P parameters, Stream& interface) {
    if (parameters.Size() == 2) {
        uint8_t x = String(parameters[0]).toInt();
        uint8_t y = String(parameters[1]).toInt();

        // Check if the route is within the disabled range
        if ((x >= 12 && x < 16) || (y >= 12 && y < 16) || (x >= 28 && x < 32) || (y >= 28 && y < 32)) {
            interface.println("Route skipped: disabled range");
            return;
        }

        cpSwitch32.addRoute(x, y);
        cpSwitch32.flush();
        interface.println("Route added 32x32");
    } else {
        interface.println("Usage: SWITCH32 x,y");
    }
}

void GetStatus(SCPI_C commands, SCPI_P parameters, Stream& interface) {
    if (parameters.Size() == 2) {
        uint8_t x = String(parameters[0]).toInt();
        uint8_t y = String(parameters[1]).toInt();

        bool isConnected16 = cpSwitch16.isRouted(x, y);
        bool isConnected32 = cpSwitch32.isRouted(x, y);

        interface.print("16x16: ");
        interface.println(isConnected16 ? "1" : "0");

        interface.print("32x32: ");
        interface.println(isConnected32 ? "1" : "0");
    } else {
        interface.println("Usage: STAT? x,y");
    }
}

void Clear(SCPI_C commands, SCPI_P parameters, Stream& interface) {
    cpSwitch16.clear();
    cpSwitch32.clear();
    interface.println("Clear complete");
}

void Print(SCPI_C commands, SCPI_P parameters, Stream& interface) {
    interface.println("16x16 Config:");
    cpSwitch16.print();

    interface.println("32x32 Config:");
    cpSwitch32.print();
}

#include "AD75019_24.h"

void setup() {
    Serial.begin(9600);
    while (!Serial);

    AD75019_24 cpSwitch(52, 21, 20);

    // Initialize the AD75019
    if (!cpSwitch.begin()) {
        Serial.println("AD75019 initialization failed");
        while (1);
    }

    // Configure all routes (close all switches)
    for (uint8_t row = 0; row < 32; ++row) {
        for (uint8_t col = 0; col < 32; ++col) {
            /**
            // Skip the disabled bits (rows 12-15 and columns 12-15 on each chip)
            if ((row % 16) >= 12 || (col % 16) >= 12) {
                continue;
            }
            */
            cpSwitch.addRoute(col, row);
        }
    }

    // Send the route configuration to the AD75019
    cpSwitch.flush();

    cpSwitch.print();
}

void loop() {
    // Main loop
}

/*
  AD75019.cpp for 24*24 switching array 

  where 4 inputs and 4 outputs have been disabled (set to constant 0)
  analogue inputs and outputs are daisy chained
  SIN and SOUT adapted cascading method (the SOUT output is the end of shift register, 
  which is directly connected to the SIN of the next chip)

  Library for the Analog Devices AD75019 Crosspoint Switch

  Copyright (c) 2024, Dan Mowehhuk (danmowehhuk@gmail.com)
  All rights reserved.
*/

#include <Arduino.h>
#include "AD75019.h"

void _ad75019_pinModeDefault(uint8_t pinNumber, uint8_t /* unused */) {
    pinMode(pinNumber, OUTPUT);
}

void _ad75019_digitalWriteDefault(uint8_t pinNumber, uint8_t value) {
    digitalWrite(pinNumber, value);
}

AD75019::AD75019(uint8_t pclkPinNumber, uint8_t sclkPinNumber, uint8_t sinPinNumber) :
    _pclkPinNumber(pclkPinNumber), _sclkPinNumber(sclkPinNumber), _sinPinNumber(sinPinNumber),
    _pinModeCallback(_ad75019_pinModeDefault), _digitalWriteCallback(_ad75019_digitalWriteDefault) {
    setUseDefaultCallbacks(true);
}

AD75019::AD75019(uint8_t pclkPinNumber, uint8_t sclkPinNumber, uint8_t sinPinNumber,
                 voidFuncCallback_t pinModeCallback, voidFuncCallback_t digitalWriteCallback) :
    _pclkPinNumber(pclkPinNumber), _sclkPinNumber(sclkPinNumber), _sinPinNumber(sinPinNumber),
    _pinModeCallback(pinModeCallback), _digitalWriteCallback(digitalWriteCallback) {}

bool AD75019::begin() {
    _pinModeCallback(_pclkPinNumber, OUTPUT);
    _pinModeCallback(_sclkPinNumber, OUTPUT);
    _pinModeCallback(_sinPinNumber, OUTPUT);
    _digitalWriteCallback(_pclkPinNumber, HIGH);
    _digitalWriteCallback(_sclkPinNumber, LOW);
    _digitalWriteCallback(_sinPinNumber, LOW);
    setBegun(true);
    return true;
}

bool AD75019::begin(uint8_t xPinMapping[16], uint8_t yPinMapping[16]) {
    uint16_t used = 0;
    for (uint8_t i = 0; i < 16; i++) {
        if (xPinMapping[i] > 15 || bitRead(used, xPinMapping[i])) {
            return false;
        } else {
            _xPinMapping[i] = xPinMapping[i];
            bitWrite(used, xPinMapping[i], 1);
        }
    }

    used = 0;
    for (uint8_t i = 0; i < 16; i++) {
        if (yPinMapping[i] > 15 || bitRead(used, yPinMapping[i])) {
            return false;
        } else {
            _yPinMapping[i] = yPinMapping[i];
            bitWrite(used, yPinMapping[i], 1);
        }
    }

    return begin();
}

void AD75019::addRoute(uint8_t x, uint8_t y) {
    int byteIndex, bitIndex;
    globalToBitIndex(y, x, byteIndex, bitIndex); 
    bitWrite(_configBuffer[byteIndex], bitIndex, 1);
}

bool AD75019::isRouted(uint8_t x, uint8_t y) {
    int byteIndex, bitIndex;
    globalToBitIndex(y, x, byteIndex, bitIndex); 
    return bitRead(_configBuffer[byteIndex], bitIndex);
}

void AD75019::globalToBitIndex(int globalRow, int globalCol, int &byteIndex, int &bitIndex) {
    int localRow = globalRow % 16;
    int localCol = globalCol % 16;
    int chipID = (globalRow / 16) * 2 + (globalCol / 16);
    int chipOffset = chipID * 256;
    int bitPosition = (localRow * 16 + localCol);
    byteIndex = (chipOffset + bitPosition) / 8;
    bitIndex = (chipOffset + bitPosition) % 8;
}

void AD75019::clearDisabledBits() {
    for (int chip = 0; chip < 4; chip++) {
        for (int i = 12; i < 16; i++) {
            for (int j = 0; j < 16; j++) {
                int bitPosition = chip * 256 + i * 16 + j;
                int byteIndex = bitPosition / 8;
                int bitIndex = bitPosition % 8;
                bitWrite(_configBuffer[byteIndex], bitIndex, 0);
            }
        }
        for (int i = 0; i < 16; i++) {
            for (int j = 12; j < 16; j++) {
                int bitPosition = chip * 256 + i * 16 + j;
                int byteIndex = bitPosition / 8;
                int bitIndex = bitPosition % 8;
                bitWrite(_configBuffer[byteIndex], bitIndex, 0);
            }
        }
    }
}

void AD75019::flush() {
    if (!isBegun()) return;

    clearDisabledBits();


//Initialisation, better kept this 
    _digitalWriteCallback(_sinPinNumber, LOW);
    for (int i = 0; i < 256 * 4; i++) {
        _digitalWriteCallback(_sclkPinNumber, HIGH);
        _digitalWriteCallback(_sclkPinNumber, HIGH);
        _digitalWriteCallback(_sclkPinNumber, LOW);
        _digitalWriteCallback(_sclkPinNumber, LOW);
    }

    _digitalWriteCallback(_pclkPinNumber, LOW);
    _digitalWriteCallback(_pclkPinNumber, HIGH);
    

// Uploading data
    for (int i = 0; i < 128; i++) { // 128 bytes = 1024 bits
        for (int bit = 7; bit >= 0; bit--) {
            bool bitValue = bitRead(_configBuffer[i], bit);
            _digitalWriteCallback(_sinPinNumber, bitValue);
            _digitalWriteCallback(_sclkPinNumber, HIGH);
            _digitalWriteCallback(_sclkPinNumber, HIGH);
            _digitalWriteCallback(_sclkPinNumber, LOW);
        }
    }

    _digitalWriteCallback(_pclkPinNumber, LOW);
    _digitalWriteCallback(_pclkPinNumber, HIGH);
}

void AD75019::clear() {
    for (uint8_t i = 0; i < 128; i++) {
        _configBuffer[i] = 0;
    }
}

void AD75019::print() {
    if (!isBegun()) {
        Serial.println(F("AD75019 not initialized!"));
        return;
    }
    Serial.println(F("  X: 1098 7654 3210 9876 5432 1098 7654 3210"));
    for (int8_t y = 31; y >= 0; y--) {
        if (y > 9) {
            Serial.print(F("Y"));
            Serial.print(y);
            Serial.print(F(": "));
        } else {
            Serial.print(F(" Y"));
            Serial.print(y);
            Serial.print(F(": "));
        }
        for (int8_t x = 31; x >= 0; x--) {
            int byteIndex, bitIndex;
            globalToBitIndex(y, x, byteIndex, bitIndex);
            Serial.print(bitRead(_configBuffer[byteIndex], bitIndex));
            if (x % 4 == 0) {
                Serial.print(F(" "));
            }
        }
        Serial.println();
    }
}

void AD75019::setBegun(bool b) {
    bitWrite(_state, 1, b);
}

bool AD75019::isBegun() {
    return bitRead(_state, 1);
}

void AD75019::setUseDefaultCallbacks(bool b) {
    bitWrite(_state, 0, b);
}

bool AD75019::isUseDefaultCallbacks() {
    return bitRead(_state, 0);
}

#include <Arduino.h>
#include "AD75019_24.h"

// Default pinMode and digitalWrite functions
void _ad75019_24_pinModeDefault(uint8_t pinNumber, uint8_t /* unused */) {
  pinMode(pinNumber, OUTPUT);
}

// Optimized digitalWriteCallback using direct register access on ARM
//Direct manipulation of the registers is much faster than using a higher-level function like digitalWrite().
//This is because it eliminates the overhead of additional checks and abstractions.
void _ad75019_24_digitalWriteCallback(uint8_t pinNumber, uint8_t value) {//value = HIGH/LOW
  //Pio is a port on the microcontroller, Pio* is a pointer to this port
  //g_APinDescription is an array that holds info of each pin on Arduino board
  //pPort is a pointer to the port that controls the pin
  Pio* port = g_APinDescription[pinNumber].pPort;
  //ulPin is the bitmask for the pin
  //Each pin in a port corresponds to a specific bit in the port's register,
  //i.e.  if a pin corresponds to the third bit in the register, ulPin would be 0b00000000000000000000000000000100
  uint32_t pinMask = g_APinDescription[pinNumber].ulPin;

  if (value == HIGH) {
    port->PIO_SODR = pinMask; // PIO_SODR (Set Output Data Register)
                              // = pinMask, specific bit corresponding to the pin will be set to 1
  } else {
    port->PIO_CODR = pinMask; // PIO_CODR (Clear Output Data Register)
                              // = pinMaks, specific bit corresponding to the pin will be set to 0
  }
}

// Constructor using default callbacks
AD75019_24::AD75019_24(uint8_t pclkPinNumber, uint8_t sclkPinNumber, uint8_t sinPinNumber)
  : _pclkPinNumber(pclkPinNumber), _sclkPinNumber(sclkPinNumber), _sinPinNumber(sinPinNumber),
    _pinModeCallback(_ad75019_24_pinModeDefault), _digitalWriteCallback(_ad75019_24_digitalWriteCallback) {
    setUseDefaultCallbacks(true);
}

// Constructor with custom callbacks
AD75019_24::AD75019_24(uint8_t pclkPinNumber, uint8_t sclkPinNumber, uint8_t sinPinNumber,
          void (*pinModeCallback)(uint8_t, uint8_t), void (*digitalWriteCallback)(uint8_t, uint8_t))
  : _pclkPinNumber(pclkPinNumber), _sclkPinNumber(sclkPinNumber), _sinPinNumber(sinPinNumber),
    _pinModeCallback(pinModeCallback), _digitalWriteCallback(digitalWriteCallback) {}

bool AD75019_24::begin() {
    _pinModeCallback(_pclkPinNumber, OUTPUT);
    _pinModeCallback(_sclkPinNumber, OUTPUT);
    _pinModeCallback(_sinPinNumber, OUTPUT);

    _digitalWriteCallback(_pclkPinNumber, HIGH);
    _digitalWriteCallback(_sclkPinNumber, LOW);
    _digitalWriteCallback(_sinPinNumber, LOW);

    setBegun(true);
    return true;
}

bool AD75019_24::begin(uint8_t xPinMapping[32], uint8_t yPinMapping[32]) {
  // Validate pin mapping arrays
  uint32_t used = 0;
  for (uint8_t i = 0; i < 32; i++) {
    if (xPinMapping[i] > 31 || bitRead(used, xPinMapping[i])) {
      return false;
    } else {
      _xPinMapping[i] = xPinMapping[i];
      bitWrite(used, xPinMapping[i], 1);
    }
  }

  used = 0;
  for (uint8_t i = 0; i < 32; i++) {
    if (yPinMapping[i] > 31 || bitRead(used, yPinMapping[i])) {
      return false;
    } else {
      _yPinMapping[i] = yPinMapping[i];
      bitWrite(used, yPinMapping[i], 1);
    }
  }
  return begin();
}

void AD75019_24::addRoute(uint8_t x, uint8_t y) {
    // Proceed with adding the route if it's not within the excluded ranges
    bitWrite(_configBuffer[_yPinMapping[y]], _xPinMapping[x], 1);
}


void AD75019_24::removeRoute(uint8_t x, uint8_t y) {
    bitWrite(_configBuffer[_yPinMapping[y]], _xPinMapping[x], 0);
}

bool AD75019_24::isRouted(uint8_t x, uint8_t y) {
  return bitRead(_configBuffer[_yPinMapping[y]], _xPinMapping[x]);
}

void AD75019_24::flush() {
	if (!isBegun()) return;
   /**
  for (int8_t y = 31; y > -1; y--) {
    for (int8_t x = 31; x > -1; x--) {
      _digitalWriteCallback(_sclkPinNumber, HIGH);
      _digitalWriteCallback(_sclkPinNumber, LOW);
    }
  }
*/
  for (int8_t y = 31; y > 15; y--) {
      for (int8_t x = 31; x > 15; x--) {
        _digitalWriteCallback(_sinPinNumber,
          bitRead(_configBuffer[y], x));
        _digitalWriteCallback(_sclkPinNumber, HIGH);
        _digitalWriteCallback(_sclkPinNumber, LOW);
      }
    }

  for (int8_t y = 31; y > 15; y--) {
    for (int8_t x = 15; x > -1; x--) {
      _digitalWriteCallback(_sinPinNumber,
        bitRead(_configBuffer[y], x));
      _digitalWriteCallback(_sclkPinNumber, HIGH);
      _digitalWriteCallback(_sclkPinNumber, LOW);
    }
  }

  for (int8_t y = 15; y > -1; y--) {
      for (int8_t x = 31; x > 15; x--) {
        _digitalWriteCallback(_sinPinNumber,
          bitRead(_configBuffer[y], x));
        _digitalWriteCallback(_sclkPinNumber, HIGH);
        _digitalWriteCallback(_sclkPinNumber, LOW);
      }
    }

  for (int8_t y = 15; y > -1; y--) {
    for (int8_t x = 15; x > -1; x--) {
      _digitalWriteCallback(_sinPinNumber,
        bitRead(_configBuffer[y], x));
      _digitalWriteCallback(_sclkPinNumber, HIGH);
      _digitalWriteCallback(_sclkPinNumber, LOW);
    }
  }
  _digitalWriteCallback(_pclkPinNumber, LOW);
  _digitalWriteCallback(_pclkPinNumber, HIGH);
}


// Clear all routes
void AD75019_24::clear() {
  for (uint8_t i = 0; i < 32; i++) { // Adjusted for 32x32
    _configBuffer[i] = 0;
  }
}

void AD75019_24::print() {
    if (!isBegun()) {
        Serial.println(F("AD75019 not initialized!"));
        return;
    }

    Serial.println(F("  X: `1098 7654 3210 9876 5432 1098 7654 3210"));
    for (int8_t y = 31; y > -1; y--) {
        if (y > 9) {
            Serial.print(F("Y"));
            Serial.print(y);
            Serial.print(F(": "));
        } else {
            Serial.print(F(" Y"));
            Serial.print(y);
            Serial.print(F(": "));
        }
        for (int8_t x = 31; x > -1; x--) {
            Serial.print(bitRead(_configBuffer[y], x));
            if (x % 4 == 0) {
                Serial.print(F(" "));
            }
        }
        Serial.println();
    }
}

void AD75019_24::setBegun(bool b) {
    bitWrite(_state, 1, b);
}

bool AD75019_24::isBegun() {
    return bitRead(_state, 1);
}

void AD75019_24::setUseDefaultCallbacks(bool b) {
    bitWrite(_state, 0, b);
}

bool AD75019_24::isUseDefaultCallbacks() {
    return bitRead(_state, 0);
}

/*
  AD75019.h

  Library for the Analog Devices AD75019 Crosspoint Switch

  Copyright (c) 2024, Dan Mowehhuk (danmowehhuk@gmail.com)
  All rights reserved.
*/

#ifndef AD75019_h
#define AD75019_h

#include <stdint.h>

class AD75019 {

public:
    AD75019(uint8_t pclkPinNumber, uint8_t sclkPinNumber, uint8_t sinPinNumber);

    typedef void (*voidFuncCallback_t)(uint8_t i, uint8_t v);
    AD75019(uint8_t pclkPinNumber, uint8_t sclkPinNumber, uint8_t sinPinNumber, 
            voidFuncCallback_t pinModeCallback, voidFuncCallback_t digitalWriteCallback);

    bool begin();
    bool begin(uint8_t xPinMapping[16], uint8_t yPinMapping[16]);

    void addRoute(uint8_t x, uint8_t y);
    bool isRouted(uint8_t x, uint8_t y);
    void flush();
    void clear();
    void print();

private:
    AD75019();
    AD75019(AD75019 &t);

    void setBegun(bool b);
    bool isBegun();
    void setUseDefaultCallbacks(bool b);
    bool isUseDefaultCallbacks();

    void globalToBitIndex(int globalRow, int globalCol, int &byteIndex, int &bitIndex);
    void clearDisabledBits();

    uint8_t _pclkPinNumber;
    uint8_t _sclkPinNumber;
    uint8_t _sinPinNumber;

    uint8_t _state = 0;

    voidFuncCallback_t _pinModeCallback = NULL;
    voidFuncCallback_t _digitalWriteCallback = NULL;
    
    uint8_t _xPinMapping[16] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};
    uint8_t _yPinMapping[16] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};

    uint8_t _configBuffer[128] = {0};  // 128 bytes = 1024 bits for 32x32 matrix
};

#endif // AD75019_h

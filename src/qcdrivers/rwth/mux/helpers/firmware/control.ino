// Control and switching functions

uint8_t PINtoM(uint8_t PIN, uint8_t M, uint8_t state) {
  byte val = 0; // value sent back to python interface and returned here, 0 if everything is OK, 128 if invalid pin/output number given, otherwise problems with I2C communication

  if (  ((PIN >= 1 && PIN <= 48) || (PIN >= 51 && PIN <= 98) ) && (M >= 1 && M <= 4) && (state == 0 || state == 1)) {

    uint8_t ICNum = ICNumber(PIN, M); //1,2,3...12
    uint8_t ICADDR = ICtoAddress(ICNum);
    uint8_t REGISTER = WhichRegister(PIN, M);

    if (ICStatus[ICNum - 1] == 0)  ActivateChip(ICNum); // if IC is off, switch it on

    val += ChannelSelect(ICtoChannel(ICNumber(PIN, M))); // select required I2C bus channel

    Wire.beginTransmission(ICADDR); // start communication with concerned MUX IC
    Wire.write(REGISTER); // pick concerned internal register of IC
    val += Wire.endTransmission();

    Wire.requestFrom((uint8_t)ICADDR, (uint8_t)1);
    uint8_t currentdata = Wire.read(); // get current data stored in the register 

    Wire.beginTransmission(ICADDR); // start communication with concerned IC
    Wire.write(REGISTER); // pick concerned internal register of IC

    if (state == 1) { // switch on
      Wire.write(currentdata | DirectRegisterData(PINtoABxx(PIN)));
      val += Wire.endTransmission();
    }
    else if (state == 0) { // switch off
      Wire.write(currentdata & ~DirectRegisterData(PINtoABxx(PIN)));   // bitwise flip the data and and it bitwise with current byte stored in the register
      val += Wire.endTransmission();
      bool IC_Idle = isIdle(ICNum);
      if (IC_Idle) ShutDownChip(ICNum); // if the ic d/n serve any purpose, switch it off
    }
  }
  else {
    val = 128; // indicates invalid PIN/OUT number
  }

  return val;
}

uint8_t PINtoMStatus(uint8_t PIN, uint8_t M) {
  byte val = 0; // to keep track of I2C communication status
  uint8_t connection = 0; // data sent back to python and returned here, 0:off, 1:on, 128: invalid PIN/M, 255: failed I2C communication

  if (  ((PIN >= 1 && PIN <= 48) || (PIN >= 51 && PIN <= 98) ) && (M >= 1 && M <= 4)) { // valid inputs

    uint8_t ICNum = ICNumber(PIN, M); //1,2,3...12
    uint8_t ICADDR = ICtoAddress(ICNumber(PIN, M));
    uint8_t REGISTER = WhichRegister(PIN, M);

    if (ICStatus[ICNum - 1] == 0)  return 0;  // if IC is off  , ALL switches are off

    val += ChannelSelect(ICtoChannel(ICNumber(PIN, M))); // select required I2C bus channel

    Wire.beginTransmission(ICADDR); // start communication with concerned MUX IC
    Wire.write(REGISTER); // pick concerned internal register of IC
    val += Wire.endTransmission();

    Wire.requestFrom((uint8_t)ICADDR, (uint8_t)1);
    uint8_t currentdata = Wire.read(); // get current data stored in the register 

    if (val != 0)  connection = 255; // failed I2C communication somewhere above
    else { // successful I2C communication
      // direct register data is just a byte with all 0s except for a 1 at location corresponding to PIN
      // if we bitwise and it with current data of the register we get zero if the connection is off and non-zero number if it is on
      if ((currentdata & DirectRegisterData(PINtoABxx(PIN))) == 0)  connection = 0;
      else connection = 1;
    }
  } else {
    connection = 128; // indicates invalid PIN/OUT number
  }

  return connection;
}
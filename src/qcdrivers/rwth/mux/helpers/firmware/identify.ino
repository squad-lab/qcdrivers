
//identifier_func
/**
  This sketch contains miscellaneous functions used to identify various hardware connections on the board


*/

/**
  Selects 1 of 4 available I2C buses via the PCA9544 I2C multiplexer
  Allowed channel numbers 0,1,2,3
  Channel 3 is unused on the actual board
*/
// Define the I2C address of the multiplexer


#define I2CMUXADDR 0x70 

uint8_t ChannelSelect(uint8_t channel) {
 if (channel > 3) return 127; // illegal channel number, allowed channel number are 0,1,2,3

 Wire.beginTransmission(I2CMUXADDR); // start communicating with I2C multiplexer slave
 Wire.write((uint8_t)(0x04 + channel));// select the I2C channel 
 return Wire.endTransmission();
}


/**
  Disables all channels of the I2C multiplexer
*/

void NoChannelSelect() {
 Wire.beginTransmission(I2CMUXADDR);
 Wire.write(0);
 Wire.endTransmission();
}


/**
  Shuts down MAX14661 chip number N (1 to 12) on the board via active low SD pin
*/

void ShutDownChip(uint8_t N) {
 digitalWrite(ShutDownPins[N - 1], LOW); // active low shut down
 ICStatus[N - 1] = 0;
}


/**
  Activates MAX14661 chip number N (1 to 12) on the board via active low SD pin
*/

void ActivateChip(uint8_t N) {
 digitalWrite(ShutDownPins[N - 1], HIGH);
 ICStatus[N - 1] = 1;
}


/**
  Turn off all MAX14661 chips and make I2C multiplexer idle
*/

void GlobalReset() {
 NoChannelSelect();
 for (int i = 1; i <= 12; i++) ShutDownChip(i - 1);
}


/**
   Identifies the multiplexer # (1-6) to which a pin is connected to
*/

int MultiplexerNumber(uint8_t PIN) {
 if (PIN >= 1 && PIN <= 48) {
   return ceil(PIN / 16.0); // i.e. ceil(5/16) = ceil(0.3125) = 1 (Pin 5 is on cip 1 ) 
 }
 else if (PIN >= 51 && PIN <= 98) {
   return 6 - (ceil((PIN - 2) / 16.0) - 4); // i.e. pin 52 would be on chip 6 
 }
}


/**
  Identifies sub IC 1 or 2 correspoding to common output M
*/
int subICNumber(uint8_t M) {
 if (M == 1 || M == 2) return 1;
 else if (M == 3 || M == 4) return 2;
}


/**
  Identifies IC 1 to 12 correspoding to input pin N and common output M
*/
int ICNumber(uint8_t N, uint8_t M) {
 if (subICNumber(M) == 2) return MultiplexerNumber(N) * 2;
 else if (subICNumber(M) == 1) return MultiplexerNumber(N) * 2 - 1;
}


/**
  Returns I2C channel number on which the IC k is
*/
int ICtoChannel(int k) {
 return 3.0 - ceil(k / 4.0); // somehow works
}


/**
  Returns 7bit address of IC k
*/
int ICtoAddress(int k) {
 return 0x4F - (4 - k % 4) % 4; // somehow works
}


/**
  Tells which input pin ABxx a pin is connected to on its respective chip
  Returns xx
*/
int PINtoABxx(uint8_t PIN) {
 int MUX = MultiplexerNumber(PIN);
 if (MUX >= 1 && MUX <= 3)
 {
   return  ( PIN % 16 == 0) ? 16 : PIN % 16;
 } else if (MUX >= 4 && MUX <= 6) {
   PIN = PIN - 2;
   int temp = PIN % 16;
   if (temp == 0) return 9;
   else if (temp >= 1 && temp <= 8) return temp;
   else return (16 - temp) + 9;
 } 
}


/**
  Returns address of DIR x register that needs to be addressed to connect PIN to M
*/
int WhichRegister(uint8_t PIN, uint8_t M) {
 int ABxx = PINtoABxx(PIN);
 if (M == 1 || M == 3) return (ABxx <= 8) ? 0x00 : 0x01; // address of DIR 0 and DIR 1 registers respectively for A connections
 else if (M == 2 || M == 4) return (ABxx <= 8) ? 0x02 : 0x03; // DIR 2 and DIR 3 registers for B connections
}


/**
  Returns the value that needs to be written to concerned direct register to ONLY connect ABxx to output
*/
int DirectRegisterData(uint8_t ABxx) {
 return ABxx % 8 == 0 ? 1 << 7 : 1 << (ABxx % 8 - 1);
}


/**
  returns true if all switches on an ICNum are open
  NOTE: this doesn't tell if an IC is on or OFF, that info is contained in ICStatus global array
         infact the IC needs to be ON for this query
*/


bool isIdle(int ICNum) {

 bool IC_idle = true; // assumes by default all switch open
 uint8_t ICADDR = ICtoAddress(ICNum);
 uint8_t val = 0; // to track I2C communication failure, this is not returned back yet,  return structure? or overkill?


 // in the usage of isIdle function in control_functions this step is redundant but included here for generality
 Wire.beginTransmission(I2CMUXADDR); // start communicating with I2C multiplexer slave
 Wire.write((uint8_t)(0x04 + ICtoChannel(ICNum))); // enabling required I2C channel
 val += Wire.endTransmission();


 // scan over all registers
 for (uint8_t reg = 0x00; reg <= 0x03; reg++)
 {
   Wire.beginTransmission(ICADDR); // start communication with concerned MUX IC
   Wire.write(reg); // pick concerned internal register of IC
   val += Wire.endTransmission();


   Wire.requestFrom((uint8_t)ICADDR, (uint8_t)1);
   uint8_t data = Wire.read();
   if (data != 0)// i.e. atleast one switch is closed
   {
     IC_idle = false;
     break;
   }
 }

 return IC_idle;
}
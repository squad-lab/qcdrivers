// Values might need to be calibrated for individual boards
int SetDAC(float voltage) {
  // possible voltage from 0.55V to 2.75 V
  DAC_voltage = voltage;
  float write_value = (int)(4096 - 1) * (voltage - 0.55) / (2.75 - 0.55);
  analogWrite(DAC0, write_value);
  return write_value;
}

float GetDAC() {
  return DAC_voltage;
}



float GetADC() {
  // read voltage on ADC in one shot
  return (float)analogRead(A6) / (4096 - 1) * 3.30;
}

float roundtoN(float val, int N){
// round/truncate val to N decimal places
  int temp = val*pow(10,N);
  return ((float) temp)/ (pow(10,N));
  }

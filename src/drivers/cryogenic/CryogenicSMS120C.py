"""
Driver for Cryogenic Magnet Power Supply SMS120C.

Please refer to Cryogenic's Magnet Power Supply SMS120C manual for further
details and functionality. This magnet PS model is not SCPI compliant. Note
that some commands return more than one line in the output, some are
unidirectional, with no return (eg. 'write' rather than 'ask').

This magnet PS driver has been tested with FTDI chip drivers (USB to serial),
    D2XX version installed and with  Cryogenic SMS120C and SMS60C (though the
    default init arguments are not correct for the latter). Both the
    coil_constant and current_rating should be based on calibration data
    accompanying the magnet. The SMS60C current_rating should be slightly below
    60, as indicated by its name. Examples of values for a 2T magnet using
    SMS60C are: coil_constant=0.0380136, current_rating=52.61
"""

import re
import logging
import time

from qcodes.utils.validators import Numbers
from qcodes import VisaInstrument
import pyvisa.constants as vi_const
from pyvisa.errors import VisaIOError


log = logging.getLogger(__name__)

_UNSET = object()


class CryogenicSMS120C(VisaInstrument):

    """
    The following hard-coded, default values for Cryogenic magnets are safety limits
    and should not be modified.
    - these values should be set using the corresponding arguments when the class is called.
    """
    default_current_ramp_limit = 0.0506  # [A/s]
    default_max_current_ramp_limit = 0.12  # [A/s]

    """
    Driver for the Cryogenic SMS120C magnet power supply.
    This class controls a single magnet PSU.
    Magnet and magnet PSU limits : max B=12T, I=105.84A, V=3.5V

    Args:
        name (str): a name for the instrument
        address (str): (serial to USB) COM number of the power supply
        coil_constant (float): coil constant in Tesla per ampere, fixed at 0.113375T/A
        current_rating (float): maximum current rating in ampere, fixed at 105.84A
        current_ramp_limit (float): current ramp limit in ampere per second,
            for 50mK operation 0.0506A/s (5.737E-3 T/s, 0.34422T/min) - usually used
            for 4K operation 0.12A/s (0.013605 T/s, 0.8163 T/min) - not recommended

    Note about timing : SMS120C needs a minimum of 200ms delay between commands being sent
    """

    # Reg. exp. to match a float or exponent in a string
    _re_float_exp = r'[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?'

    def __init__(self, name, address, coil_constant=0.113375, current_rating=105.84,
                 current_ramp_limit=0.0506, timeout=20, **kwargs):

        log.debug('Initializing instrument')

        if 'terminator' in kwargs.keys():
            kwargs.pop('terminator')
            log.warning('Passing terminator to CryogenicSMS is no longer supported and has no effect')

        super().__init__(name, address, terminator='\r\n', **kwargs)

        # Apply VISA timeout (pyvisa uses milliseconds)
        self.visa_handle.timeout = int(timeout * 1000)

        self.visa_handle.baud_rate = 9600
        self.visa_handle.parity = vi_const.Parity.none
        self.visa_handle.stop_bits = vi_const.StopBits.one
        self.visa_handle.data_bits = 8
        self.visa_handle.flow_control = 0
        self.visa_handle.flush(vi_const.VI_READ_BUF_DISCARD |
                               vi_const.VI_WRITE_BUF_DISCARD)  # keep for debugging
        

        # Give the interface/controller a short settle time after opening
        time.sleep(0.25)

        idn = self.IDN.get()
        print(idn)

        self._persistentField = 0  # temp code stub
        self._coil_constant = coil_constant
        self._current_rating = current_rating
        self._current_ramp_limit = current_ramp_limit
        self._field_rating = coil_constant * \
            current_rating  # corresponding max field based
        self._field_ramp_limit = coil_constant * current_ramp_limit

        # ADDED WAIT FOR FIELD PARAMETERS TO BE CHANGEABLE
        self._wait_field_threshold = 0.0013   # T (1.3 mT default)
        self._wait_refresh_time = 0.3         # s
        self._wait_timeout = None             # None -> computed 1.1 * max ramp time
        self._wait_check_status_period = 5    # s

        self.add_parameter(name='unit',
                           get_cmd=self._get_unit,
                           set_cmd=self._set_unit,
                           val_mapping={'AMPS': 0, 'TESLA': 1})

        self.add_parameter('rampStatus',
                           get_cmd=self._get_rampStatus,
                           val_mapping={'HOLDING': 0,
                                        'RAMPING': 1,
                                        'QUENCH DETECTED': 2,
                                        'EXTERNAL TRIP': 3,
                                        'FAULT': 4,
                                        })

        self.add_parameter('polarity',
                           get_cmd=self._get_polarity,
                           set_cmd=self._set_polarity,
                           val_mapping={'POSITIVE': '+', 'NEGATIVE': '-'})

        self.add_parameter(name='switchHeater',
                           get_cmd=self._get_switchHeater,
                           set_cmd=self._set_switchHeater,
                           val_mapping={False: 0, True: 1})

        self.add_parameter('persistentMode',
                           get_cmd=self._get_persistentMode,
                           set_cmd=self._set_persistentMode,
                           val_mapping={False: 0, True: 1})

        self.add_parameter(name='persistentField',
                           get_cmd=self._get_persistentField,
                           vals=Numbers(self._persistentField))

        self.add_parameter(name='field',
                           get_cmd=self._get_field,
                           set_cmd=self._set_field_bidirectional,#_set_field,
                           vals=Numbers(-self._field_rating,  # i.e. ~12T, calculated
                                        self._field_rating))
        
        self.add_parameter(name='sweepField',
                           get_cmd=self._get_field,
                           set_cmd=self._set_field_bidirectional_fast,#_set_field,
                           vals=Numbers(-self._field_rating,  # i.e. ~12T, calculated
                                        self._field_rating))

        self.add_parameter(name='maxField',
                           get_cmd=self._get_maxField,
                           set_cmd=self._set_maxField,
                           vals=Numbers(0,  # i.e. ~12T, calculated
                                        self._field_rating))

        self.add_parameter(name='rampRate',
                           get_cmd=self._get_rampRate,
                           set_cmd=self._set_rampRate,
                           vals=Numbers(0,
                                        self._current_ramp_limit))

        self.add_parameter('pauseRamp',
                           set_cmd=self._set_pauseRamp,
                           get_cmd=self._get_pauseRamp,
                           val_mapping={False: 0, True: 1})


    def get_idn(self):
        """
        Overwrites the get_idn function using constants as the hardware
        does not have a proper ``*IDN`` function.
        """
        idparts = ['Cryogenic', 'Magnet PS SMS120C', 'None', '1.0']

        return dict(zip(('vendor', 'model', 'serial', 'firmware'), idparts))

    def query(self, msg):
        """
        Message outputs do not follow the standard SCPI format,
        separate regexp to parse unique/variable instrument message structures.

        Returns:
            The key (unused), and the value (parsed value extracted from output
            message)
        """
        #value = self.ask(msg)
        value = self._ask_retry(msg, retries=3, delay=0.2)

        #BUG: The SMS60C sometimes returns an incorrect \x13 at the beginning of the string
        value = value.strip('\x13')
        m = re.match(r'((\S{8})\s)+(([^:]+)(:([^:]+))?)', value)
        if not m:
            log.error('Malformed message received from the magnet PS: "%s"', value)
            return None, None

        if m[2] == '------->':
            log.error('Command information or unrecognizable qualifier: "%s"', m[3])
            return None, None

        key = m[4].strip()
        val = m[6].strip() if m[6] is not None else None
        return key, val

    def _flush_io(self) -> None:
        """Best-effort flush of VISA buffers."""
        try:
            self.visa_handle.flush(
                vi_const.VI_READ_BUF_DISCARD | vi_const.VI_WRITE_BUF_DISCARD
            )
        except Exception:
            # Some VISA backends can throw here; flushing is best-effort only.
            pass


    def _ask_retry(self, msg: str, retries: int = 3, delay: float = 0.2) -> str:
        """Ask with retries on VISA timeouts/transient errors."""
        last_exc: Exception | None = None

        for _ in range(retries):
            try:
                # use super() to avoid recursion if you later override ask()
                return super().ask(msg)
            except VisaIOError as e:
                last_exc = e
                self._flush_io()
                time.sleep(delay)
            except Exception as e:
                last_exc = e
                self._flush_io()
                time.sleep(delay)

        raise RuntimeError(
            f"Instrument ask failed after {retries} retries for {msg!r}. Last error: {last_exc}"
        )

    def _get_limit(self):
        """Get voltage limit (float, in VOLTS)."""
        last = None
        for _ in range(3):
            _, value = self.query('GET VL')
            last = value

            if value is None:
                time.sleep(0.2)
                continue

            m = re.match(r'({}) VOLTS'.format(CryogenicSMS120C._re_float_exp), value)
            if m:
                return float(m[1])

            time.sleep(0.2)

        raise RuntimeError(f"GET VL returned unexpected reply: {last!r}")

    # get heater status, returns a boolean ON (1) or OFF (0)
    def _get_switchHeater(self):
        last = None
        for _ in range(3):
            _, value = self.query('HEATER')
            last = value
            if value is None:
                time.sleep(0.2)
                continue

            v = value.upper()
            if 'OFF' in v:
                return 0
            if 'ON' in v:
                return 1

            time.sleep(0.2)

        raise RuntimeError(f"HEATER returned unexpected reply: {last!r}")
    

    # check if magnet is in persistent mode, and if so return current in the
    # magnet
    def _get_persistentMode(self):
        _, value = self.query('HEATER')
        field = self._get_field()
        # check for switch heater OFF, and non-zero current
        if value is not None and ('OFF' in value) and (abs(field) >= 0.005):
            persistentField = self._get_persistentField()
            units = self._get_unit()
            if units == 1:
                log.info("Magnet in persistent mode, at a field of %f T" %
                         persistentField)
            elif units == 0:
                log.info("Magnet in persistent mode, at a field of %f A" %
                         persistentField)
            persistentMode = True
        else:
            log.info("Magnet not persistent.")
            persistentMode = False
        return persistentMode

    # get units, returns a boolean integer - Tesla (1) or Amps(0)
    def _get_persistentField(self):
        # read persistent field from controller
        BLeads = self._get_field()
        if (self._get_switchHeater() == 1):
            log.info("Switch heater ON, magnet not in persistent mode.")
            persistentField = 0
        elif (self._get_switchHeater() == 0) and (abs(BLeads) > 0.007):
            log.info(
                "Switch heater OFF, but current is still in present in leads - not in persistent mode. Leads at: %f" % BLeads)
            perString = self._ask_retry('GET PER')
            m = re.match(r'((\S{8})\s)+([^:]+)', perString)
            persistentField = float(m[2])
        else:
            perString = self._ask_retry('GET PER')
            # handles a different string return format
            m = re.match(r'((\S{8})\s)+([^:]+)', perString)
            persistentField = float(m[2])
        return persistentField

    def _get_unit(self):
        last = None
        for _ in range(3):
            _, value = self.query('TESLA')
            last = value

            if value is None:
                time.sleep(0.2)
                continue

            v = value.upper().strip()

            # If controller is returning help/qualifiers, this is not a unit state reply
            if 'QUALIFIER' in v or 'QUALIFIERS' in v:
                time.sleep(0.2)
                continue

            # Expected TESLA-mode indication
            if v == 'TESLA':
                return 1

            # If you ever see an explicit AMPS indication, accept it
            if 'AMPS' in v:
                return 0

            # Unknown reply -> retry
            time.sleep(0.2)

        raise RuntimeError(f"Could not reliably determine unit from TESLA response. Last reply: {last!r}")

    # get direction of current, returns a string - Positive (1) or Negative(0)
    def _get_polarity(self):
        """Get sweep polarity: '+' (POSITIVE) or '-' (NEGATIVE)."""
        last = None
        for _ in range(3):
            _, value = self.query('GET SIGN')
            last = value

            if value is None:
                time.sleep(0.2)
                continue

            v = value.upper().strip()
            if v == 'POSITIVE':
                return '+'
            if v == 'NEGATIVE':
                return '-'

            time.sleep(0.2)

        raise RuntimeError(f"GET SIGN returned unexpected reply: {last!r}")

    def _get_maxField(self):  # Get the maximum B field, returns a float (in Amps or Tesla)
        _, value = self.query('GET MAX')
        units = self._get_unit()
        if units == 1:
            m = re.match(r'({}) TESLA'.format(
                CryogenicSMS120C._re_float_exp), value)
        elif units == 0:
            m = re.match(r'({}) AMPS'.format(
                CryogenicSMS120C._re_float_exp), value)
        maxField = float(m[1])
        return maxField

    # Get current magnetic field, returns a float (if unit is Tesla, otherwise raises an exception)
    def _get_field(self):
        last = None
        for _ in range(3):
            _, value = self.query('GET OUTPUT')
            last = value

            if value is None:
                time.sleep(0.2)
                continue

            m = re.match(
                r'({}) TESLA AT ({}) VOLTS'.format(CryogenicSMS120C._re_float_exp, CryogenicSMS120C._re_float_exp), value)
            if m:
                return float(m[1])

            # Reply existed but didn't match expected TESLA format → retry
            time.sleep(0.2)

        raise RuntimeError(f"GET OUTPUT returned unexpected reply (cannot parse TESLA field). Last reply: {last!r}")

    def _get_rampStatus(self):
        last = None
        for _ in range(3):
            _, value = self.query('RAMP STATUS')
            last = value

            if value is None:
                time.sleep(0.2)
                continue

            v = value.upper()
            if 'HOLDING' in v:
                return 0
            if 'RAMPING' in v:
                return 1
            if 'QUENCH' in v:
                return 2
            if 'EXTERNAL' in v:
                return 3
            if 'FAULT' in v:
                return 4

            time.sleep(0.2)

        raise RuntimeError(f"RAMP STATUS returned unexpected reply: {last!r}")

    # checks if controller is paused (1) or active (0), returns a boolean
    # integer
    def _get_pauseRamp(self):
        _, value = self.query('PAUSE')
        if value == 'ON':
            pauseRamp = 1
        else:  # assume pause OFF
            pauseRamp = 0
        return pauseRamp

    # Get current magnet ramping rate, returns a float (in units of Amps/sec only)
    def _get_rampRate(self):
        last = None
        for _ in range(3):
            _, value = self.query('GET RATE')
            last = value

            # If query() couldn't parse the reply, retry after a short pause
            if value is None:
                time.sleep(0.2)
                continue

            # Try to parse something like "0.0506 A/SEC"
            m = re.match(r'({}) A/SEC'.format(CryogenicSMS120C._re_float_exp), value)
            if m:
                rampRate = float(m[1])
                if rampRate <= 0:
                    raise RuntimeError(f"Invalid ramp rate returned: {rampRate}")
                return rampRate

            # Reply existed but didn't match expected format → wait and retry
            time.sleep(0.2)

        # After retries, fail with a meaningful error containing the last reply
        raise RuntimeError(f"GET RATE returned unexpected reply: {last!r}")

    # Set magnet sweep direction : "+" for positive B, "-" for negative B
    def _set_polarity(self, val):
        # using standard write as read returns an error/is non-existent.
        if self._get_persistentMode() == False and abs(self._get_field()) <= 0.007:
            self.write('DIRECTION %s' % val)
            return True
        elif self._get_persistentMode() == True:
            log.error(
                'Cannot switch polarity, magnet in persistent mode - please engage switch heater and go to zero field before changing sign.')
            return False
        elif abs(self._get_field()) > 0.007:
            log.error('Recommended to switch sign only when field is at zero.')
            return False
        else:
            log.error('Cannot switch polarity, check magnet.')
            return False

    def _set_unit(self, val):        # Set unit to Tesla(1) or Amps(0),
        # Enables us to set units of Tesla
        self._ask_retry('SET TPA %f' % self._coil_constant)
        self._ask_retry('TESLA %d' % val)

    def _set_maxField(self, val):  # Set the maximum field (in Amps or Tesla)
        self._ask_retry('SET MAX %0.2f' % val)

    def _set_switchHeater(self, val):  # Turn heater ON(1) or OFF(0)
        if self._get_rampStatus() == 1:
            log.error(
                'Cannot switch heater during a ramp, first pause the controller.')
        else:
            # Switch ON, if currently OFF
            if val == 1 and (self._get_switchHeater() == False):
                strHeaterStatus = self._ask_retry('HEATER %d' % val)
                switchHeater = 1
            # Switch OFF, if currently ON
            elif val == 0 and (self._get_switchHeater() == True):
                strHeaterStatus = self._ask_retry('HEATER %d' % val)
                switchHeater = 0
            else:  # assume no change to current switch heater state
                strHeaterStatus = self._ask_retry('HEATER %d' % val)
                switchHeater = self._get_switchHeater()
            log.info(strHeaterStatus)
            return switchHeater

    # Move into persistent mode (1) or out of persistent mode(0)
    def _set_persistentMode(self, val):
        if self._get_rampStatus() == 0:     # Check magnet on HOLD
            currField = self._get_field()
            log.info("Leads now at %f ." % currField)
            # Enter persistent mode from non-persistent
            if val == 1:
                if self._get_persistentMode() == False and (self._get_switchHeater() == True):
                    log.info('Moving into persistent mode:')
                    switchHeater = 0
                    strHeaterStatus = self._ask_retry('HEATER %d' % switchHeater)
                    log.info(strHeaterStatus)
                    log.info('Waiting 60s for switch heater to cool down.')
                    time.sleep(60)
                    log.info('Ramping down magnet leads...')
                    self._set_field(0)
                    while True:
                        if self._get_rampStatus() == 0:
                            log.info('Leads at zero.')
                            persistentMode = 1
                            persistentField = self._get_persistentField()
                            log.info(
                                'Magnet is in persistent mode at Field = %f.' % persistentField)
                            break
                        time.sleep(5)  # check every 5 seconds
                elif self._get_persistentMode() == True:
                    persistentMode = 1
                    persistentField = self._get_persistentField()
                    log.info('Already in persistent mode.')
            # Exit persistent mode
            elif val == 0:
                persistentField = self._get_persistentField()
                if self._get_persistentMode() == True and (self._get_switchHeater() == False):
                    log.info('Exiting persistent mode from a field of %f' %
                             persistentField)
                    switchHeater = 1
                    strHeaterStatus = self._ask_retry('HEATER %d' % switchHeater)
                    log.info(strHeaterStatus)
                    log.info('Waiting 30s for switch heater to warm up.')
                    time.sleep(30)
                    log.info(
                        'Matching magnet lead current to persistent field of %f...' % persistentField)
                    self._set_field(persistentField)
                    while True:
                        if self._get_rampStatus() == 0:
                            persistentMode = 0
                            persistentField = 0
                            log.info('Magnet is non-persistent.')
                            break
                        time.sleep(5)  # check every 5 seconds
                elif self._get_persistentMode() == False:
                    persistentMode = 0
                    persistentField = 0
                    log.info('Magnet already non-persistent.')
        else:
            log.warning(
                'Cannot change (non-)persistent mode state, check magnet status.')
        return persistentMode, persistentField

    def _set_pauseRamp(self, val):  # Pause magnet controller Pause=1, Unpause=0
        self._ask_retry('PAUSE %d' % val)

    # Set ramp speed Amps/sec , check it is reasonable if it is being manually
    # modified
    def _set_rampRate(self, val):
        if self._current_ramp_limit is None:
            self._current_ramp_limit = CryogenicSMS120C.default_current_ramp_limit

        if val <= self._current_ramp_limit:
            self._ask_retry('SET RAMP %0.2f' % val)
            return True
        elif val > CryogenicSMS120C.default_max_current_ramp_limit:
            self._ask_retry('SET RAMP %0.2f' %
                     CryogenicSMS120C.default_current_ramp_limit)
            msg = 'Requested rate of {} is unsafe and over the maximum limit of {} A/s. Coerced to default ramp rate.'
            log.error(msg.format(
                val, CryogenicSMS120C.default_max_current_ramp_limit))
            return False
        else:
            msg = 'Requested ramp speed is over the limit of {} A/s. Change limit, at your own risk after consulting the SMS120C manual.'
            log.error(msg.format(self._current_ramp_limit))
            return False

    # Check magnet state and ramp speed to see if it is safe to ramp, returns
    # boolean
    def _can_startRamping(self):
        state = self._get_rampStatus()

        if self._get_rampRate() <= self._current_ramp_limit:
            if state == 2:         # Quench
                log.error(
                    'Magnet quench detected - please check magnet status before ramping.')
                return False
            elif state == 1:       # Ramping
                log.info('Magnet currently ramping.')
                return True
            elif state == 0:       # Holding
                log.info('Magnet currently holding.')
                return True
            log.error(
                'Could not ramp, magnet in state: {}'.format(state))
            return False
        else:
            log.warning(
                'Could not ramp, ramp rate is over the set limit, please lower.')
            return False

    # Between any two commands, there are must be around 200ms waiting time.
    def _set_field(self, val):
        #Set field magnitude (TESLA) assuming polarity already correct. Expects val >= 0.
        if val < 0:
            raise ValueError("_set_field expects a non-negative magnitude; use _set_field_bidirectional for signed fields.")

        if not self.switchHeater(): # If switch heater is OFF
            log.error('Unable to set field, switch heater is off, persistent mode may be active')
            return
        # check ramp status is OK
        if self._can_startRamping():
            # Check that field is not outside max.field limit
            if (self._get_unit() == 1 and (val <= self._get_maxField())) or (
                    self._get_unit() == 0 and (val <= self._current_rating)):
                # pause the controller if it is currently ramping
                self._set_pauseRamp(1)
                self._ask_retry('SET MID %0.3f' % val)       # Set target field, CHANGED FROM 0.2 to 0.3
                self._set_pauseRamp(0)               # Unpause the controller
                # Ramp magnet/field to MID or ZERO (Note: Using standard write
                # as read returns an error/is non-existent).
                if val == 0:
                    self.write('RAMP ZERO')
                    log.info('Ramping magnetic field to zero...')
                else:
                    self.write('RAMP MID')
                    log.info('Ramping magnetic field...')

                pol = self._get_polarity()
                signed_target = -val if pol == '-' else val
                self._wait_for_field(signed_target)#, refresh_time=0.05)   # ADDED WAIT UNTIL FIELD IS ACTUALLY REACHED
                #THIS MIGHT LEAD TO PROBLEMS WITH NEGATIVE FIELDS, CHECK!!!!
            else:
                log.error(
                    'Target field is outside max. limits, please lower the target value.')
        else:
            log.error('Cannot set field - check magnet status.')


    def _set_field_bidirectional(self, val):
        # Set signed field in TESLA, handling polarity changes safely.
        # IMPORTANT: SMS120C uses magnitude for SET MID; direction is controlled by polarity.

        if val == 0:
            self._set_field(0.0)
            return
        
        polarity = self._get_polarity()
        desired_polarity = '-' if val < 0 else '+'

        if polarity != desired_polarity:
            self._set_field(0)
            # This is, sadly, blocking     ???
            self._wait_for_field(0 , field_threshold=0.001)
            self._set_polarity(desired_polarity)

        self._set_field(abs(val))





    def _set_field_bidirectional_fast(self, val: float) -> None:
        """
        Fast signed field setter intended for stepped sweeps.
        Assumes preflight_sweep() was run and Tesla mode is active.

        Uses magnitude for SET MID and polarity for sign.
        """
        # Handle zero early
        if val == 0:
            magnitude = 0.0
        else:
            desired_polarity = '-' if val < 0 else '+'
            magnitude = abs(val)

        # Abort on fault states
        st = self._get_rampStatus()
        if st in (2, 3, 4):
            raise RuntimeError(f"Magnet in error state {st} (2=QUENCH,3=EXTERNAL,4=FAULT).")

        # If sign needs to change, go to ~0 first, then flip polarity
        if val != 0:
            current_pol = self._get_polarity()
            if current_pol != desired_polarity:
                self._ask_retry("SET MID %0.3f" % 0.0)
                self.write("RAMP ZERO")
                self._wait_for_field(0.0)  

                ok = self._set_polarity(desired_polarity)
                if not ok:
                    raise RuntimeError(f"Failed to set polarity to {desired_polarity}")

        # Now ramp to the requested magnitude with the (possibly updated) polarity
        self._ask_retry("SET MID %0.3f" % magnitude)
        if magnitude == 0:
            self.write("RAMP ZERO")
        else:
            self.write("RAMP MID")

        # Wait for signed target (your _get_field returns signed value)
        self._wait_for_field(float(val))

    
    # RENAMED to _wait_for_field from _wait_for_field_zero AND UPDATED THRESHOLD FROM 0.003 to 0.0003 AND time from 0.1 to 0.05
    # Wait until field() is within field_threshold of target_field.
    # Adds timeout and basic state checks to avoid infinite blocking if the ramp stops.
    # If timeout is None, use 1.1 * (max current / current ramp limit) as a conservative bound.
    # Waits for the field to be within a certain threshold
    def _wait_for_field(
        self,
        target_field: float,
        field_threshold: float | None = None,
        refresh_time: float | None = None,
        timeout: float | None = None,
    ):
        if field_threshold is None:
            field_threshold = self._wait_field_threshold
        if refresh_time is None:
            refresh_time = self._wait_refresh_time
        if timeout is None:
            timeout = self._wait_timeout

        if timeout is None:
            start_field = self.field()
            delta_B = abs(target_field - start_field)
            delta_I = delta_B / self._coil_constant
            timeout = 1.2 * (delta_I / self._get_rampRate()) + 10 # +10s slack


        t0 = time.time()
        next_status_check = t0 + self._wait_check_status_period

        while True:
            now = time.time()

            if now - t0 > timeout:
                raise TimeoutError(
                    f"Timed out waiting for field to reach {target_field} T "
                    f"(threshold {field_threshold} T). Last field was {self.field()} T."
                )

            # ramp status check every N seconds
            if now >= next_status_check:
                status = self._get_rampStatus()
                if status in (2, 3, 4):
                    raise RuntimeError(
                        f"Magnet entered error state {status} while waiting for field to reach target."
                    )
                if self._get_switchHeater() != 1:
                    raise RuntimeError("Switch heater is OFF. Cannot set field.")
                next_status_check = now + self._wait_check_status_period

            if abs(self.field() - target_field) <= field_threshold:
                return

            #print(target_field)
            time.sleep(refresh_time)



    def configure_wait(
        self,
        field_threshold: float | None = None,
        refresh_time: float | None = None,
        timeout=_UNSET,
        check_status_period: float | None = None,
    ) -> None:
        #Configure waiting behavior for field ramps.

        #Any argument left as None is not changed.
        #timeout=None means use the computed default (1.1 * max ramp time).

        if field_threshold is not None:
            if field_threshold <= 0:
                raise ValueError("field_threshold must be > 0")
            self._wait_field_threshold = float(field_threshold)

        if refresh_time is not None:
            if refresh_time <= 0:
                raise ValueError("refresh_time must be > 0")
            self._wait_refresh_time = float(refresh_time)

        # NOTE: timeout can validly be None (meaning: computed default)
        if timeout is not _UNSET:
            if timeout is not None and timeout <= 0:
                raise ValueError("timeout must be > 0 or None")
            self._wait_timeout = timeout

        if check_status_period is not None:
            if check_status_period <= 0:
                raise ValueError("check_status_period must be > 0")
            self._wait_check_status_period = float(check_status_period)

    
    
    def preflight_sweep(self, *, require_tesla: bool = True) -> None:
        """
        Run once before a stepped sweep using sweep_field.

        Ensures the controller is in a sane state and avoids per-step overhead.
        Raises RuntimeError on unsafe/unknown states.
        """
        # Reject fault states
        st = self._get_rampStatus()
        if st in (2, 3, 4):
            raise RuntimeError(f"Magnet in error state {st} (2=QUENCH,3=EXTERNAL,4=FAULT).")

        # Heater must be ON (otherwise persistent mode may be active)
        if self._get_switchHeater() != 1:
            raise RuntimeError("Switch heater is OFF. Cannot sweep safely.")

        # Ensure TESLA mode if desired
        if require_tesla:
            if self._get_unit() != 1:
                # strict: don’t silently coerce; you can decide to call self.unit('TESLA') outside if you want
                raise RuntimeError("Controller is not in TESLA mode.")

        # Ramp rate sanity (also ensures GET RATE parsing works)
        rr = self._get_rampRate()
        if rr <= 0 or rr > self._current_ramp_limit:
            raise RuntimeError(f"Invalid ramp rate: {rr}")

        # MaxField sanity (optional, but useful)
        mf = self._get_maxField()
        if mf <= 0 or mf > self._field_rating:
            raise RuntimeError(f"Invalid maxField: {mf}")


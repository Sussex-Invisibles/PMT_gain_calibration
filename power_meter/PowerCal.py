import threading
import time
#import ROOT
from core import serial_command
import sys
from pyvisa.vpp43 import visa_library
visa_library.load_library("/Library/Frameworks/VISA.framework/VISA")
import visa
import serial
from array import *
#from find import *`
#import util
import math
import random


class Power_Meter(threading.Thread):
#class Power_Meter():
    
    def __init__(self, threadID, name, wavelength, period, fileName ):
        #-- Definitions
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.period = period
        self.exit_flag = 0
        self.scale = self.scaling(wavelength)
        
        wait = 0.25         # Wait call, in s
        pW    = 1e-12       # 1 pico Watt
        
        ####################
        # INSTRUMENT SET-UP
        ####################
        print visa.get_instruments_list() # enable this to find the device ID if needed
        #self.power_meter = visa.instrument("USB0::0x1313::0x8072::P2000781::0") # Leeds
        self.power_meter   = visa.instrument("USB0::0x1313::0x8072::P2001877::0") # Sussex
        
        time.sleep(wait);   self.power_meter.write("*RST")
        time.sleep(wait);   print "Info: Instrument ID:",   self.power_meter.ask("*IDN?")
        time.sleep(wait);   print "Info: Self test status:",self.power_meter.ask("*TST?")
        time.sleep(wait);   print "Info: System version: ", self.power_meter.ask("SYSTEM:VERSION?")
        time.sleep(wait);   response = self.power_meter.ask("SYSTEM:SENSOR:IDN?"); list = response.split(","); print "Info: Sensor ID is ",list[0];

        time.sleep(wait);   self.power_meter.write("CONFIGURE:SCALAR:TEMPERATURE")
        time.sleep(wait);   temperature = float(self.power_meter.ask("READ?")); print "Info: Sensor temperature is %.1f Celsius" % temperature

        time.sleep(wait);   self.power_meter.write("CONFIGURE:SCALAR:POWER")
        time.sleep(wait);   self.power_meter.write("POWER:DC:UNIT W")
        time.sleep(wait);   print "Info: Unit for DC power is now : ",self.power_meter.ask("POWER:DC:UNIT?")

        time.sleep(wait);   self.power_meter.write("SENSE:CORRECTION:WAVELENGTH "+str(int(wavelength)))
        time.sleep(wait);   nm = float(self.power_meter.ask("SENSE:CORRECTION:WAVELENGTH?")); print "Info: Wavelength now set to [nm]: ",int(nm)
        time.sleep(wait);   self.power_meter.write("SENSE:AVERAGE:COUNT 3000")
        time.sleep(wait);   counts = int(self.power_meter.ask("SENSE:AVERAGE:COUNT?")); print "Info: Samples per average pre zero adjustment: ",int(counts)

        time.sleep(wait);   print "Info: Configuration is set to : ", self.power_meter.ask("CONFIGURE?")
        time.sleep(wait);   print "Info: Power auto range status : ", self.power_meter.ask("POWER:RANGE:AUTO?")
        
        #-- zero suppression
        for n in range(0, 1) :
            time.sleep(wait); self.power_meter.write("SENSE:CORRECTION:COLLECT:ZERO:INITIATE")
            state = 9
            while state > 0 :
                time.sleep(wait);  state = int(self.power_meter.ask("SENSE:CORRECTION:COLLECT:ZERO:STATE?"))
                print "Info: Zero adjustment (1=waiting, 0=done) :", state
            else:
                ped = float(self.power_meter.ask("SENSE:CORRECTION:COLLECT:ZERO:MAGNITUDE?"))
                time.sleep(wait); print "Info: Pedestal [pW] : ",ped/pW
        
        #-- reduce counts per average (1 count takes 2 ms)
        counts = 500
        cmd = "SENSE:AVERAGE:COUNT %i " % counts
        time.sleep(wait); self.power_meter.write(cmd)
        time.sleep(wait); counts = int(self.power_meter.ask("SENSE:AVERAGE:COUNT?"))
        print "Info: Samples per average post zero adjustment: ",int(counts)
    
        #-- Save header to file
        data = open(fileName,"w")
        rate=1./period
        dataStr = "%i %1.2e %i %2.1f %3.3e \n" % (wavelength, period, rate, temperature, ped)
        data.write(dataStr)
        data.close()


    def scaling(self, wavelength):
        E = 6.63e-34*3e8 / (wavelength*1e-9)    # Calc photon energy (hc/lambda)
        noPhotonsPerSec = 1e-12 / E             # no. of photons per sec for pW of power
        return noPhotonsPerSec
    
    def run(self):
        print "Info: Starting " + self.name
        global ppp_value, ppp_error, Watt_value, Watt_error
        p_dict = {}
        while self.exit_flag < 1 :
            with LOCK:
                p_dict = self.read()
                ppp_value = p_dict["photons"]
                ppp_error = p_dict["error"]
                Watt_value = p_dict["Watts"]
                Watt_error = p_dict["Watt_error"]
            time.sleep(0.1)
        print "Info: Exiting " + self.name

    def read(self, sample_time=4.0) :
        global width
        pW    = 1e-12
        power = []
        start = time.time()                                             # start clock for OFF time
        #while  (time.time()+86400-start)%86400 < sample_time  :
        while  (time.time() < (start + sample_time)):
            #power.append(power)
            power.append(float(self.power_meter.ask("READ?")))          # start measurement; when finished read average power
        if len(power) < 3 :
            print "Warning: Only %i power measurements made." % power.size
        power_avg = self.avg(power)
        power_rms = self.std(power,power_avg)
        del power
        Watt_value = power_avg
        Watt_error = power_rms
        ppp_value = self.scale*1e-4 * (power_avg/pW)*(self.period/100e-6)         # number of photons per pulse
        ppp_error = self.scale*1e-4 * (power_rms/pW)*(self.period/100e-6)         # error estimate
        print "Info: Watts %1.4e +/- %1.2e : Photons per pulse %1.4e +/- %1.2e, width %i" % (Watt_value, Watt_error, ppp_value, ppp_error, width)
        return { "Watts" : Watt_value , "Watt_error" : Watt_error, "photons" : ppp_value , "error" : ppp_error  }

    def avg(self, tmpList):
        sum=0
        for ent in tmpList:
            sum += ent
        return sum / len(tmpList)

    def std(self, tmpList, tmpAvg):
        sqSum=0;
        for ent in tmpList:
            sqSum += (ent - tmpAvg)*(ent - tmpAvg)
        return math.sqrt(sqSum/len(tmpList))

##########################
#   MAIN FUNCTION
##########################
if __name__ == "__main__":
    
    #Datafile name
    fname = "./data/pin_calib_TellieRange.dat"

    pulse_delay_ms = 25e-3  # in ms (for direct input to set_pulse_delay func)
    wavelength=495          # in nm

    # Set up range of widths to be run
    widths = range(0,9000,100)
    #widths = [0,6000]
    print widths
    
    channel = 5

    power_meter = Power_Meter( 1, "power_meter", wavelength, pulse_delay_ms*1e-3, fname )  # ID, name, wavelength [nm], pulse period [s]
    sc = serial_command.SerialCommand('/dev/tty.usbserial-FTGA2OCZ')

    LOCK = threading.RLock()
    with LOCK:
        ppp_value = 0
        ppp_error = 0
        Watt_value = 0
        Watt_error = 0

    sc.select_channel(channel)
    sc.set_pulse_width(0)
    sc.set_pulse_delay(pulse_delay_ms)
    sc.set_pulse_number(100)
    sc.set_fibre_delay(0)
    sc.set_trigger_delay(0)
    sc.disable_external_trigger()
    sc.set_pulse_height(16383)
    sc.fire()
    time.sleep(1)
    pin = None
    while pin==None:
        pin = sc.read_pin()
    print "DARK FIRE OVER: PIN",pin
    time.sleep(1)

    sc.clear_channel()
    sc.select_channel(channel)
    sc.set_pulse_width(0)
    sc.set_pulse_delay(pulse_delay_ms)
    sc.set_pulse_number(100)
    sc.set_fibre_delay(0)
    sc.set_trigger_delay(0)
    sc.set_pulse_height(16383)
    #sc.disable_external_trigger()
        
    ipt = 0
    data = open(fname,"a")

    width = widths[0]
    power_meter.start()
    time.sleep(3)
    for width in widths:
        #with LOCK:
            #if width == 0:
            #if i % 2 == 0:
            #   width = int(6500 + i*12.5)
            #   width = int(6700 +  random.random()*400)
            #else:
            #width = 0
        sc.set_pulse_width(width)
        time.sleep(0.1)
        sc.fire_continuous()
        time.sleep(10)
        tmpPPP = ppp_value
        tmpPPPErr = ppp_error
        tmpWatt = Watt_value
        tmpWattErr = Watt_error
        time.sleep(1)
        sc.stop()
        with LOCK:
            sc.fire_sequence()
            #time.sleep(1)
            pin = None
            print "pin init ",pin
            while pin==None:
                pin, _ = sc.read_pin_sequence()
            try:
                dataStr = "%i %i %i %i %1.7e %1.2e \n" % (width, int(pin[channel]), tmpPPP, tmpPPPErr, tmpWatt, tmpWattErr)
                data.write(dataStr)
                data.flush()
            except:
                print "ERROR WITH DATA WRITING"
                power_meter.exit_flag = 1
            
            # Print results
            print "*********** DATA FOR WIDTH: %4i ************" % (width)
            outStr = "Width: \t\t%i \nPIN: \t\t%i \nPhoton no.: \t%1.4e +/- %1.1e \nWatts: \t\t%1.4e +/- %1.1e" % (width, int(pin[channel]), tmpPPP, tmpPPPErr, tmpWatt, tmpWattErr)
            print outStr
            print "*********************************************"
            print ""

    power_meter.exit_flag = 1
    data.close()


        

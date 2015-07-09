###################################################
# Script to sweep over ipw range, acquiring
# a set of PMT pulses at each step. PMT's charge
# response is then calculated through calculations
# of similar power meter linearity data.
#
# Author: Ed Leming
# Date: 21/10/2014
###################################################

# from tellie and leCroyScope directories
# run "source env.sh" if these fail
from core import serial_command
import scopes
import scope_connections
import sweep
# standard libray stuff
import time
import sys
import math
import os
import optparse
import numpy as np

def readPowerMeterFile(fileName):
    """Read previously generated power meter file"""
    # Open file, read only the first line
    with open(fileName, 'r') as file:
        header = file.readline()
    # Return as dict.
    tmp = header.split(" ")
    head = {"Wavelength" : int(tmp[0]), "Pulse sep" : float(tmp[1]), "Rate" : int(tmp[2]), "Temp" : float(tmp[3]), "Pedestal" : float(tmp[4]) }
    noLin = sum(1 for line in open(fileName)) - 1  ###-1 to correct for header

    # Open file
    widths, c = np.zeros(noLin, dtype=int), 0
    with open(fileName, 'r') as file:
        next(file)
        for line in file:
            tmp = line.split(" ")
            widths[c] = np.int(tmp[0])
            c=c+1
    # return filled lists
    return head, widths


##########################
#   MAIN FUNCTION
##########################
if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option("-f",dest="file",help="Power meter file to be loaded")
    parser.add_option("-c",dest="channel",help="Channel number (1-8)")
    parser.add_option("-v",dest="voltage",help="Gain setting at PMT (V)")
    (options,args) = parser.parse_args()
    total_time = time.time()

    # Read in power meter file to get width / frequency settings
    header, widths = readPowerMeterFile(options.file)

    #widths = range(7200,7500,100)
    print widths

    channel = int(options.channel)
    pulse_delay_ms = header["Pulse sep"]*1e3

    sc = serial_command.SerialCommand('/dev/tty.usbserial-FTE3C0PG')
    sc.clear_channel()
    sc.select_channel(channel)
    sc.set_pulse_width(0)
    sc.set_pulse_delay(pulse_delay_ms)
    sc.set_pulse_number(100)
    sc.set_fibre_delay(0)
    sc.set_trigger_delay(0)
    sc.set_pulse_height(16383)

    #run the initial setup on the scope
    usb_conn = scope_connections.VisaUSB()
    scope = scopes.Tektronix3000(usb_conn)
    ###########################################
    scope_chan = 1 # We're using channel 1!
    termination = 50 # Ohms
    trigger_level = 0.5 # half peak minimum
    falling_edge = True
    min_trigger = -0.004
    y_div_units = 1 # volts
    x_div_units = 10e-9 # seconds
    y_offset = 0.5*y_div_units # offset in y (for UK scope)
    x_offset = +2*x_div_units # offset in x (2 divisions to the left)
    record_length = 1e3 # trace is 1e3 samples long
    half_length = record_length / 2 # For selecting region about trigger point
    ###########################################
    scope.set_horizontal_scale(x_div_units)
    scope.set_horizontal_delay(x_offset) #shift to the left 2 units
    scope.set_channel_y(scope_chan, y_div_units, pos=2.5)
    scope.set_channel_termination(scope_chan, termination)
    scope.set_single_acquisition() # Single signal acquisition mode
    scope.set_record_length(record_length)
    scope.set_data_mode(half_length-80, half_length+20)
    scope.lock()
    scope.begin() # Acquires the pre-amble!

    #File system stuff
    saveDir = sweep.check_dir("data/scope_data_%1.2fV/" % float(options.voltage))
    sweep.check_dir("%sraw_data/" % saveDir)
    output_filename = "%s/Chan%02d_%1.2fV.dat" % (saveDir,channel,float(options.voltage))
    output_file = file(output_filename,'w')
    output_file.write("#PWIDTH\tPWIDTH Error\tPIN\tPIN Error\tWIDTH\tWIDTH Error\tRISE\tRISE Error\tFALL\t\
FALL Error\tAREA\tAREA Error\tMinimum\tMinimum Error\n")

    flag, tmpResults, min_volt = 0, None, None
    run_start = time.time()
    for width in widths:
        loop_start = time.time()
        if tmpResults!=None:
            #set a best guess for the trigger and the scale
            #using the last sweeps value
            min_volt = float(tmpResults["peak"])

        tmpResults = sweep.sweep(saveDir,1,channel,width,pulse_delay_ms,scope,min_volt)        

        output_file.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n"%(width, 0,
                                            tmpResults["pin"], tmpResults["pin error"],
                                            tmpResults["width"], tmpResults["width error"],
                                            tmpResults["rise"], tmpResults["rise error"],
                                            tmpResults["fall"], tmpResults["fall error"],
                                            tmpResults["area"], tmpResults["area error"],
                                            tmpResults["peak"], tmpResults["peak error"] ))

        print "WIDTH %d took : %1.1f s" % (width, time.time()-loop_start)

    output_file.close()
    print "Total script time : %1.1f mins"%( (time.time() - total_time) / 60)

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
import scope
# standard libray stuff
import time
import sys
import math
import os
import numpy as np


def readPowerMeterFile(fileName):

    # Open file, read only the first line
    with open(fileName, 'r') as file:
        header = file.readline()
    # Return as dict.
    tmp = header.split(" ")
    head = {"Wavelength" : int(tmp[0]), "Pulse sep" : float(tmp[1]), "Rate" : int(tmp[2]), "Temp" : float(tmp[3]), "Pedestal" : float(tmp[4]) }

    noLin = sum(1 for line in open(fileName)) - 1  ###-1 to correct for header

    # Define new arrays
    widths = np.zeros(noLin)

    # Open file
    c = 0
    with open(fileName, 'r') as file:
        next(file)
        for line in file:
            tmp = line.split(" ")
            widths[c] = int(tmp[0])
            c=c+1

    # return filled lists
    return head, widths


##########################
#   MAIN FUNCTION
##########################
if __name__ == "__main__":

    # Read in power meter file to get width / frequency settings
    fullRfile = "./power_meter/data/pin_calib_Run2.dat"
    fullHeader, fullWidths = readPowerMeterFile(fullRfile)

    selRangeFile = "./power_meter/data/pin_calib_TellieRange.dat"
    selRangeHeader, widths = readPowerMeterFile(selRangeFile)
 
    # Sum two arrays but only keep unique enteries
    #tmpWidths = np.concatenate([fullWidths, selWidths])
    #widths = np.unique(tmpWidths)
    #idx = np.where(widths > 7360)
    #widths = widths[idx]
    print widths
    #widths = [0,6600,7000]

    channel = 5
    pulse_delay_ms = fullHeader["Pulse sep"]*1e3

    sc = serial_command.SerialCommand('/dev/tty.usbserial-FTGA2OCZ')
    sc.clear_channel()
    sc.select_channel(channel)
    sc.set_pulse_width(0)
    sc.set_pulse_delay(pulse_delay_ms)
    sc.set_pulse_number(100)
    sc.set_fibre_delay(0)
    sc.set_trigger_delay(0)
    sc.set_pulse_height(16383)

    scope_chan = 2
    scp = scope.LeCroy684()
    scp.set_x_scale( 2e-9)
    scp.set_y_scale(scope_chan, 2, "V")
    scp.set_y_position(scope_chan, 3, "V")
    scp.set_trigger_mode("single")
    scp.set_trigger_delay(20) # as percentage of full hoizontal scale
    scp.set_trigger(scope_chan, -0.5, True)
    scp.enable_trigger()
    scp.clear_sweeps()

    est_RunTime = (75*len(widths))/60
    print "For {:d} data points, the code will likely take : {:1.1f} mins".format(len(widths), est_RunTime)
    print "####################################################"
    print "Code will be finished at :", time.asctime( time.localtime(time.time()+(est_RunTime*60)) )
    print "####################################################"

    tmp = [widths[1], widths[65], widths[70]]
    tmp = [widths[70],widths[75],widths[80],widths[85],widths[90],widths[95]]
    tmp = [widths[109]]

    flag = 0
    run_start = time.time()
    for width in widths:
        loop_start = time.time()
        sc.set_pulse_width(int(width))
        print "WIDTH: {:d}".format(int(width))
        time.sleep(0.1)
        sc.fire_continuous()
        scp.clear_sweeps()
     
        if(width > 7300 and width < 7450):
            flag=1
            scp.set_y_scale(scope_chan, 0.5, "V")
            scp.set_y_position(scope_chan, 1.5, "V")
            scp.set_trigger(scope_chan, -0.2, True)
        elif(width >= 7450 and width < 7580):
            flag=2
            scp.set_y_scale(scope_chan, 200, "MV")
            scp.set_y_position(scope_chan, 600, "MV")
        elif(width >= 7600 and width < 7680):
            flag=3
            scp.set_y_scale(scope_chan, 50, "MV")
            scp.set_y_position(scope_chan, 150, "MV")
            scp.set_trigger(scope_chan, -0.03, True)
        elif(width >= 7600 and width < 7720):
            flag=4
            scp.set_y_scale(scope_chan, 10, "MV")
            scp.set_y_position(scope_chan, 30, "MV")
            scp.set_trigger(scope_chan, -0.005, True)
        elif(width >= 7720 and width < 7800):
            flag=5
            scp.set_y_scale(scope_chan, 5, "MV")
            scp.set_y_position(scope_chan, 15, "MV")
            scp.set_trigger(scope_chan, -0.005, True)
        elif(width >= 7800):
            flag=5
            scp.set_y_scale(scope_chan, 2, "MV")
            scp.set_y_position(scope_chan, 4, "MV")
            scp.set_trigger(scope_chan, -0.004, True)

        ## TEST STUFF
        #scp.set_trigger_mode("normal")
        #time.sleep(60)

        savePath = "/Users/js376/Desktop/PMT_cal_data/TellieRange_reRun/width_{:d}/".format(int(width))
        if not os.path.exists(savePath):
           os.makedirs(savePath)
        for i in range(1000):
            saveFile = "{}pulse_{:d}.dat".format(savePath,i)
            #print saveFile
            #scp.get_waveform(scope_chan)
            scp.save_waveform(scope_chan, saveFile)
            time.sleep(0.01)

        
        sc.stop()
        print "Loop took : {:1.1f} s".format(time.time() - loop_start)

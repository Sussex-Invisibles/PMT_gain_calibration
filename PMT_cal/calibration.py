##################################################
# Code to use power meter results to calibrate the
# the gain of PMT at a specfic POT setting
#
# Author: Ed Leming
# Date: 23/10/2014
##################################################

# From Matt's leCroyComms scripts
import get_waveform
import sys
#import Analysis
# Standard stuff
import time
import math
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import ROOT

def readHeader(fileName):
    # Open file, read only the first line
    with open(fileName, 'r') as file:
        header = file.readline()
    tmp = header.split(" ")
    # Return as dict.
    return {"Wavelength" : int(tmp[0]), "Pulse sep" : float(tmp[1]), "Rate" : int(tmp[2]), "Temp" : float(tmp[3]), "Pedestal" : float(tmp[4]) }


def readData(fileName):
    # Find no. of lines
    noLin = sum(1 for line in open(fileName)) - 1  ###-1 to correct for header    
    # Define new arrays
    widths, PIN = np.zeros(noLin), np.zeros(noLin)
    photons, photonErr = np.zeros(noLin), np.zeros(noLin)
    watts, wattsErr = np.zeros(noLin), np.zeros(noLin)
    # Open file
    c = 0
    with open(fileName, 'r') as file:
        next(file)
        for line in file:
            tmp = line.split(" ")
            widths[c] = int(tmp[0])
            PIN[c] = int(tmp[1])
            photons[c] = int(tmp[2])
            photonErr[c] = int(tmp[3])
            watts[c] = float(tmp[4])
            wattsErr[c] = float(tmp[5])
            c=c+1
    # return filled lists
    return widths, PIN, watts, wattsErr


def scaling(rawArr, rawErr, header):
    # New arrays
    scaledArr, scaledErr = np.zeros( len(rawArr) ), np.zeros( len(rawArr) )
    # Calculate photon energy (J)
    ePh = (6.626e-34 * 3e8) / (header["Wavelength"]*1e-9)
    # Duty cycle stuff
    pulseWidth = 10e-9;
    ratio = header["Pulse sep"]/pulseWidth
    for i, val in enumerate(rawArr):
        # Calaulate peak power
        pp = rawArr[i] * ratio
        ppErr = rawErr[i] * ratio
        # Calculate no of photons
        scaledArr[i] = (pp*pulseWidth) / ePh
        scaledErr[i] = (ppErr*pulseWidth) / ePh
    return scaledArr, scaledErr

def integrate(x, y):
    return np.trapz(y, dx=(x[1]-x[0]))

def calcGain(integral,width,w1,p1,p1Err,w2,p2,p2Err):
    a = np.where( w2 == width )
    if a[0].size is not 0:
        idx = np.where( w2 == width )[0][0]
        nPh = p2[idx]
        nPhErr = p2Err[idx]
    else:
        idx = np.where( w1 == width )[0][0]
        nPh = p1[idx]
        nPhErr = p1Err[idx]
    return abs(integral / (nPh*1.6e-19)), nPh, nPhErr

def straightLineEq(x1,x2,y1,y2):
    dy = y1-y2
    dx = x1-x2
    m = dy/dx
    c = y1 - m*x1
    return m,c

def calcRiseTime(x,y):
    y=np.array(y) # force to loop like numpy array
    # Find max amplitude
    index = np.argmin( y )
    upRange = 0.9*y[index]
    loRange = 0.1*y[index]
    first = np.where( y < loRange )[0][0]
    last = np.where( y < upRange )[0][0]
    m1,c1 = straightLineEq(x[(first-1)], x[first], y[(first-1)], y[first])
    m2,c2 = straightLineEq(x[(last-1)], x[last], y[(last-1)], y[last])
    time1 = (loRange - c1) / m1
    time2 = (upRange - c2) / m2
    #print time1, time2, time2-time1
    return time2-time1

def matPlot(n,x,y,yErr):
    plt.figure(num=n, figsize=(10, 8), dpi=80, facecolor='w')
    a = plt.errorbar(x,y,yErr,'x')
    a.legend()
    a.show()
    return a

def fitHist(hist, data):
    idx = np.nonzero(data)
    f1 = ROOT.TF1("f1","gaus",min(data[idx]),max(data[idx]))
    hist.Fit(f1, "RQ")
    
    pars = f1.GetParameters()
    mean, sig = pars[1], pars[2]
    return float(mean), float(sig)

def drawHist(hist, xlabel):
    hist.GetXaxis().SetTitle(xlabel)
    hist.SetStats(0)
    hist.Draw("")
    tc.Modified(); tc.Update()
    time.sleep(1)
    return 0


###############
# MAIN FUNCTION
###############
if __name__ == "__main__":
    scriptTime = time.time()

    # ROOT stuff
    ROOT.gEnv.SetValue('Canvas.SavePrecision', "16")
    tc = ROOT.TCanvas("c1","c1",800,600)

    # Set-up path
    #basePath = "/Users/el230/Data/SNO+/PMT_cal/testRun/"
    basePath = "/Users/el230/Data/SNO+/PMT_cal/TellieRange_reRun/"

    # Find what data we have saved
    widths = np.zeros(1000)
    c=0
    for i in range(0, 9000, 10):
        folder = basePath + "width_{:d}".format(i)
        if os.path.exists(folder):
            widths[c] = i
            c=c+1
    fin = np.where( widths[1:999] == 0 )[0][0]
    widths = widths[0:fin-25].astype(int)
    print widths

    # Read in power_meter data files
    head = readHeader("./power_meter/data/pin_calib_Run2.dat")
    w1, PIN_1, watts, wattsErr = readData("./power_meter/data/pin_calib_Run2.dat")
    p1, p1Err = scaling(watts, wattsErr, head)
    head = readHeader("./power_meter/data/pin_calib_Run2.dat")
    w2, PIN_2, watts, wattsErr = readData("./power_meter/data/pin_calib_TellieRange.dat")
    p2, p2Err = scaling(watts, wattsErr, head)

    # Set-up variables
    intMean, intSig = np.zeros(len(widths)), np.zeros(len(widths))
    gainMean, gainSig = np.zeros(len(widths)), np.zeros(len(widths))
    riseMean, riseSig = np.zeros(len(widths)), np.zeros(len(widths))
    noPhotons, noPhotonsSig = np.zeros(len(widths)), np.zeros(len(widths))

    # Read pulses from file, store y values in arrays
    for j, width in enumerate(widths):

        loopStart = time.time()
        # Set-up loop variables
        y = np.zeros((1000,168))
        integral, gain, riseTime = np.zeros(1000), np.zeros(1000), np.zeros(1000)
        intHist = ROOT.TH1F("intHist","Integrated PMT pulse charge", 100, -1.1e-9, -1.1e-6)
        gainHist = ROOT.TH1F("gainHist","PMT gain", 1000, 5e4, 5e6)
        riseHist = ROOT.TH1F("riseHist","LED - PMT rise time", 100, 1e-9, 3e-9)
 
        # Loop over pulses for specific width
        for i in range(0,1000):
            filePath = basePath + "width_{:d}/pulse_{:d}.dat".format(width,i)
            if os.path.exists(filePath):
                x, tmpY = get_waveform.get_waveform(filePath)
                y[i][:] = tmpY
                integral[i] = integrate(x, tmpY)
                gain[i], nPh, nPhErr = calcGain(integral[i],width,w1,p1,p1Err,w2,p2,p2Err)
                riseTime[i] = calcRiseTime(x,tmpY)
                intHist.Fill(integral[i])
                gainHist.Fill(gain[i])
                riseHist.Fill(riseTime[i])

        # Caluclate mean and uncertainties
        intMean[j], intSig[j] = fitHist(intHist, integral)
        gainMean[j], gainSig[j] = fitHist(gainHist, gain)
        riseMean[j], riseSig[j] = fitHist(riseHist, riseTime)

        noPhotons[j], noPhotonsSig[j] = nPh, nPhErr

        #drawHist(intHist, "Charge integral (eV)")
        #drawHist(gainHist, "PMT gain")
        #drawHist(riseHist, "Rise time (s)")

        print "#############################################"
        print "Width : \t{:d}\nCharge : \t{:1.3e} +/- {:1.1e} (ev)\nRise : \t\t{:1.3f} +/- {:1.3f} (ns)\nGain : \t\t{:1.3e} +/- {:1.1e}\nnPhotons : \t{:1.3e} +/- {:1.1e}".format(width, intMean[j], intSig[j], riseMean[j]*1e9, riseSig[j]*1e9,gainMean[j],gainSig[j],noPhotons[j], noPhotonsSig[j])
        print "Loop took : \t{:1.2f} s".format( (time.time()-loopStart))

        intHist.Delete()
        gainHist.Delete()
        riseHist.Delete()
    

    ######### PLOT RESULTS ##########

    matplotlib.rcParams.update({'font.size': 18})
    plt.figure(num=1, figsize=(10, 8), dpi=80, facecolor='w')
    ax = plt.errorbar(widths, gainMean*1e-5, gainSig*1e-5, marker='x')
    plt.title("Gain as a function of IPW")
    plt.xlabel("IPW (14 bit)")
    plt.ylabel("Gain (x10**5)")
    #plt.show()
    saveStr = './PMT_cal/results/GainVsIPW.png'
    plt.savefig(saveStr, dpi=100)

    plt.figure(num=2, figsize=(10, 8), dpi=80, facecolor='w')
    ax = plt.errorbar(noPhotons, gainMean*1e-5, gainSig*1e-5, marker='x')
    plt.title("Gain as a function of number of photons")
    plt.xlabel("No. Photons")
    plt.ylabel("Gain (x10**5)")
    plt.xscale('log')
    #plt.show()
    saveStr = './PMT_cal/results/GainVsPhotons.png'
    plt.savefig(saveStr, dpi=100)

    #plot = ROOT.TGraphErrors(len(widths), np.asarray(widths), gainMean, np.zeros(len(widths)), gainSig)
    #plot.SetMarkerStyle(1)
#   plot.Draw("ap")
#   plot.GetYaxis().SetRangeUser(-1e-12,2.5e-7)
#   plot.GetXaxis().SetRangeUser(0,max(widths))
#   tc.Modified(); tc.Update()
#   name = "GainVsIPW"
#   plot.SetTitle(name)
#   plot.GetXaxis().SetTitle("IPW (14 bit)")
#   plot.GetYaxis().SetTitle("Gain")
#   tc.SaveAs("./PMT_cal/results/{:s}.png".format(name));

    print "Script took : \t{:1.2f} min".format( (time.time()-scriptTime)/60 )

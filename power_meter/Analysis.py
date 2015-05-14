#####################################################
# Analysis of push pull LED driver boad intensities,
# as read by PM100USB power meter.
#
# Author: Ed Leming
# Date: 18/10/2014
#####################################################

import ROOT
from ROOT import kRed, kBlue, kWhite
import time
#import matplotlib.pyplot as plt
import numpy as np

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

def plotXY(x,y):
    
    # Plot data set
    plot = ROOT.TGraph(len(x), x, y)
    plot.SetMarkerStyle(2)
    plot.Draw("ap")
    #plot.GetYaxis().SetRangeUser(-1e-12,2.5e-7)
    plot.GetXaxis().SetRangeUser(0,max(x))
    tc.Modified(); tc.Update()
    time.sleep(5)

    return plot

def plotErr(x,y,yErr):

    # Plot data set
    plot = ROOT.TGraphErrors(len(x), x, y, np.zeros(len(x)), yErr)
    plot.SetMarkerStyle(1)
    plot.Draw("ap")
    #plot.GetYaxis().SetRangeUser(-1e-12,2.5e-7)
    plot.GetXaxis().SetRangeUser(0,max(x))
    tc.Modified(); tc.Update()

    return plot

def pol1(x, p0, p1):
    return p0 + p1*x[0]

def pol2(x, p0, p1, p2):
    return p0 + p1*x[0] + p2*(x[0]*x[0])

def fitFunc(x, par):
    return pol1(x,par[0],par[1]) + pol2(x,par[2],par[3],par[4]) + pol1(x,par[5],par[6])

def fitFunc1(x, par):
    if(x[0] <= 7100):
        print x[0]
        return pol1(x,par[0],par[1])
    if(7100 < x[0] and x[0] <= 7700):
        print x[0]
        return pol2(x,par[2],par[3],par[4])
    if(x[0] > 7700):
        print x[0], par[5], par[6]
        return pol1(x,par[5],par[6])


def lineExpFit(plot):

    #Define the fit
    f1 = ROOT.TF1("f1","pol1",6600,7100) # + [2]*exp(-x/[3])")
    f2 = ROOT.TF1("f2","pol2",7100,7700)
    f3 = ROOT.TF1("f3","pol1",7700,8200)
    total = ROOT.TF1("total","pol1(0) + pol2(2) + pol1(5)",6600,8200)
    #total = ROOT.TF1("total",fitFunc,6600,8250,7)

    f1.SetLineColor(1)
    f2.SetLineColor(1)
    f3.SetLineColor(1)
    
    # "RSQO" R flag forces range, S returns pointer to parameters, Q is 'quiet mode', N do not draw
    p1 = plot.Fit(f1, "RS")
    p2 = plot.Fit(f2, "RS+")
    p3 = plot.Fit(f3, "RS+")

    # Get parameters from sep fits
    par1 = f1.GetParameters()
    par2 = f2.GetParameters()
    par3 = f3.GetParameters()

    # Get set parameters for summed fit
    #par = np.zeros(7)
    par = total.GetParameters()
    par[0], par[1]          = par1[0], par1[1]
    par[2], par[3], par[4]  = par2[0], par2[1], par2[2]
    par[5], par[6]          = par3[0], par3[1]
    total.SetParameters(par)

    # Fit
    #pT = plot.Fit(total,"RSQM+")
    pT = plot.Fit(total,"RL+")
    
    # Write parameters to canvas
    ROOT.gStyle.SetOptFit(1111)
    stats = tc.GetPrimitive("stats")
    stats.SetTextColor(1)
    tc.Modified(); tc.Update()

    return pT


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


def calcSettings(p, noPh):

    return 0


###############
# MAIN FUNCTION
###############
if __name__ == "__main__":

    #fileName = "./data/pin_calib_Run2.dat"
    fileName = "./power_meter/data/pin_calib_Run2.dat"

    # Read file
    header = readHeader(fileName)
    widths, PIN, watts, wattsErr = readData(fileName)

    # Scale power values to give photons
    photons, photonErr = scaling(watts, wattsErr, header)

    # ROOT stuff
    tc = ROOT.TCanvas("c1","c1",800,600)
    tc.SetLogy()

    # Make basic plot
    tmpPlot = plotErr(widths,photons,photonErr)
    # Refine
    name = "PhotonsVsWidth"
    tmpPlot.SetTitle(name)
    tmpPlot.GetXaxis().SetTitle("LED pulse width (14 bit)")
    tmpPlot.GetYaxis().SetTitle("No. Photons")
    #tmpPlot.GetYaxis().SetRangeUser(0.5e4,1e6)
    #tmpPlot.GetXaxis().SetRangeUser(6000,8000)
    #pars = lineExpFit(tmpPlot)
    tc.SaveAs("./power_meter/results/{:s}.png".format(name))

    tc.SetLogy(0)
    # Make PIN plot
    tmpPlot2 = plotXY(widths,PIN)
    # Refine
    name = "PINVsWidth"
    tmpPlot2.SetTitle(name)
    tmpPlot2.GetXaxis().SetTitle("LED pulse width (14 bit)")
    tmpPlot2.GetYaxis().SetTitle("PIN reading (14 bit)")
    tc.SaveAs("./power_meter/results/{:s}.png".format(name));

    tc.SetLogx()
    tmpPlot2 = plotXY(photons,PIN)
    # Refine
    name = "PINVsPhotons"
    tmpPlot2.SetTitle(name)
    tmpPlot2.GetXaxis().SetTitle("No. Photons")
    tmpPlot2.GetYaxis().SetTitle("PIN reading (14 bit)")
    tc.SaveAs("./power_meter/results/{:s}.png".format(name));







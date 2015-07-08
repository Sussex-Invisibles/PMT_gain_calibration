##################################################
# Code to use power meter results to calibrate the
# the gain of PMT at a specfic POT setting
#
# Author: Ed Leming
# Date: 23/10/2014
##################################################
import calc_utils as calc
import sys
#import Analysis
# Standard stuff
import optparse
import time
import math
import os
import numpy as np
import scipy.optimize
import scipy.stats.distributions
import matplotlib.pyplot as plt
import matplotlib
import ROOT

def read_scope_scan(fname):
    """Read data as read out and stored to text file from the scope.
    Columns are: ipw, pin, width, rise, fall, width (again), area.
    Rise and fall are opposite to the meaning we use (-ve pulse)
    """
    fin = file(fname,'r')
    resultsList = []
    for line in fin.readlines():
        if line[0]=="#":
            continue
        bits = line.split()
        if len(bits)!=14:
            continue
        resultsList.append({"ipw":int(bits[0]),"ipw_err": int(bits[1]),"pin":int(bits[2]),"pin_err":int(bits[3]),"width":float(bits[4]),"width_err":float(bits[5]),"rise":float(bits[6]),"rise_err":float(bits[7]),"fall":float(bits[8]),"fall_err":float(bits[9]),"area":float(bits[10]),"area_err":float(bits[11]),"mini":float(bits[12]),"mini_err":float(bits[13])})
    return resultsList

def read_pin_header(fileName):
    '''Read header of power-meter data file'''
    # Open file, read only the first line
    with open(fileName, 'r') as file:
        header = file.readline()
    tmp = header.split(" ")
    # Return as dict.
    return {"Wavelength" : int(tmp[0]), "Pulse sep" : float(tmp[1]), "Rate" : int(tmp[2]), "Temp" : float(tmp[3]), "Pedestal" : float(tmp[4]) }

def read_pin_data(fileName):
    '''Read power-meter data'''
    # Find no. of lines
    noLin = sum(1 for line in open(fileName)) - 1  ###-1 to correct for header    
    # Define new arrays
    widths, PIN, PINErr = np.zeros(noLin), np.zeros(noLin), np.zeros(noLin)
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
            PINErr[c] = int(tmp[2])
            photons[c] = int(tmp[3])
            photonErr[c] = int(tmp[4])
            watts[c] = float(tmp[5])
            wattsErr[c] = float(tmp[6])
            c=c+1
    # return filled lists
    return widths, PIN, PINErr, watts, wattsErr

def get_clean_data_points(widths, gain, path):
    '''Check all data points for saturation or 0 result.'''
    index = []
    for i, g in enumerate(gain):
        file = '%s/Width%05d.pkl' % (path, widths[i])
        if os.path.isfile(file):
            x, y = calc.readPickleChannel(file, 1)
            print i, len(widths)
            if check_saturation(y) is False and gain[i] > 0:
                index.append(i)
    return index

def check_saturation(y):
    '''Check if data set is saturated'''
    counter = 0
    for i in range(len(y[:,1])):
        idx = np.where(y[i,:] == min(y[i,:]))[0]
        if len(idx) > 4:
            counter = counter + 1
        if counter > 10:
            return True
    return False

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

def calcGain(data_list, noPhotons, noPhotonsErr):
    gain, gainErr = np.zeros(len(data_list)), np.zeros(len(data_list))
    for i in range(len(data_list)):
        if data_list[i]["area"] != 0:
            gain[i] = np.abs(data_list[i]["area"]) / (noPhotons[i]*1.6e-19)
            gainErr[i] = np.abs(gain[i])*np.sqrt( (data_list[i]["area_err"]/data_list[i]["area"])**2 + (noPhotonsErr[i]/noPhotons[i])**2 )
        else:
            gain[i], gainErr[i] = 0, 0
    return gain, gainErr

def check_dir(dname):
    """Check if directory exists, create it if it doesn't"""
    direc = os.path.dirname(dname)
    try:
        os.stat(direc)
    except:
        os.mkdir(direc)
        print "Made directory %s...." % dname
    return dname

def get_num_from_str(x):
    return float(''.join(ele for ele in x if ele.isdigit() or ele == '.'))

def line_func(x, a, b):
    return a*x + b

def build_fitted_arrays(x_arr, a, b):
    '''Make y array using fitted parameters'''
    y = np.zeros(len(x_arr))
    for i, x in enumerate(x_arr):
        y[i] = line_func(x, a, b)
    return y

def fit_standard_errors(pars, cov, noPoints):
    '''Calc standard errors on fitted parameters'''
    sigma  = np.zeros(len(pars))
    for i, var in zip(range(pars), np.sqrt(np.diag(cov))):
        sigma[i] = var
    return sigma

def conf_intervals(pars, cov, noPoints, alpha=0.05):
    '''Calc confidence interval for fitted parameters'''
    # No. of degrees of freedom
    dof = max(0, noPoints - len(pars))
    # Student-t value for the dof and conf. level
    tval = scipy.stats.distributions.t.ppf(1.-alpha/2., dof)
    intervals = np.zeros((len(pars),2)) 
    i = 0
    for par, sigma in zip(pars, np.sqrt(np.diag(cov))):
        intervals[i, 0] = par - sigma*tval
        intervals[i, 1] = par + sigma*tval
        i=i+1
    return intervals

def weighted_avg_and_std(values, weights):
    """Return the weighted average and standard deviation.

    values, weights -- Numpy ndarrays with the same shape.
    """
    average = np.average(values, weights=weights)
    variance = np.average((values-average)**2, weights=weights)  # Fast and numerically precise
    return (average, np.sqrt(variance))

###############
# MAIN FUNCTION
###############
if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option("-p", dest="powerFile")
    parser.add_option("-s", dest="scopeFile")
    (options,args) = parser.parse_args()
    scriptTime = time.time()

    # ROOT stuff
    ROOT.gEnv.SetValue('Canvas.SavePrecision', "16")
    tc = ROOT.TCanvas("c1","c1",800,600)

    # Read in power_meter data file
    head = read_pin_header(options.powerFile)
    wi, PIN, PINErr, watts, wattsErr = read_pin_data(options.powerFile)
    ph, phErr = scaling(watts, wattsErr, head)

    # Read in PMT-scope data file
    pmt_data = read_scope_scan(options.scopeFile)
    g, gErr = calcGain(pmt_data, ph, phErr)
    
    # Take out bad (zero) data points
    p =  options.scopeFile.split('/')
    tmpStr = ''
    for it, direc in enumerate(p):
        if it < len(p)-1:
            tmpStr = tmpStr + '/%s' % direc
    idx = get_clean_data_points(wi, g, "%s/raw_data/Channel_08/" % (tmpStr))
    print idx
    photons, photonsErr = ph[idx], phErr[idx]
    gain, gainErr = g[idx], gErr[idx]
    widths, pin, pinErr = wi[idx], PIN[idx], PINErr[idx]

    ######### PLOT RESULTS ##########
    check_dir('results/%s/' % p[-1])
    voltage = get_num_from_str(p[-2])
    final_gain, final_gain_err = weighted_avg_and_std(gain[:-2], gainErr[:-2])
    print ######################################
    print "\nGain at %1.1fV is: %.3e +/- %.3e\n" % (voltage, final_gain, final_gain_err)
    print ######################################
    
    ### Fit stuff - doesn't always hold
    #initial_guess = [-1e-1, 1e5]
    #pars, cov = scipy.optimize.curve_fit(line_func, photons[:-2], gain[:-2], p0=initial_guess, sigma=gainErr[:-2], absolute_sigma=True)
    #intervals = conf_intervals(pars, cov, len(photons))
    #fit_x = range(0, int(max(photons)), int(max(photons)/1e4))
    #fit_y = build_fitted_arrays(fit_x, pars[0], pars[1])
    #fit_lo = build_fitted_arrays(fit_x, intervals[0,0], intervals[1,0])
    #fit_hi = build_fitted_arrays(fit_x, intervals[0,1], intervals[1,1])

    matplotlib.rcParams.update({'font.size': 18})
    plt.figure(num=1, figsize=(10, 8), dpi=80, facecolor='w')
    ax = plt.errorbar(photons[:-2], gain[:-2], gainErr[:-2], fmt = '', marker='x')
    #ax1 = plt.plot(fit_x, fit_y,'-',color='c')
    #ax.fill_between(fit_x, fit_lo, fit_hi, facecolor='yellow', alpha=0.5, label='Cl 95%') #Doens't work for errobar
    #ax2 = plt.plot(fit_x, fit_lo,'--',color='c')
    #ax3 = plt.plot(fit_x, fit_hi,'--',color='c', label='Cl 95%')
    plt.title("Gain as a function of photons")
    plt.xlabel("No. Photons")
    plt.ylabel("Gain")
    text_str = "           Gain:\nmean = %.3e\nsigma = %.3e" % (final_gain, final_gain_err)
    axis = plt.gca()
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    axis.text(0.65, 0.95, text_str, transform=axis.transAxes, fontsize=14,verticalalignment='top', bbox=props)
    saveStr = 'results/%s/GainVsPhotons.png' % p[-1]
    plt.savefig(saveStr, dpi=100)

    plt.figure(num=2, figsize=(10, 8), dpi=80, facecolor='w')
    ax = plt.errorbar(widths, gain, gainErr, fmt = '', marker='x')
    plt.title("Gain as a function of IPW")
    plt.xlabel("IPW (14 bit)")
    plt.ylabel("Gain")
    #plt.show()                                                                                                                         
    saveStr = 'results/%s/GainVsIPW.png' % p[-1]
    plt.savefig(saveStr, dpi=100)

    plt.figure(num=3, figsize=(10, 8), dpi=80, facecolor='w')
    ax = plt.errorbar(pin[:-2], photons[:-2], photonsErr[:-2], fmt = '', marker='x')
    plt.title("PIN reading as a function of photons")
    plt.xlabel("PIN (16 bit)")
    plt.ylabel("No. photons")
    plt.legend()
    saveStr = 'results/%s/PINVsPhotons.png' % p[-1]
    plt.savefig(saveStr, dpi=100)

    plt.figure(num=4, figsize=(10, 8), dpi=80, facecolor='w')
    ax = plt.errorbar(wi, PIN, PINErr, fmt='', marker='x')
    plt.title("IPW as a function of PIN readout")
    plt.xlabel("IPW (14 bit)")
    plt.ylabel("PIN (16 bit)")
    plt.legend()
    saveStr = 'results/%s/IPWVsPIN.png' % p[-1]
    plt.savefig(saveStr, dpi=100)

    print "Script took : \t{:1.2f} min".format( (time.time()-scriptTime)/60 )

# PMT_gain_calibration
Code to calibrate PMT gain using a Thorlabs PMT100USB powermeter

### env.sh
An environment file to set-up library paths used with this arrangement.

### powermeter/PowerCal.py
Script to interface with a PMT100USB powermeter, recording power readings for a full range of TELLIE IPW settings.
Results are stored in a text file in the ./data directory, created realtive to whichever directory the script was called 
from.

### powermeter/Analysis.py
Generates plots using the data file created with the PowerCal.py script above. 

### PMT_cal/sweep_and_acquire.py
Script to acquire PMT data using a Tektronix DPO/MSO3000 'scope. The datafile created in powermeter/PowerCal.py is used
to define the range of TELLIE IPW settings required. Additional libraries from 'Sussex-Invisibles' repository are required.

### PMT_cal/calibrate.py
Generate and fit plots using the data recorded using sweep_and_acquire.py.

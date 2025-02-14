# Open-Meteo-Weather-Models
## Overview

The python code here is open_meteo.py. It uses the Open Meteo Weather Forecast API to download model data for a point and create time-series plots. The other html files are examples of what the code creates.

Forecast plots updating in real-time for Albany, NY can be found [here](https://jnocera3.github.io/Open-Meteo-Weather-Models/Albany_forecast.html)

More info on the Open Meteo Weather Forecast API can be found [here](https://open-meteo.com/en/docs)

## Installation

```
git clone https://github.com/jnocera3/Open-Meteo-Weather-Models.git
```

## Dependencies
```
pip install openmeteo-requests
pip install requests-cache retry-requests numpy pandas
pip install GitPython
pip install plotly[express]
```

## Running the code
```
python open_meteo.py -h
usage: open_meteo.py [-h] [-location LOCATION] [-lat LAT] [-lon LON] [-git]

optional arguments:
  -h, --help            show this help message and exit
  -location LOCATION, --location LOCATION
                        Name of Location for outut purposes
  -lat LAT, --lat LAT   Latitude of location
  -lon LON, --lon LON   Longitude of location
  -git, --git           Enable git update
```

The code can be run with no arguments. Right now it is set to extract data for Albany, NY. The code can easily be modified to change the default location. 

To run the code to extract for any location, example Chicago (ORD):
```
python open_meteo.py -location Chicago -lat 41.9803 -lon -87.9090
```
After running the code a bunch of html files will be created. The one to view is $location_forecast.html. This page enables selecting the plots to display.

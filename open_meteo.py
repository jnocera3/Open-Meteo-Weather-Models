#!/usr/bin/python
import openmeteo_requests
import requests_cache
import argparse
import pandas as pd
import numpy as np
import shutil
import plotly.express as px
from datetime import datetime, timezone, timedelta
from retry_requests import retry

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Argument Parsing
parser = argparse.ArgumentParser()

# Read in arguments
parser.add_argument("-location","--location", required=False, default="Albany", help='Name of Location for outut purposes')
parser.add_argument("-lat","--lat", required=False, default=42.6526, help='Latitude of location')
parser.add_argument("-lon","--lon", required=False, default=-73.7562, help='Longitude of location')

# Parse the input
args = parser.parse_args()

# Store the date as datetime object
location = args.location
lat = args.lat
lon = args.lon

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
url = "https://api.open-meteo.com/v1/forecast"
params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["temperature_2m", "dew_point_2m", "precipitation_probability", "precipitation", "snowfall", "pressure_msl", "cloud_cover", "wind_speed_10m", "wind_direction_10m"],
        "varnames": ["2m Temp (deg F)", "2m Dewp (deg F)", "PoP (%)", "Hourly Precip (in)", "Hourly Snow (in)", "MSLP (mb)", "Cloud Cover (%)", "10m WSpd (kts)", "10m WDir (deg)"],
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "kn",
        "precipitation_unit": "inch",
        "timezone": "America/New_York",
    "models": ["ecmwf_ifs025", "ecmwf_aifs025", "gfs_global", "gfs_hrrr", "gfs_graphcast025", "ncep_nbm_conus", "jma_seamless", "icon_seamless", "gem_seamless", "meteofrance_arpege_world", "ukmo_seamless"],
    "modelnames": ["ECMWF", "ECMWF-AI", "GFS", "HRRR", "Google-AI", "NBM", "JMA", "ICON", "GEM", "ARPEGE", "UKMET"]
}

# Function to create html navigation file from Template
def create_nav_file(navfile, old_string, new_string):
    try:
        with open(navfile, 'r') as file:
            content = file.read()
    except FileNotFoundError:
        print(f"Error: File not found: {navfile}")
        return

    modified_content = content.replace(old_string, new_string)

    with open(navfile, 'w') as file:
        file.write(modified_content)

# Get current time rounded to next hour
current_time = datetime.now(timezone.utc)
current_time = current_time.strftime("%Y%m%d/%H%M UTC")

# Grab model data
responses = openmeteo.weather_api(url, params=params)

# Add timestamps to dictionary
hourly_data = {"date/time (UTC)": pd.date_range(
        start = pd.to_datetime(responses[0].Hourly().Time(), unit = 's', utc = True),
        end = pd.to_datetime(responses[0].Hourly().TimeEnd(), unit = 's', utc = True),
        freq = pd.Timedelta(seconds = responses[0].Hourly().Interval()),
        inclusive = "left"
)}

# Get first forecast time = current time rounded to next hour
first_forecast_time = datetime.now(timezone.utc).replace(second=0, microsecond=0, minute=0) + timedelta(hours=1)

# Initialize hourly data dictionary
hourly = {}

# Loop over variables
ivar=0
for var in params["hourly"]:
    # Store dictionary of dataframes by variable
    hourly[var] = pd.DataFrame(data = hourly_data)
    # Add cumulative precip variables
    if var == "precipitation":
        hourly["total_qpf"] = pd.DataFrame(data = hourly_data)
        hourly["frozen_qpf"] = pd.DataFrame(data = hourly_data)
        hourly["total_frozen_qpf"] = pd.DataFrame(data = hourly_data)
    elif var == "snowfall":
        hourly["total_snow"] = pd.DataFrame(data = hourly_data)
    # Loop over models
    imodel=0
    for model in params["modelnames"]:
        # Add data to dataframe
        model_data = pd.DataFrame()
        model_data[model] = responses[imodel].Hourly().Variables(ivar).ValuesAsNumpy()
        hourly[var] = pd.concat([hourly[var],model_data[model]],axis=1)
        # For snowfall base ratio on temperature: 32 = 9/1, 20F = 15/1
        if var == "snowfall":
            mask = hourly[var][model] > 0
#           hourly[var][model] = hourly["precipitation"][model] *  10 * mask
#           hourly[var][model] = hourly["precipitation"][model] * (23.333312 - 0.416666 * hourly["temperature_2m"][model]) * mask
            hourly[var][model] = hourly["precipitation"][model] * (25.0 - 0.5 * hourly["temperature_2m"][model]) * mask
        # Frozen precip is precip when temp is <=32 F
        elif var == "precipitation":
            mask = hourly["temperature_2m"][model] <= 32
            hourly["frozen_qpf"][model] = hourly[var][model] * mask
            hourly["frozen_qpf"][model] = hourly["frozen_qpf"][model].astype(float)
        imodel+=1
    print(var)
    # Remove past times from dataframe
    hourly[var] = hourly[var][hourly[var]['date/time (UTC)'] >= first_forecast_time]
    # Add ensemble mean
    hourly[var]["Mean"] = hourly[var].drop("NBM",axis=1).mean(axis=1,numeric_only=True)
    # Round decimal places depending on variable
    if var == "precipitation_probability" or var == "cloud_cover" or var == "wind_direction_10m":
        for model in params["modelnames"]:
            hourly[var][model] = hourly[var][model].round(0)
        hourly[var]["Mean"] = hourly[var]["Mean"].round(0)
    elif var == "temperature_2m" or var == "dew_point_2m" or var == "snowfall" or var == "wind_speed_10m" or var == "pressure_msl":
        for model in params["modelnames"]:
            hourly[var][model] = hourly[var][model].round(1)
        hourly[var]["Mean"] = hourly[var]["Mean"].round(1)
    elif var == "precipitation":
        for model in params["modelnames"]:
            hourly[var][model] = hourly[var][model].round(2)
        hourly[var]["Mean"] = hourly[var]["Mean"].round(2)
        # Set up frozen qpf dataframe
        hourly["frozen_qpf"] = hourly["frozen_qpf"][hourly["frozen_qpf"]['date/time (UTC)'] >= first_forecast_time]
        hourly["frozen_qpf"]["Mean"] = hourly["frozen_qpf"].drop("NBM",axis=1).mean(axis=1,numeric_only=True)
        for model in params["modelnames"]:
            hourly["frozen_qpf"][model] = hourly["frozen_qpf"][model].round(2)
        hourly["frozen_qpf"]["Mean"] = hourly["frozen_qpf"]["Mean"].round(2)
    # Plot data
    plot_title = params["varnames"][ivar] + ' Forecast for ' + location + "<br>Updated: " + str(current_time)
    fig = px.line(hourly[var], x='date/time (UTC)', y=hourly[var].columns, title=plot_title, markers=True, color_discrete_map={"Mean": "black"})
    fig.update_traces(mode="markers+lines", hovertemplate=None)
    fig.update_layout(xaxis_title="Time/Date (UTC)", yaxis_title=None, legend_title_text="Models", hovermode="x unified", title_x=0.5)
    fig.update_xaxes(dtick="H12", tickformat="%HZ\n%m-%d")
    fig['data'][11]['line']['width'] = 4
    # Define name of output file
    out_file = location + "_" + var + "_forecast.html"
    fig.write_html(out_file)
    # Add cumulative snowfall dataframe
    if var == "snowfall":
        hourly["total_snow"] = hourly[var].drop("date/time (UTC)",axis=1).cumsum(axis=0)
        hourly["total_snow"]["date/time (UTC)"] = hourly[var]["date/time (UTC)"]
        for model in params["modelnames"]:
            hourly["total_snow"][model] = hourly["total_snow"][model].round(1)
        hourly["total_snow"]["Mean"] = hourly["total_snow"]["Mean"].round(1)
    # Add cumulative qpf and cumulative frozen qpf dataframe
    elif var == "precipitation":
        # Total QPF
        hourly["total_qpf"] = hourly[var].drop("date/time (UTC)",axis=1).cumsum(axis=0)
        hourly["total_qpf"]["date/time (UTC)"] = hourly[var]["date/time (UTC)"]
        for model in params["modelnames"]:
            hourly["total_qpf"][model] = hourly["total_qpf"][model].round(2)
        hourly["total_qpf"]["Mean"] = hourly["total_qpf"]["Mean"].round(2)
        # Total Frozen QPF
        hourly["total_frozen_qpf"] = hourly["frozen_qpf"].drop("date/time (UTC)",axis=1).cumsum(axis=0)
        hourly["total_frozen_qpf"]["date/time (UTC)"] = hourly["frozen_qpf"]["date/time (UTC)"]
        for model in params["modelnames"]:
            hourly["total_frozen_qpf"][model] = hourly["total_frozen_qpf"][model].round(2)
        hourly["total_frozen_qpf"]["Mean"] = hourly["total_frozen_qpf"]["Mean"].round(2)
    ivar+=1

# Create additional plots for frozen qpf, cumulative snowfall, qpf and frozen qpf
for var in ["frozen_qpf", "total_qpf", "total_snow", "total_frozen_qpf"]:
    # Plot data
    if var == "total_qpf":
        plot_title = 'Total Precip (in) Forecast for ' + location + "<br>Updated: " + str(current_time)
    elif var == "total_snow":
        plot_title = 'Total Snow (in) Forecast for ' + location + "<br>Updated: " + str(current_time)
    elif var == "frozen_qpf":
        plot_title = 'Hourly Frozen Precip (in) Forecast for ' + location + "<br>Updated: " + str(current_time)
    elif var == "total_frozen_qpf":
        plot_title = 'Total Frozen Precip (in) Forecast for ' + location + "<br>Updated: " + str(current_time)
    fig = px.line(hourly[var], x='date/time (UTC)', y=hourly[var].columns, title=plot_title, markers=True, color_discrete_map={"Mean": "black"})
    fig.update_traces(mode="markers+lines", hovertemplate=None)
    fig.update_layout(xaxis_title="Time/Date (UTC)", yaxis_title=None, legend_title_text="Models", hovermode="x unified", title_x=0.5)
    fig.update_xaxes(dtick="H12", tickformat="%HZ\n%m-%d")
    fig['data'][11]['line']['width'] = 4
    # Define name of output file
    out_file = location + "_" + var + "_forecast.html"
    fig.write_html(out_file)

# Create navigation file from template
template_file = "Template_forecast.html"
out_file = location + "_forecast.html"
shutil.copyfile(template_file, out_file)
create_nav_file(out_file,"Template",location)
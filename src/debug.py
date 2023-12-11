import pandas as pd
import numpy as np
import pytz
import re
from datetime import datetime, timedelta
import googlemaps
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, callback

# Google Maps API initialization
gmaps = googlemaps.Client(key='AIzaSyCRFJ3g0ifIADm4l_IWw4sEXv4XdDeP3d8')

# Constants
NIH_ADDRESS = "Medical Center, Bethesda, MD 20894, United States"
SMITHSONIAN_ADDRESS = "10th St. & Constitution Ave. NW, Washington, DC 20560"
DATA_FILE = "/Users/szufan/PropertyRankings/src/data/test.csv"

# Utility Functions
def to_eastern_time(local_time):
    """Convert local time to Eastern Time."""
    eastern = pytz.timezone('US/Eastern')
    return local_time.astimezone(eastern)

def convert_time_to_minutes(time_str):
    """Convert a time string to minutes."""
    if not time_str or not isinstance(time_str, str):
        return np.nan
    time_pattern = re.compile(r'(?:(\d+)\s+hour[s]?)?\s*(?:(\d+)\s+min[s]?)?')
    match = time_pattern.search(time_str)
    if not match:
        return np.nan
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    return hours * 60 + minutes

# Data Loading
def load_data(data_file):
    """Load data from a CSV file."""
    return pd.read_csv(data_file)

# Payment Calculation
def calculate_monthly_payment(price, annual_tax, hoa, monthly_interest_rate, total_payments):
    """Calculate monthly payment."""
    monthly_tax = annual_tax / 12 if annual_tax > 0 else 0
    total_loan_amount = price + monthly_tax + hoa
    if monthly_interest_rate > 0:
        return total_loan_amount * (monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments) / ((1 + monthly_interest_rate) ** total_payments - 1)
    return total_loan_amount / total_payments

def calculate_payments(df, annual_interest_rate=0.068, loan_term_years=30):
    """Calculate payments for all rows in a DataFrame."""
    monthly_interest_rate = annual_interest_rate / 12.0
    total_payments = loan_term_years * 12
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
    df['Annual tax'] = pd.to_numeric(df['Annual tax'], errors='coerce')
    df['HOA'] = pd.to_numeric(df['HOA'], errors='coerce')
    df['Payment'] = df.apply(lambda row: calculate_monthly_payment(row['Price'], row['Annual tax'], row['HOA'], monthly_interest_rate, total_payments), axis=1)
    return df

# Travel Time Calculation
def calculate_travel_time(gmaps, origin, destination, departure_time):
    """Calculate travel time using Google Maps API."""
    if departure_time is None:
        departure_time = datetime.now()
    departure_time_et = to_eastern_time(departure_time)
    directions_result = gmaps.directions(origin, destination, mode="transit", departure_time=departure_time_et)
    if directions_result:
        return directions_result[0]['legs'][0]['duration']['text']
    return "No data"

def calculate_travel_time_and_walking_distance(gmaps, origin, destination, departure_time):
    """Calculate travel time and walking distance using Google Maps API."""
    directions_result = gmaps.directions(origin, destination, mode="transit", departure_time=departure_time)
    if directions_result:
        travel_time = directions_result[0]['legs'][0]['duration']['text']
        total_walking_distance = sum(step['distance']['value'] for step in directions_result[0]['legs'][0]['steps'] if step['travel_mode'] == 'WALKING')
        return travel_time, total_walking_distance
    return "No data", 0

# Score Calculation
def calculate_score(df):
    """Calculate score based on weighted criteria."""
    max_payment = df['Payment'].max()
    min_sq_ft = df['Size'].min()
    max_distance_to_metro = df['Metro'].max()
    max_commute_time = df['Commute'].max()
    max_transit_time_to_museums = df['Time to Smithsonian'].max()
    df['Normalized Monthly Payment'] = 1 - (df['Payment'] / max_payment)
    df['Normalized Sq. Ft.'] = (df['Size'] - min_sq_ft) / (df['Size'].max() - min_sq_ft)
    df['Normalized Distance to Metro'] = 1 - (df['Metro'] / max_distance_to_metro)
    df['Normalized Commute Time'] = 1 - (df['Commute'] / max_commute_time)
    df['Normalized Transit Time to DC Museums'] = 1 - (df['Time to Smithsonian'] / max_transit_time_to_museums)
    df['Score'] = (0.25 * df['Normalized Monthly Payment']) + (0.25 * df['Normalized Sq. Ft.']) + (0.20 * df['Normalized Distance to Metro']) + (0.20 * df['Normalized Commute Time']) + (0.10 * df['Normalized Transit Time to DC Museums'])
    return df

# Main Execution
if __name__ == "__main__":
    df = load_data(DATA_FILE)
    df = calculate_payments(df)

    current_time = datetime.now(pytz.timezone('Australia/Sydney'))
    weekday_morning_et = to_eastern_time(current_time + timedelta((2 - current_time.weekday() + 7) % 7)).replace(hour=8, minute=0, second=0, microsecond=0)
    df['Travel Info'] = df['Address'].apply(lambda x: calculate_travel_time_and_walking_distance(gmaps, x, NIH_ADDRESS, weekday_morning_et))
    df['Time to NIH'] = df['Travel Info'].apply(lambda x: x[0])
    df['Metro'] = df['Travel Info'].apply(lambda x: x[1])
    df.drop('Travel Info', axis=1, inplace=True)

    weekday_evening_et = to_eastern_time(current_time + timedelta((2 - current_time.weekday() + 7) % 7)).replace(hour=18, minute=0, second=0, microsecond=0)
    df['Time from NIH'] = df['Address'].apply(lambda x: calculate_travel_time(gmaps, NIH_ADDRESS, x, weekday_evening_et))
    df['Time to NIH'] = df['Time to NIH'].apply(convert_time_to_minutes)
    df['Time from NIH'] = df['Time from NIH'].apply(convert_time_to_minutes)
    df['Commute'] = (df['Time from NIH'] + df['Time to NIH']) / 2

    next_saturday_et = to_eastern_time(current_time + timedelta((5 - current_time.weekday() + 7) % 7)).replace(hour=11, minute=0, second=0, microsecond=0)
    df['Time to Smithsonian'] = df['Address'].apply(lambda x: calculate_travel_time(gmaps, x, SMITHSONIAN_ADDRESS, next_saturday_et))
    df['Time to Smithsonian'] = df['Time to Smithsonian'].apply(convert_time_to_minutes)

    df = calculate_score(df)
    print(df)

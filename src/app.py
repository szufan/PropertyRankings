import pathlib
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, State, callback
import dash_uploader as du
import io
import base64
import googlemaps
from datetime import datetime, timedelta
import pytz
import numpy as np
import re
from google.cloud import secretmanager

def access_secret_version(project_id, secret_id, version_id):
    """
    Access the payload for the given secret version if one exists.
    The version can be a version number as a string (e.g. "5") or an
    alias (e.g. "latest").
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

# Use your Google Cloud Project ID, secret ID, and version
project_id = "maps-407800"
secret_id = "google-api-key"
version_id = "latest"  # Can be "latest" or a specific version number

api_key = access_secret_version(project_id, secret_id, version_id)

app = Dash(__name__, title="Property Rankings")

server = app.server

# Constants
NIH_ADDRESS = "Medical Center, Bethesda, MD 20894, United States"
SMITHSONIAN_ADDRESS = "10th St. & Constitution Ave. NW, Washington, DC 20560"
DATA_FILE = "data/test.csv"

# Create a custom color palette inspired by Wes Anderson aesthetics with 15 colors
wes_anderson_palette = [
    "#EC6D71", "#FAC18E", "#9BCCB9", "#CCC3A0", "#70A9A1",
    "#FFD700", "#CD7F32", "#536872", "#FF6F61", "#C84A4D",
    "#A8A7A7", "#CCD7D4", "#D8A499", "#A89F91", "#ACD8AA"
]

# Initialize Google Maps client
gmaps = googlemaps.Client(key=api_key)

# Function to load data
def load_data(data_file: str = "test.csv") -> pd.DataFrame:
    PATH = pathlib.Path(__file__).parent
    DATA_PATH = PATH.joinpath("data").resolve()

def parse_contents(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in content_type:
            # Assume that the user uploaded a CSV
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
            return df
    except Exception as e:
        print(e)
        return None

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

def calculate_monthly_payment(price, annual_tax, hoa, annual_interest_rate, loan_term_years):
    """Calculate monthly mortgage payment including taxes and HOA fees."""
    # Calculate the loan amount (80% of the property price)
    loan_amount = price * 0.8

    # Convert annual interest rate to monthly and total number of payments
    monthly_interest_rate = annual_interest_rate / 12
    total_payments = loan_term_years * 12

    # Monthly mortgage payment calculation
    if monthly_interest_rate > 0:
        monthly_mortgage_payment = loan_amount * (monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments) / ((1 + monthly_interest_rate) ** total_payments - 1)
    else:
        monthly_mortgage_payment = loan_amount / total_payments

    # Add monthly property tax and HOA fees
    monthly_tax = annual_tax / 12
    total_monthly_payment = monthly_mortgage_payment + monthly_tax + hoa

    return total_monthly_payment

def calculate_payments(df, annual_interest_rate=0.068, loan_term_years=30):
    """Calculate payments for all rows in a DataFrame."""
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
    df['Annual tax'] = pd.to_numeric(df['Annual tax'], errors='coerce')
    df['HOA'] = pd.to_numeric(df['HOA'], errors='coerce')
    df['Payment'] = df.apply(lambda row: calculate_monthly_payment(row['Price'], row['Annual tax'], row['HOA'], annual_interest_rate, loan_term_years), axis=1)
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

def minutes_to_hours_minutes(total_minutes):
    """Convert minutes to a 'hours and minutes' string format."""
    if pd.isna(total_minutes):
        return None

    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{int(hours)} hours {int(minutes)} mins" if hours else f"{int(minutes)} mins"


# Function to create the description text
def create_description_text():
    return [
        html.P("This application assists in evaluating real estate properties by ranking them based on a set of weighted criteria. Each criterion is calculated with specific assumptions:"),
        html.Ul([
            html.Li([html.Strong("Estimated Monthly Payment:"), " Calculated considering the price, annual tax, and HOA fees, giving lower payments higher scores (25%)."]),
            html.Li([html.Strong("Property Size:"), " Based on the square footage of the property, with larger sizes scoring higher (25%)."]),
            html.Li([html.Strong("Proximity to Metro Stations:"), " Measured by the distance to the nearest metro stop, with closer distances scoring higher (20%)."]),
            html.Li([html.Strong("Commute Time:"), " Calculated using Google Maps API to estimate commute time to key locations, with shorter times scoring higher (20%)."]),
            html.Li([html.Strong("Transit Time to DC Museums:"), " Also calculated via Google Maps API, focusing on transit time to major DC museums, where shorter times score higher (10%)."])
        ])
    ]

app.layout = html.Div([
    dcc.Graph(id='graph-id'),
    html.Div(id='copyable-url'),
    html.Div(create_description_text(), style={'margin-top': '20px', 'font-family': 'Arial, sans-serif'}),
    
    html.Div([
        dcc.Upload(
            id='upload-data', 
            children=html.Button('Upload CSV'), 
            multiple=False,
            style={'margin-top': '20px', 'margin-bottom': '20px'}  # Adjust the top and bottom margins
        ),
        html.A(
            "Download CSV Template",
            href="https://docs.google.com/spreadsheets/d/1nVribTQGQDjxDtSQkET6gy5bZvRm50UirCkelaH5Wq0/edit?usp=sharing",
            target="_blank"
        )
    ])
])

@app.callback(
    Output('graph-id', 'figure'),
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')]
)

def update_graph(contents, filename):
    # Load and process data
    df = load_data(DATA_FILE)
    
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
    
    df = calculate_payments(df)
    
    df = calculate_score(df)

    df['Time to Smithsonian'] = df['Time to Smithsonian'].apply(minutes_to_hours_minutes)

    # Sort the DataFrame by 'Score'
    df_sorted = df.sort_values(by="Score", ascending=False)

    # Create hover text
    hover_text = [
        f"<b>Address:</b> {address}<br>"
        f"<b>Est. Monthly Payment:</b> ${payment:,.2f}<br>"
        f"<b>Size:</b> {size} sqft<br>"
        f"<b>Nearest Metro stop:</b> {metro} meters<br>"
        f"<b>Avg. commute to NIH:</b> {commute} mins<br>"
        f"<b>Time to museum campus:</b> {city}"
        for address, payment, size, metro, commute, city in zip(df_sorted["Address"], df_sorted["Payment"], df_sorted["Size"], df_sorted["Metro"], df_sorted["Commute"], df_sorted["Time to Smithsonian"])
    ]

    # Create the figure
    fig = go.Figure(data=[
        go.Bar(
            y=df_sorted['Score'], 
            hovertext=hover_text, 
            marker_color=wes_anderson_palette[:len(df_sorted)],  # Apply Wes Anderson color palette
            customdata=df_sorted["Link"].tolist()  # Add URLs as customdata
        )
    ])

    # Set the title and layout configuration
    fig.update_layout(
        title="Property Rankings (Descending Order)",
        xaxis=dict(
            title="Ranking",
            range=[0.5, len(df_sorted.index) + 0.5]  # Adjusting the x-axis range to start at 1
        ),
        yaxis_title="Score"
    )

    return fig

@app.callback(
    Output('copyable-url', 'children'),
    [Input('graph-id', 'clickData')]
)
def display_url(clickData):
    if clickData and 'points' in clickData and 'customdata' in clickData['points'][0]:
        url = clickData['points'][0]['customdata']
        if url:
            return html.A(href=url, children="Go to listing", target='_blank')
    return "Click on a bar to activate the listing URL"

if __name__ == "__main__":
    app.run_server(debug=True)

import pathlib
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output
import plotly.express as px

app = Dash(__name__, title="Property Rankings")

# Declare server for Heroku deployment. Needed for Procfile.
server = app.server

# Function to load data
def load_data(data_file: str) -> pd.DataFrame:
    PATH = pathlib.Path(__file__).parent
    DATA_PATH = PATH.joinpath("data").resolve()
    return pd.read_csv(DATA_PATH.joinpath(data_file))

# Load your data
df = load_data("homes_plot.csv")
df_sorted = df.sort_values(by="Score", ascending=False)

# Data mapping ID to Address
id_to_address = {
    "A": "10401 Grosvenor Pl., Rockville, MD 20852",
    "B": "1115 Gilbert Rd., Rockville, MD 20851",
    "C": "11801 Rockville Pike, Rockville, MD 20852",
    "D": "10500 Rockville Pike, Rockville, MD 20852",
    "E": "10715 Hampton Mill Ter., Rockville, MD 20852",
    "F": "5821 Edson Ln., Rockville, MD 20852",
    "G": "1201 Edmonston Dr., Rockville, MD 20851",
    "H": "4600 Connecticut Ave NW, Washington, DC 20008",
    "I": "4301 Military Rd NW #609, Washington, DC 20015",
    "J": "5305 Connecticut Ave NW #2, Washington, DC 20015",
    "K": "4515 Willard Ave Unit 1701S, Chevy Chase, MD 20815",
    "L": "5500 Friendship Blvd Unit 2303N Chevy Chase, MD 20815",
    "M": "3041 Sedgwick St NW Unit 403D, Washington, DC 20008",
    "N": "3001 Veazey Ter NW #213, Washington, DC 20008",
    "O": "3001 Veazey Ter NW #1405, Washington, DC 20008"
}

# Convert the "Payment" column to numerical values
df_sorted["Payment"] = df_sorted["Payment"].str.replace("$", "", regex=False).str.replace(",", "", regex=False).astype(float)

# Create a custom color palette inspired by Wes Anderson aesthetics with 15 colors
wes_anderson_palette = [
    "#EC6D71", "#FAC18E", "#9BCCB9", "#CCC3A0", "#70A9A1",
    "#FFD700", "#CD7F32", "#536872", "#FF6F61", "#C84A4D",
    "#A8A7A7", "#CCD7D4", "#D8A499", "#A89F91", "#ACD8AA"
]

# Create hover text
hover_text = [
    f"<b>Address:</b> {id_to_address[id]}<br>"
    f"<b>Est. Monthly Payment:</b> ${payment:,.2f}<br>"
    f"<b>Size:</b> {size} sqft<br>"
    f"<b>Nearest Metro stop:</b> {metro} meters<br>"
    f"<b>Avg. commute to NIH:</b> {commute} mins<br>"
    f"<b>Time to museum campus:</b> {city}"
    for id, payment, size, metro, commute, city in zip(df_sorted["ID"], df_sorted["Payment"], df_sorted["Size"], df_sorted["Metro"], df_sorted["Commute"], df_sorted["City"])
]

# Create the Plotly figure
fig = go.Figure()
fig.add_trace(go.Bar(
    x=df_sorted["ID"],
    y=df_sorted["Score"],
    hovertext=hover_text,
    marker_color=wes_anderson_palette,
    customdata=df_sorted["Link"]
))

# Set the title in the figure layout
fig.update_layout(
    title="Property Rankings (Descending Order)",
    xaxis_title="ID",
    yaxis_title="Score",
    clickmode='event+select'
)

# Description text explaining the ranking criteria
description_text = [
    html.P("Properties were ranked based on the following weighted criteria:"),
    html.Li("Lowest est. monthly payment (25%)"),
    html.Li("Highest sq. ft. (25%)"),
    html.Li("Closest distance to Metro stop (20%)"),
    html.Li("Shortest commute time (20%)"),
    html.Li("Shortest transit time to DC museums (10%)"),
]

# App layout
app.layout = html.Div([
    dcc.Graph(id='graph-id', figure=fig),
    html.Div(id='copyable-url'),
    html.Div([html.H4("Ranking Criteria:"), *description_text], 
             style={'margin-top': '20px', 'font-family': 'Arial, sans-serif'})
])

@app.callback(
    Output('copyable-url', 'children'),
    [Input('graph-id', 'clickData')]
)
def display_url(clickData):
    if clickData is not None:
        url = clickData['points'][0]['customdata']
        return html.A(href=url, children="Go to listing", target='_blank')
    else:
        return "Click on a bar to activate the listing URL"

if __name__ == "__main__":
    app.run_server(debug=True)

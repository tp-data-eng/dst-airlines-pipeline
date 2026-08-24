import plotly.express as px

def generate_flight_map(df, target_airports):
    # Filter after relevant flights
    df = df[
        df['dep_icao'].isin(target_airports) |
        df['arr_icao'].isin(target_airports)
    ].copy()

    # Drop rows without coordinates
    df_plot = df.dropna(subset=['aircraft_latitude', 'aircraft_longitude']).copy()

    # Fill missing schedules and telemetry with 'N/A' for a cleaner look
    cols_to_fill = ['scheduled_dep_time', 'scheduled_arr_time', 'aircraft_altitude', 'aircraft_speed']
    df_plot[cols_to_fill] = df_plot[cols_to_fill].fillna('N/A')

    # Remove the 'T' from the Timestamps
    df_plot['scheduled_dep_time'] = df_plot['scheduled_dep_time'].astype(str).str.replace('T', ' ')
    df_plot['scheduled_arr_time'] = df_plot['scheduled_arr_time'].astype(str).str.replace('T', ' ')

    def categorize_flight(row):
        if row['arr_icao'] in target_airports:
            return f"Inbound {row['arr_icao']}"
        elif row['dep_icao'] in target_airports:
            return f"Outbound {row['dep_icao']}"
        return "Other"

    # Apply categorizer
    df_plot['flight_category'] = df_plot.apply(categorize_flight, axis=1)

    route_colors = {
        "Inbound EGLL": "#00E5FF",  # Neon Cyan
        "Outbound EGLL": "#FF007F", # Bright Pink

        "Inbound LFPG": "#39FF14",  # Neon Green
        "Outbound LFPG": "#FF9900", # Orange

        "Inbound LTFM": "#FFFF00",  # Yellow
        "Outbound LTFM": "#9D00FF", # Neon Purple

        "Other": "#555555"          # Gray
    }

    fig = px.scatter_mapbox(
        df_plot,
        lat="aircraft_latitude",
        lon="aircraft_longitude",
        hover_name="reg_number",
        hover_data=[
            "flight_number",
            "dep_icao",
            "arr_icao",
            "scheduled_dep_time",
            "scheduled_arr_time",
            "aircraft_altitude",
            "aircraft_speed"
        ],
        color="flight_category",
        color_discrete_map=route_colors,
        zoom=4,
        mapbox_style="carto-darkmatter",
        title=(
            "Live Aircraft Positions<br>"
            "<i><sup>Inbound & Outbound: London Heathrow (EGLL), Paris-Charles-de-Gaulle (LFPG), Istanbul (LTFM)</sup></i>"
        ),
        labels={
            "flight_category": "Flight Route",
            "arr_icao": "Arr. Airport",
            "dep_icao": "Dep. Airport",
            "flight_number": "Flight No.",
            "aircraft_altitude": "Altitude (m)",
            "aircraft_speed": "Speed (km/h)",
            "scheduled_dep_time": "Sch. Departure",
            "scheduled_arr_time": "Sch. Arrival"

        }
    )

    # Force Plotly to use a HTML card format
    fig.update_traces(
        hovertemplate=(
            "<span style='color: black;'>"
            "<b>Registration: %{hovertext}</b><br><br>"
            "<b>Flight No.: %{customdata[0]}<br>"
            "<b>Route: %{customdata[1]} ➔ %{customdata[2]}<br>"
            "<b>Sch. Departure: %{customdata[3]}<br>"
            "<b>Sch. Arrival: %{customdata[4]}<br>"
            "<b>Altitude: %{customdata[5]}<br>"
            "<b>Speed: %{customdata[6]} km/h"
            "</span>"
            "<extra></extra>"  # Hides the redundant side-box
        )
    )

    # Position the legend horizontally at the top of the map
    fig.update_layout(
        legend_font_color="black",  # Legend Font Color
        legend=dict(
            orientation="h",
            yanchor="top",
            y=0.98,             # just slightly below the very top
            xanchor="center",
            x=0.5,              # centers it horizontally
            bgcolor="rgba(255, 255, 255, 0.8)",   # White background
            title_text=""       # Hides the "Flight Route" title to save horizontal space
        )
    )

    # Save the interactive map as a standalone webpage
    # 'cdn'-argument shrinks the file size by ~90% and fixes slow loading
    fig.write_html("outputs/daily_flight_map.html", include_plotlyjs="cdn")
    print("Map successfully generated at outputs/daily_flight_map.html")
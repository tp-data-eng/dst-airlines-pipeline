import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import gaussian_kde

# Project Palette
PALETTE = {
    'primary': '#2b5c8f',    # Navy blue
    'secondary': '#d95f02',  # Warm orange
    'accent': '#7570b3',     # Purple
    'neutral': '#666666'     # Gray
}

class InteractiveAirlineVisualizer:
    """Generates interactive Plotly figures for Streamlit dashboards."""

    @staticmethod
    def _format_eur_number(val: float | int) -> str:
        """Formats numbers using European style (1,000 -> 1.000)."""
        return f"{int(val):,}".replace(",", ".")

    def plot_flight_altitude_distribution(self, df: pd.DataFrame) -> go.Figure:
        """Generates an interactive Plotly histogram of flight altitudes with KDE overlay."""
        if 'aircraft_altitude' not in df.columns:
            raise ValueError("DataFrame must contain 'aircraft_altitude' column.")

        altitudes = df['aircraft_altitude'].dropna()

        # Compute continuous KDE coordinates using SciPy
        kde = gaussian_kde(altitudes)
        x_kde = np.linspace(0, altitudes.max(), 300)
        y_kde = kde(x_kde)

        fig = go.Figure()

        # Primary Trace: Interactive Histogram (Primary Y-Axis)
        fig.add_trace(
            go.Histogram(
                x=altitudes,
                nbinsx=30,
                name="Aircraft Count",
                marker_color=PALETTE['primary'],
                opacity=0.85,
                hovertemplate="Altitude Range: %{x} m<br>Count: %{y}<extra></extra>"
            )
        )

        # Secondary Trace: Smooth KDE Density Curve (Secondary Y-Axis)
        fig.add_trace(
            go.Scatter(
                x=x_kde,
                y=y_kde,
                mode='lines',
                name="KDE Density",
                line=dict(
                    color=PALETTE['secondary'],
                    width=3,
                ),
                yaxis = "y2",
                hovertemplate = "Altitude: %{x:.0f} m<br>Density: %{y:.6f}<extra></extra>"
            )
        )

        # Statistical Reference: Vertical Median Line
        median_alt = altitudes.median()
        fig.add_vline(
            x=median_alt,
            line_dash="dash",
            line_color=PALETTE['secondary'],
            line_width=2,
            annotation_text=f"Median: {self._format_eur_number(median_alt)} m",
            annotation_position="top left"
        )

        # Layout & Axis Formatting
        fig.update_layout(
            title={
                'text': "<b>Live Fleet Altitude Distribution Audit</b><br><sup>Telemetry Altitude Spread</sup>",
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis=dict(
                title="Altitude (m)",
                range=[0, altitudes.max() * 1.05],
                zeroline=False
            ),
            yaxis=dict(
                title="Aircraft Count"
            ),
            yaxis2=dict(
                title="",
                overlaying="y",
                side="right",
                showticklabels=False,  # Keep secondary y-axis clean
                range=[0, max(y_kde) * 1.25]  # 25% Headroom above peak
            ),
            legend=dict(
                x=0.01,
                y=0.98,
                bgcolor="rgba(255,255,255,0.7)",
                bordercolor="rgba(0,0,0,0)"
            ),
            template="plotly_white",
            margin=dict(
                l=50,
                r=30,
                t=80,
                b=50),
            height=500,
            width=1000
        )

        return fig

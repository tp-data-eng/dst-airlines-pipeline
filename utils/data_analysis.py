from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
from wcwidth import width

# ----------------------------------------------------------------------
# GLOBAL STYLE CONFIGURATION
# ----------------------------------------------------------------------
# Standardize design theme across all pipeline reports
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
PALETTE = {
    'primary': '#2b5c8f',    # Navy blue
    'secondary': '#d95f02',  # Warm orange
    'accent': '#7570b3',     # Purple
    'neutral': '#666666'     # Gray
}

class AirlineVisualizer:
    """Reusable plotter for airline data engineering reports."""

    def __init__(self, output_dir: Path | str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents = True, exist_ok = True)

    def _save_fig(self, fig: plt.Figure, filename: str) -> Path:
        """Helper to safely save and close figures to prevent memory leaks."""
        filepath = self.output_dir / filename
        fig.savefig(filepath, dpi = 300, bbox_inches = 'tight')
        plt.close(fig)
        return filepath

    def plot_registration_coverage(self, df: pd.DataFrame, filename: str = "registration_coverage.png") -> Path:
        """Plot donut + bar chart of mapped vs UNKNOWN_REG counts."""
        if df.empty or 'reg_number' not in df.columns:
            raise ValueError("DataFrame must contain 'reg_number' column.")

        # Categorize entries into 'Mapped' vs 'UNKNOWN_REG'
        status_counts = df['reg_number'].apply(
            lambda x: 'UNKNOWN_REG' if x == 'UNKNOWN_REG' else 'Mapped'
        ).value_counts()

        # Calculate percentages for exact ratio labels
        total = len(df)
        colors = [PALETTE['primary'], PALETTE['secondary']]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize = (12, 5))

        # Donut Chart
        ax1.pie(
            status_counts,
            labels=status_counts.index,
            autopct='%1.1f%%',  # formats the % ratios onto the donut slices
            startangle=140,
            colors=colors,
            pctdistance=0.75,
            textprops={'weight': 'bold'}
            )

        ax1.add_artist(plt.Circle((0, 0), 0.55, fc = 'white'))
        ax1.set_title("Registration Mapping Coverage", fontweight = 'bold')

        # -----------------------------------
        # Bar Chart with Count & Ratio Annotations
        bars = ax2.bar(
            status_counts.index,
            status_counts.values,
            color=colors,
            width=0.5
        )
        ax2.set_ylabel(
            'Total Aircraft Records',
            fontsize=10
        )
        ax2.set_title(
            'Mapped vs. UNKNOWN_REG Record Counts',
            fontsize=12,
            fontweight='bold'
        )
        ax2.set_ylim(0, max(status_counts.values) * 1.15)  # Add headroom for labels

        for bar in bars:
            height = bar.get_height()
            pct = (height / total) * 100
            ax2.annotate(
                f'{height:,}\n({pct:.1f}%)',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 5),
                textcoords='offset points',
                ha='center',
                va='bottom',
                fontweight='bold'
            )

        return self._save_fig(fig, filename)

    def plot_flight_altitude_distribution(self, df: pd.DataFrame, filename: str = "flight_altitude_distribution.png") -> Path:
        """Histogram of flight altitudes to spot telemetry outliers."""
        if 'aircraft_altitude' not in df.columns:
            raise ValueError("DataFrame must contain 'aircraft_altitude' column.")

        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.hist(df['aircraft_altitude'].dropna(), bins = 30, color = PALETTE['primary'], edgecolor = 'white')
        ax.set_title("Live Fleet Altitude Distribution", fontweight = 'bold')
        ax.set_xlabel("Altitude (ft)")
        ax.set_ylabel("Aircraft Count")

        return self._save_fig(fig, filename)

    def plot_top_airlines(self, df: pd.DataFrame, airline_col: str = 'airline_name', top_n: int = 10, filename: str = "top_airlines.png") -> Path:
        """Plots a horizontal bar chart of the top N airlines by active flight volume."""
        if df.empty or airline_col not in df.columns:
            print(f"Warning: DataFrame empty or missing '{airline_col}'. Skipping plot.")
            return None

        # Aggregate counts & slice top N (reversed for top-to-bottom bar order)
        counts = df[airline_col].value_counts().head(top_n).iloc[::-1]

        fig, ax = plt.subplots(figsize = (10, 5))
        bars = ax.barh(
            counts.index,
            counts.values,
            color = PALETTE['primary'],
            height = 0.6
        )

        ax.set_title(f"Top {top_n} Active Airlines by Flight Count", fontsize = 12, fontweight = 'bold')
        ax.set_xlabel("Total Flights", fontsize = 10)
        ax.set_xlim(0, max(counts.values) * 1.15)       # Add headroom for labels

        # Bars with Counts
        for bar in bars:
            width = bar.get_width()
            ax.annotate(
                f'{width:,}',
                xy = (width, bar.get_y() + bar.get_height() / 2),
                xytext = (5, 0),
                textcoords = 'offset points',
                ha = 'left',
                va = 'center',
                fontweight = 'bold',
                color = PALETTE['neutral']
            )

        plt.tight_layout()
        return self._save_fig(fig, filename)

    def plot_top_hub_airlines(self, df: pd.DataFrame, airport_col: str = 'hub_airport', airline_col: str = 'airline_name', top_n: int = 5, filename: str = "top_hub_airlines.png") -> Path:
        """
        Plots top active airlines per target airport hub from schedule data.
        """
        if df.empty or airline_col not in df.columns or airport_col not in df.columns:
            print("Warning: Missing required columns for hub airline plot.")
            return None

        # Group by airport and airline to extract top N carriers per hub
        grouped = (
            df.groupby([airport_col, airline_col])
            .size()
            .reset_index(name='flight_count')
        )

        # Filtering: Rank airlines per hub and keep only the Top N for each airport
        top_per_hub = (
            grouped.sort_values([airport_col, 'flight_count'], ascending = [True, False])
            .groupby(airport_col)
            .head(top_n)
        )

        hubs = top_per_hub[airport_col].unique()

        # Create Fig
        fig, axes = plt.subplots(1, len(hubs), figsize = (5 * len(hubs), 5), sharey = False)

        # Ensure 'axes' is an iterable list
        if len(hubs) == 1:
            axes = [axes]

        # Plot: Loop through each hub subplot axis and render horizontal bar charts
        for ax, hub in zip(axes, hubs):
            # Filter dataset to current hub and reverse rows so highest values plot at top
            hub_data = top_per_hub[top_per_hub[airport_col] == hub].iloc[::-1]

            # Render horizontal bar chart
            bars = ax.barh(hub_data[airline_col], hub_data['flight_count'], color = PALETTE['primary'], height = 0.6)

            # Format plot axes, headers, and scale boundaries
            ax.set_title(f"Top Airlines at {hub}", fontsize=11, fontweight='bold')
            ax.set_xlabel("Scheduled Flights", fontsize=10)

            # Add 15% headroom on X-axis max limit
            ax.set_xlim(0, max(hub_data['flight_count']) * 1.15 if not hub_data.empty else 1)

            # Bar Annotations: Add exact numerical values at the end of each bar
            for bar in bars:
                width = bar.get_width()
                ax.annotate(
                    f'{width:,}',
                    xy = (width, bar.get_y() + bar.get_height() / 2),
                    xytext = (4, 0),
                    textcoords = 'offset points',
                    ha = 'left',
                    va = 'center',
                    fontsize = 9,
                    fontweight = 'bold',
                    color = PALETTE['neutral']
                )
        plt.tight_layout()
        return self._save_fig(fig, filename)
            

    def plot_top_aircraft_models(self, df: pd.DataFrame, model_col: str = 'model', top_n: int = 10, filename: str = "top_aircraft_models.png") -> Path:
        """Plots a horizontal bar chart of the most frequent aircraft models in the fleet."""
        if df.empty or model_col not in df.columns:
            print(f"Warning: DataFrame empty or missing '{model_col}'. Skipping plot.")
            return None

        # Clean fallback values and aggregate Top N
        cleaned_series = df[model_col].fillna('UNKNOWN_MODEL')
        counts = cleaned_series.value_counts().head(top_n).iloc[::-1]

        fig, ax = plt.subplots(figsize = (10, 5))

        # Set different Color if UNKNOWN_MODEL present in Top N
        bar_colors = [
            PALETTE['secondary'] if label == 'UNKNOWN_MODEL' else PALETTE['accent']
            for label in counts.index
        ]

        bars = ax.barh(
            counts.index,
            counts.values,
            color = bar_colors,
            height = 0.6
        )

        ax.set_title(f"Top {top_n} Aircraft Models in Fleet", fontsize = 12, fontweight = 'bold')
        ax.set_xlabel("Aircraft Count", fontsize = 10)
        ax.set_xlim(0, max(counts.values) * 1.15)

        for bar in bars:
            width = bar.get_width()
            ax.annotate(
                f'{width:,}',
                xy = (width, bar.get_y() + bar.get_height() / 2),
                xytext = (5, 0),
                textcoords = 'offset points',
                ha = 'left',
                va = 'center',
                fontweight = 'bold',
                color = PALETTE['neutral']
            )

        plt.tight_layout()
        return self._save_fig(fig, filename)

    def plot_fleet_coverage_audit(self, df: pd.DataFrame, model_col: str = 'model', top_n: int = 10, filename: str = "fleet_coverage_audit.png") -> Path:
        """Generates a 2-panel visual auditing data enrichment health:
        1. Known vs UNKNOWN coverage ratio
        2. Top populated aircraft models (excluding UNKNOWN)
        """
        if df.empty or model_col not in df.columns:
            print(f"Warning: DataFrame empty or missing '{model_col}'. Skipping audit plot.")
            return None

        # Standardize series
        series = df[model_col].fillna('UNKNOWN_MODEL')

        # Calculate overall metrics
        total_count = len(series)
        unknown_count = (series == 'UNKNOWN_MODEL').sum()
        known_count = total_count - unknown_count

        known_pct = (known_count / total_count * 100) if total_count > 0 else 0
        unknown_pct = (unknown_count / total_count * 100) if total_count > 0 else 0

        # Extract Top N known models
        known_series = series[series != 'UNKNOWN_MODEL']
        top_known = known_series.value_counts().head(top_n).iloc[::-1]

        # Figure layout: Left (Coverage Ratio), Right (Top Known Models)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize = (14, 5), gridspec_kw = {'width_ratios': [1, 2]})

        # Panel 1: Overall Data Quality Ratio
        categories = ['Enriched\n(Known)', 'Unmapped\n(UNKNOWN)']
        values = [known_count, unknown_count]
        colors = [PALETTE['primary'], PALETTE['secondary']]

        bars1 = ax1.bar(categories, values, color = colors, width = 0.5)
        ax1.set_title(f"Fleet Data Quality Overview\n({known_pct:.1f}% Enriched)", fontsize = 11, fontweight = 'bold')
        ax1.set_ylabel("Aircraft Hex Records", fontsize = 10)
        ax1.set_ylim(0, max(values) * 1.15 if values else 1)

        for bar in bars1:
            yval = bar.get_height()
            ax1.annotate(
                f'{yval:,}',
                xy = (bar.get_x() + bar.get_width() / 2, yval),
                xytext = (0, 3),
                textcoords = 'offset points',
                ha = 'center',
                va = 'bottom',
                fontweight = 'bold',
                color = PALETTE['neutral']
            )

        # Panel 2: Top Populated Aircraft Types
        if not top_known.empty:
            bars2 = ax2.barh(top_known.index, top_known.values, color = PALETTE['accent'], height = 0.6)
            ax2.set_title(f"Top {len(top_known)} Resolved Aircraft Models", fontsize = 11, fontweight = 'bold')
            ax2.set_xlabel("Airframe Count", fontsize = 10)
            ax2.set_xlim(0, max(top_known.values) * 1.15)

            for bar in bars2:
                width = bar.get_width()
                ax2.annotate(
                    f'{width:,}',
                    xy = (width, bar.get_y() + bar.get_height() / 2),
                    xytext = (5, 0),
                    textcoords = 'offset points',
                    ha = 'left',
                    va = 'center',
                    fontweight = 'bold',
                    color = PALETTE['neutral']
                )

        else:
            ax2.text(0.5, 0.5, "No known models found yet", ha = 'center', va = 'center', transform = ax2.transAxes)

        plt.tight_layout()
        return self._save_fig(fig, filename)


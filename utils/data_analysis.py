from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd

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

    def __init__(self, output_dir: Path | str = "outputs"):
        self.base_output_dir = Path(output_dir)
        # Generate  timestamp string at class initialization
        self.timestamp = datetime.now().strftime("%Y%m%d-%H%M")

    def _save_fig(self, fig: plt.Figure, filename: str, subfolder: str = "", data_as_of: str | None = None) -> Path:
        """Helper to safely save figures into target subfolders with timestamps
         and close figures to prevent memory leaks."""
        target_dir = self.base_output_dir / subfolder if subfolder else self.base_output_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        # Add Data Freshness Annotation (Bottom Right Footer)
        render_time = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M %Z")
        freshness_label = f"Data as of: {data_as_of}" if data_as_of else "Data As Of: Unknown"
        footer_text = f"{freshness_label} | Rendered: {render_time}"

        fig.text(
            0.99, 0.01,
            footer_text,
            ha='right',
            va='bottom',
            fontsize=8,
            color=PALETTE['neutral'],
            style='italic'
        )

        path_obj = Path(filename)

        # Adds timestamp
        timestamped_filename = f"{path_obj.stem}_{self.timestamp}{path_obj.suffix}"
        filepath = target_dir / timestamped_filename

        fig.savefig(filepath, dpi = 300, bbox_inches = 'tight')
        plt.close(fig)
        return filepath

    @staticmethod
    def _map_registration_status(val: str) -> str:
        """Helper to map raw database registration values to clean display labels."""
        return 'Unmapped' if val == 'UNKNOWN_REG' else 'Mapped'

    @staticmethod
    def _format_eur_number(val: float | int) -> str:
        """Formats numbers using European style (1,000 -> 1.000)."""
        return f"{int(val):,}".replace(",", ".")

    def plot_registration_coverage(self, df: pd.DataFrame, filename: str = "registration_coverage.png", data_as_of: str | None = None) -> Path:
        """Plot donut + bar chart of mapped vs UNKNOWN_REG counts."""
        if df.empty or 'reg_number' not in df.columns:
            raise ValueError("DataFrame must contain 'reg_number' column.")

        # Use Class Helper Method for Cleaner Category Labels
        status_counts = df['reg_number'].apply(self._map_registration_status).value_counts()

        # Calculate percentages for exact ratio labels
        total = len(df)
        colors = [PALETTE['primary'], PALETTE['secondary']]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize = (12, 5))

        # Overall Figure Title
        fig.suptitle("Aircraft Registration Mapping Coverage Audit", fontsize = 14, fontweight = 'bold', y = 0.95)

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
            width=0.4
        )
        ax2.set_ylabel('Total Aircraft Records', fontsize=10)
        ax2.set_title('Mapped vs. Unmapped Record Counts', fontsize=12, fontweight='bold')
        ax2.set_ylim(0, max(status_counts.values) * 1.15)  # Add headroom for labels

        # Add padding to x-axis
        ax2.set_xlim(-0.6, 1.6)

        # Modernize chart (Remove Top and Right Spines)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)

        for bar in bars:
            height = bar.get_height()
            pct = (height / total) * 100
            ax2.annotate(
                f'{self._format_eur_number(height)}\n({pct:.1f}%)',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 5),
                textcoords='offset points',
                ha='center',
                va='bottom',
                fontweight='bold'
            )

        # Adjust layout spacing to accommodate the overall title and footer
        fig.subplots_adjust(top = 0.82, bottom = 0.12)

        return self._save_fig(fig, filename, subfolder="coverage", data_as_of=data_as_of)

    def plot_flight_altitude_distribution(self, df: pd.DataFrame, filename: str = "flight_altitude_distribution.png", data_as_of: str | None = None) -> Path | None:
        """Histogram of flight altitudes with KDE overlay, European formatting and statistical reference line."""
        if 'aircraft_altitude' not in df.columns:
            raise ValueError("DataFrame must contain 'aircraft_altitude' column.")

        altitudes = df['aircraft_altitude'].dropna()

        fig, ax1 = plt.subplots(figsize=(10, 5))

        # Overall Figure Title
        fig.suptitle("Live Fleet Altitude Distribution Audit", fontsize = 14, fontweight = 'bold', y = 0.95)

        # Primary Axis: Histogram (Counts)
        ax1.hist(
            altitudes,
            bins = 30,
            color = PALETTE['primary'],
            edgecolor = 'white',
            linewidth = 0.8,
            alpha = 0.85
        )

        ax1.set_title("Telemetry Altitude Spread", fontsize = 12, fontweight = 'bold', pad = 10)
        ax1.set_xlabel("Altitude (m)", fontsize = 10)
        ax1.set_ylabel("Aircraft Count", fontsize = 10)

        # Set lower x-axis boundary at 0
        ax1.set_xlim(left = 0)
        ax1.margins(x = 0)

        # Secondary Axis: Kernel Density Estimate (KDE) Overlay
        ax2 = ax1.twinx()
        altitudes.plot.kde(
            ax=ax2,
            color=PALETTE['secondary'],
            linewidth = 2.5,
            label = 'KDE Density'
        )

        # Clean up secondary axis (hide raw density decimals & add 25% peak headroom)
        ax2.set_yticks([])
        ax2.set_ylabel("")
        ax2.set_ylim(bottom = 0, top = ax2.get_ylim()[1] * 1.25)

        # Spine adjustments
        ax1.spines['top'].set_visible(False)
        ax2.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax2.spines['right'].set_visible(False)

        # Set European number format for both axes using class helper
        ax1.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: self._format_eur_number(x)))
        ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: self._format_eur_number(x)))

        # Vertical Median Line
        median_alt = altitudes.median()
        ax1.axvline(
            median_alt,
            color = PALETTE['secondary'],
            linestyle = '--',
            linewidth = 2,
            label = f'Median: {self._format_eur_number(median_alt)} m',
        )

        # Combined Legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, frameon = False, loc = 'upper left')

        # Set layout spacing
        fig.subplots_adjust(top = 0.82, bottom = 0.15, left = 0.1, right = 0.95)

        return self._save_fig(fig, filename, subfolder="fleet", data_as_of=data_as_of)


    def plot_top_airlines(self, df: pd.DataFrame, airline_col: str = 'airline_name', top_n: int = 10, filename: str = "top_airlines.png", data_as_of: str | None = None) -> Path | None:
        """Plots a horizontal bar chart of the top N airlines by active flight volume."""
        if df.empty or airline_col not in df.columns:
            print(f"Warning: DataFrame empty or missing '{airline_col}'. Skipping plot.")
            return None

        # Aggregate counts & take Top N
        top_counts = df[airline_col].value_counts().head(top_n)

        if top_counts.empty:
            print(f"Warning: No valid records found in {airline_col}. Skipping plot.")
            return None

        # Reverse order for top-to-bottom bar chart display
        counts = top_counts.iloc[::-1]
        max_count = top_counts.max()

        fig, ax = plt.subplots(figsize = (10, 5))

        # Horizontal Bar Chart
        bars = ax.barh(
            counts.index,
            counts.values,
            color = PALETTE['primary'],
            height = 0.6,
            alpha = 0.9
        )

        # Titles and Labels
        ax.set_title(
            f"Top {top_n} Active Airlines by Flight Count",
            fontsize = 12,
            fontweight = 'bold',
            pad = 12
        )
        ax.set_xlabel("Total Flights", fontsize = 10, labelpad = 8)

        # Set x-axis limit with 15% headroom for annotations
        ax.set_xlim(0, max_count * 1.15)

        # Remove Top and Right Spines for a clean visual
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Apply European formatting to x-axis tick labels
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: self._format_eur_number(x)))

        # Annotate Bar Values with European Number Formatting
        for bar in bars:
            width = bar.get_width()
            ax.annotate(
                self._format_eur_number(width),
                xy = (width, bar.get_y() + bar.get_height() / 2),
                xytext = (6, 0),
                textcoords = 'offset points',
                ha = 'left',
                va = 'center',
                fontweight = 'bold',
                fontsize = 9,
                color = PALETTE['neutral']
            )

        plt.tight_layout()
        return self._save_fig(fig, filename, subfolder="airlines", data_as_of=data_as_of)

    def plot_top_hub_airlines(self, df: pd.DataFrame, airport_col: str = 'hub_airport', airline_col: str = 'airline_name', top_n: int = 5, filename: str = "top_hub_airlines.png", data_as_of: str = None) -> Path:
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
        return self._save_fig(fig, filename, subfolder="airlines", data_as_of=data_as_of)


    def plot_fleet_coverage_audit(self, df: pd.DataFrame, model_col: str = 'model', top_n: int = 10, filename: str = "fleet_coverage_audit.png", data_as_of: str | None = None) -> Path:
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
        return self._save_fig(fig, filename, subfolder="coverage", data_as_of=data_as_of)


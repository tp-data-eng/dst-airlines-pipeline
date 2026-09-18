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

    @staticmethod
    def _apply_clean_spines(
            ax: plt.Axes,
            top: bool = False,
            right: bool = False,
            left_color: str = "#cccccc",
            bottom_color: str = '#cccccc'
    ):
        """Applies standardized clean spine formatting to a Matplotlib Axes object."""
        ax.spines["top"].set_visible(top)
        ax.spines["right"].set_visible(right)
        ax.spines["left"].set_color(left_color)
        ax.spines["bottom"].set_color(bottom_color)

    @staticmethod
    def _setup_figure_header(
            fig: plt.Figure,
            title: str,
            fontsize: int = 14,
            x: float = 0.04,
            y: float = 0.98
    ):
        """Applies a standardized executive top-level title to a figure canvas."""
        fig.suptitle(
            title,
            fontsize = fontsize,
            fontweight = 'bold',
            x = x,
            ha = 'left',
            y = y,
        )

    @staticmethod
    def _format_eur_pct(val: float, decimals: int = 1) -> str:
        """Formats float values as European percentage strings (e.g. 41.4 -> '41,4%')."""
        return f"{val:.{decimals}f}%".replace(".", ",")


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
        self._setup_figure_header(fig, "Aircraft Registration Mapping Coverage Audit")

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
        self._apply_clean_spines(ax2)

        for bar in bars:
            height = bar.get_height()
            pct = (height / total) * 100
            ax2.annotate(
                f'{self._format_eur_number(height)}\n({self._format_eur_pct(pct)})',
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
        self._setup_figure_header(fig, "Live Fleet Altitude Distribution Audit")

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
        self._apply_clean_spines(ax1)
        self._apply_clean_spines(ax2)

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

        # Calculate counts & percentages
        total_volume = len(df[df[airline_col].notna()])
        top_counts = df[airline_col].value_counts().head(top_n)

        if top_counts.empty:
            print(f"Warning: No valid records found in {airline_col}. Skipping plot.")
            return None

        # Dynamic metrics for the #1 leading airline
        top_airline_name = top_counts.index[0]
        top_airline_count = top_counts.iloc[0]
        top_airline_share = (top_airline_count / total_volume) * 100
        formatted_share = f"{self._format_eur_pct(top_airline_share)}"

        # Reverse order for top-to-bottom bar chart display
        counts = top_counts.iloc[::-1]
        max_count = top_counts.max()

        fig, ax = plt.subplots(figsize = (10, 5))

        # Dynamic Color Array: Highlight #1 Leader in Primary Color, remaining in Secondary
        bar_colors = [
            PALETTE['primary'] if idx != len(counts) - 1 else PALETTE['secondary'] for idx in range(len(counts))
        ]

        # Horizontal Bar Chart
        bars = ax.barh(
            counts.index,
            counts.values,
            color = bar_colors,
            height = 0.62,
            edgecolor = 'none',
            alpha = 0.92
        )

        # Titles and Labels
        self._setup_figure_header(fig, f"Top {top_n} Active Airlines by Flight Count")

        # ax.set_title(
        #   f"Key Insight: {top_airline_name} leads operating volume with {formatted_share} total market share in active telemetry",
        #    fontsize = 10,
        #    color = '#555555',
        #    pad = 12,
        #    loc = 'center'
        #)

        ax.set_xlabel("Total Flights", fontsize = 10, labelpad = 8)

        # Set x-axis limit with 15% headroom for annotations
        ax.set_xlim(0, max_count * 1.15)

        # Clean Spines
        self._apply_clean_spines(ax)

        # Apply European formatting to x-axis tick labels
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: self._format_eur_number(x)))

        # Annotate Values with Count and Market Share %
        for bar, val in zip(bars, counts.values):
            width = bar.get_width()
            share_pct = (val / total_volume) * 100
            label_str = (
                f"{self._format_eur_number(width)} ({self._format_eur_pct(share_pct)})"
            )

            # Distinct text color for top leader
            is_leader = width == max_count
            text_color = PALETTE['secondary'] if is_leader else PALETTE['neutral']

            ax.annotate(
                f"{self._format_eur_number(width)} ({self._format_eur_pct(share_pct)})",
                xy = (width, bar.get_y() + bar.get_height() / 2),
                xytext = (7, 0),
                textcoords = 'offset points',
                ha = 'left',
                va = 'center',
                fontweight = 'bold',
                fontsize = 9.5,
                color = text_color
            )

        plt.tight_layout()
        #fig.subplots_adjust(top = 0.84)
        return self._save_fig(fig, filename, subfolder="airlines", data_as_of=data_as_of)

    def plot_top_hub_airlines(
            self,
            df: pd.DataFrame,
            airport_col: str = 'hub_airport',
            airline_col: str = 'airline_name',
            top_n: int = 5,
            filename: str = "top_hub_airlines.png",
            data_as_of: str | None = None
    ) -> Path:
        """Plots side-by-side horizontal bar charts comparing airline market share (%) across target hub airports."""
        if df.empty or airline_col not in df.columns or airport_col not in df.columns:
            print("Warning: Missing required columns for hub airline plot.")
            return None

        # Filter out unmapped/null airlines
        valid_df = df[df[airline_col].notna()].copy()

        if valid_df.empty:
            print("Warning: No valid airline records available. Skipping plot.")
            return None

        # Group by airport and airline to extract top N carriers per hub
        grouped = (
            valid_df.groupby([airport_col, airline_col])
            .size()
            .reset_index(name='flight_count')
        )

        # Calculate total flight volume per hub for normalized market share calculation
        hub_totals = (
            grouped.groupby(airport_col)["flight_count"]
            .sum()
            .to_dict()
        )
        grouped['market_share_pct'] = grouped.apply(
            lambda row: (row["flight_count"] / hub_totals[row[airport_col]]) * 100,
            axis = 1
        )

        # Filtering: Rank airlines per hub and keep only the Top N for each airport
        top_per_hub = (
            grouped.sort_values([airport_col, 'market_share_pct'], ascending = [True, False])
            .groupby(airport_col)
            .head(top_n)
        )

        hubs = top_per_hub[airport_col].unique()

        if len(hubs) == 0:
            print("Warning: No hub data available to plot.")
            return None

        # Create Fig
        fig, axes = plt.subplots(1, len(hubs), figsize = (5 * len(hubs), 5), sharey = False)

        # Ensure 'axes' is an iterable list
        if len(hubs) == 1:
            axes = [axes]

        # Executive Header Alignment
        self._setup_figure_header(fig, f"Top {top_n} Airlines Market Share (%) Across Target Hub Airports", x = 0.04, y = 0.98)

        # Plot: Loop through each hub subplot axis and render horizontal bar charts
        for ax, hub in zip(axes, hubs):
            # Filter dataset to current hub and reverse rows so highest values plot at top
            hub_data = top_per_hub[top_per_hub[airport_col] == hub].iloc[::-1]

            if hub_data.empty:
                continue

            max_share = hub_data['market_share_pct'].max()

            # Highlight #1 Hub Leader in secondary color, remaining carriers in primary
            bar_colors = [
                (
                    PALETTE['secondary']
                    if share == max_share
                    else PALETTE['primary']
                )
                for share in hub_data['market_share_pct']
            ]

            # Render Horizontal Bars (Plotting Market Share %)
            bars = ax.barh(
                hub_data[airline_col],
                hub_data['market_share_pct'],
                color = bar_colors,
                height = 0.6,
                edgecolor = 'None',
                alpha = 0.92
            )

            # Format plot axes, headers, and scale boundaries
            ax.set_title(f"Hub: {hub}", fontsize=11, fontweight='bold', pad = 10)
            ax.set_xlabel("Hub Market Share (%)", fontsize=9.5, labelpad = 6)

            # Add 30% headroom on X-axis max limit
            ax.set_xlim(0, max_share * 1.30)

            # Clean Spines
            self._apply_clean_spines(ax)

            # Format X-axis tick labels as European percentage strings
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: self._format_eur_pct(x, decimals = 0)))

            # Bar Annotations: Format raw flights + market share percentage
            for bar, raw_count, share_val in zip(
                bars, hub_data['flight_count'], hub_data['market_share_pct']
            ):
                width = bar.get_width()
                is_leader = share_val == max_share
                text_color = (
                    PALETTE['secondary'] if is_leader else PALETTE['neutral']
                )

                formatted_val = self._format_eur_number(raw_count)

                ax.annotate(
                    f"{formatted_val} ({self._format_eur_pct(share_val)})",
                    xy = (width, bar.get_y() + bar.get_height() / 2),
                    xytext = (6, 0),
                    textcoords = 'offset points',
                    ha = 'left',
                    va = 'center',
                    fontsize = 8.5,
                    fontweight = 'bold' if is_leader else 'normal',
                    color = text_color
                )

        # Bottom Callout Subtitle
        fig.text(
            x = 0.04,
            y = 0.02,
            s = "Note: Operational volume normalized as percentage share of total scheduled flights per target hub.",
            fontsize = 9,
            fontstyle = 'italic',
            color = '#555555',
            ha = 'left',
            va = 'bottom'
        )

        plt.tight_layout()
        fig.subplots_adjust(top = 0.86, bottom = 0.15)

        return self._save_fig(fig, filename, subfolder="airlines", data_as_of=data_as_of)


    def plot_hub_market_share_donuts(
            self,
            df: pd.DataFrame,
            airport_col: str = 'hub_airport',
            airline_col: str = 'airline_name',
            top_n: int = 4,
            filename: str = 'hub_market_share_donuts.png',
            data_as_of: str | None = None,
    ) -> Path | None:
        """Plots side-by-side donut charts showing airline market share concentration at target hubs."""
        if df.empty or airline_col not in df.columns or airport_col not in df.columns:
            print("Warning: Missing required columns for donut plot.")
            return None

        valid_df = df[df[airline_col].notna()].copy()
        grouped = (
            valid_df.groupby([airport_col, airline_col])
            .size()
            .reset_index(name='flight_count')
        )
        hubs = grouped[airport_col].unique()

        if len(hubs) == 0:
            return None

        fig, axes = plt.subplots(
            1, len(hubs), figsize = (5.8 * len(hubs), 5.5), subplot_kw = dict(aspect='equal')
        )
        if len(hubs) == 1:
            axes = [axes]

        self._setup_figure_header(fig, "Airline Market Share Concentration Across Target Hubs")

        # Sequential blue shades to differentiate secondary carriers (Airlines 2-4)
        SECONDARY_BLUE_GRADIENT = ["#2b5c8f", "#4f7bb0", "#7ba3cd"]

        for ax, hub in zip(axes, hubs):
            hub_data = (
                grouped[grouped[airport_col] == hub]
                .sort_values("flight_count", ascending = False)
            )
            total_flights = hub_data['flight_count'].sum()

            # Slice Top N airlines, group rest into 'Other'
            top_slice = hub_data.head(top_n).copy()
            other_count = hub_data.iloc[top_n:]['flight_count'].sum()

            if other_count > 0:
                other_row = pd.DataFrame(
                    [{airport_col: hub, airline_col: 'Other Airlines', 'flight_count': other_count}]
                )
                top_slice = pd.concat([top_slice, other_row], ignore_index = True)

            # Palette: #1 Leader in secondary, 2-4 in primary, 'Other' in neutral
            colors = []
            secondary_idx = 0
            for i, row in top_slice.iterrows():
                if i == 0:
                    colors.append(PALETTE['secondary'])     # Secondary for #1 Leader
                elif row[airline_col] == 'Other Airlines':
                    colors.append(PALETTE['neutral'])       # Neutral for Others
                else:
                    # Assign distinct shade of blue for carriers 2 through 4
                    color = SECONDARY_BLUE_GRADIENT[secondary_idx % len(SECONDARY_BLUE_GRADIENT)]
                    colors.append(color)
                    secondary_idx += 1

            # Draw Donut Chart
            wedges, texts, autotexts = ax.pie(
                top_slice['flight_count'],
                autopct = lambda pct: self._format_eur_pct(pct) if pct >= 3.0 else "",
                startangle = 140,
                colors = colors,
                pctdistance = 0.68,
                wedgeprops = dict(width = 0.40, edgecolor = 'white', linewidth = 2)
            )

            # Style percentage value annotations dynamically based on slice size
            total_val = sum(top_slice["flight_count"])
            for i, (autotext, wedge) in enumerate(zip(autotexts, wedges)):
                pct = (top_slice.iloc[i]["flight_count"] / total_val) * 100

                # Larger slices get bold white text inside; small slices get gray text
                if pct < 10.0:
                    autotext.set_color("#333333")
                    autotext.set_fontsize(8.0)
                    autotext.set_weight("bold")
                else:
                    autotext.set_color("white")
                    autotext.set_fontsize(8.5)
                    autotext.set_weight("bold")

            # Subplot Title
            formatted_total = self._format_eur_number(total_flights)
            ax.set_title(
                f"Hub: {hub}\n({formatted_total} Flights)",
                fontsize = 11,
                fontweight = 'bold',
                pad = 10
            )

            # Clean legend below each subplot to eliminate text collisions
            ax.legend(
                wedges,
                top_slice[airline_col],
                title = 'Airlines',
                loc = 'upper center',
                bbox_to_anchor = (0.5, -0.06),
                frameon = False,
                fontsize = 8.5,
                title_fontsize = 9
            )

        plt.tight_layout()
        fig.subplots_adjust(top = 0.82, bottom = 0.25)

        return self._save_fig(fig, filename, subfolder = 'airlines', data_as_of = data_as_of)


    def plot_hub_consolidation_comparison(
            self,
            df: pd.DataFrame,
            airport_col: str = 'hub_airport',
            airline_col: str = 'airline_name',
            filename: str = 'hub_consolidation_comparison.png',
            data_as_of: str | None = None,
    ) -> Path | None:
        """Plots a single comparison bar chart contrasting Home Carrier Dominance vs. Foreign Competitors."""
        if df.empty or airline_col not in df.columns or airport_col not in df.columns:
            return None

        # Map primary home carriers per target hub
        HOME_CARRIER_MAP = {
            "EGLL": "British Airways",
            "LFPG": "Air France",
            "LTFM": "Turkish Airlines"
        }

        valid_df = df[df[airline_col].notna()].copy()
        hubs = valid_df[airport_col].unique()

        records = []
        for hub in hubs:
            hub_data = valid_df[valid_df[airport_col] == hub]
            total = len(hub_data)
            home_carrier = HOME_CARRIER_MAP.get(hub, hub_data[airline_col].mode()[0])

            home_count = len(hub_data[hub_data[airline_col] == home_carrier])
            foreign_count = total - home_count

            records.append({
                "hub": hub,
                "home_carrier": home_carrier,
                "home_pct": (home_count / total) * 100 if total > 0 else 0,
                "foreign_pct": (foreign_count / total) * 100 if total > 0 else 0,
                "total_flights": total
            })

        summary_df = pd.DataFrame(records).sort_values("home_pct", ascending = False)

        fig, ax = plt.subplots(figsize = (9, 4.5))

        # Render Stacked Horizontal Bars (100% Market Share)
        y_pos = range(len(summary_df))
        bars_home = ax.barh(
            y_pos,
            summary_df["home_pct"],
            color = PALETTE['secondary'],
            height = 0.52,
            label = "Home Flag Carrier"
        )
        bars_foreign = ax.barh(
            y_pos,
            summary_df["foreign_pct"],
            left = summary_df["home_pct"],
            color = PALETTE['primary'],
            height = 0.52,
            label = "Foreign Competitors"
        )

        # Titles & Labels
        self._setup_figure_header(fig, "Hub Consolidation Index: Home Carrier Market Dominance")

        ax.set_yticks(y_pos)
        ax.set_yticklabels(
            [f"Hub: {row['hub']}\n({row['home_carrier']})" for _, row in summary_df.iterrows()],
            fontsize = 9.5
        )
        ax.set_xlabel("Market Share (%)", fontsize = 9.5, fontweight = 'bold', labelpad = 8)
        ax.set_xlim(0, 100)

        # Clean Spines
        self._apply_clean_spines(ax)

        # Annotate Percentages inside bars
        for i, row in summary_df.reset_index(drop = True).iterrows():
            if row['home_pct'] > 5:
                # Home Carrier %
                ax.annotate(
                    f"{row['home_pct']:.1f}%".replace(".", ","),
                    xy = (row['home_pct'] / 2, i),
                    ha = 'center',
                    va = 'center',
                    color = 'white',
                    fontweight = 'bold',
                    fontsize = 9.5
                )
                # Foreign Competitors %
                ax.annotate(
                    f"{row['foreign_pct']:.1f}%".replace(".", ","),
                    xy = (row['home_pct'] + (row['foreign_pct'] / 2), i),
                    ha = 'center',
                    va = 'center',
                    color = 'white',
                    fontweight = 'bold',
                    fontsize = 9.5
                )

        ax.legend(
            loc = 'lower right',
            bbox_to_anchor = (1.0, 1.02),
            ncol = 2,
            frameon = False,
            fontsize = 9
        )

        plt.tight_layout()
        fig.subplots_adjust(top = 0.82, bottom = 0.15)

        return self._save_fig(fig, filename, subfolder = 'airlines', data_as_of = data_as_of)


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
                f'self._format_eur_number(yval)',
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
                    f'self._format_eur_number(width)',
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


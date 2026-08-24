from pathlib import Path
import matplotlib.pyplot as plt
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
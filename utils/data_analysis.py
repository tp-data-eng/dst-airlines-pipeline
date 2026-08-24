import matplotlib.pyplot as plt
import pandas as pd



def plot_reg_mapping_results(df, output_path = 'registration_coverage.png'):
    """Generates and saves a mapping quality report for aircraft registrations."""
    if df.empty or 'reg_number' not in df.columns:
        print("Warning: DataFrame is empty or missing 'reg_number' column. Skipping plot.")
        return

    # Categorize entries into 'Mapped' vs 'UNKNOWN_REG'
    status_counts = df['reg_number'].apply(
        lambda x: 'UNKNOWN_REG' if x == 'UNKNOWN_REG' else 'Mapped'
    ).value_counts()

    # Calculate percentages for exact ratio labels
    total = len(df)
    percentages = (status_counts / total) * 100

    # Configure plot layout
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize = (12, 5))
    colors = ['#2b5c8f', '#d95f02']  # Steel blue for Mapped, Warm orange for Unknown

    # -----------------------------------
    # Donut Chart
    wedges, texts, autotexts = ax1.pie(
        status_counts,
        labels = status_counts.index,
        autopct = '%1.1f%%',            # formats the % ratios onto the donut slices
        startangle = 140,
        colors = colors,
        pctdistance = 0.75,
        textprops = dict(
            color = 'black',
            weight = 'bold'
        )
    )

    # Draw center circle for donut effect
    center_circle = plt.Circle((0, 0), 0.55, fc = 'white')
    ax1.add_artist(center_circle)
    ax1.set_title("Registration Mapping Distribution", fontsize = 12, fontweight = 'bold')

    # -----------------------------------
    # Bar Chart with Count & Ratio Annotations
    bars = ax2.bar(
        status_counts.index,
        status_counts.values,
        color = colors,
        width = 0.5
    )
    ax2.set_ylabel(
        'Total Aircraft Records',
        fontsize = 10
    )
    ax2.set_title(
        'Mapped vs. UNKNOWN_REG Record Counts',
        fontsize = 12,
        fontweight = 'bold'
    )
    ax2.set_ylim(0, max(status_counts.values) * 1.15)       # Add headroom for labels

    # Annotate bars with total count and percentage ratio
    for bar in bars:
        height = bar.get_height()
        pct = (height / total) * 100
        ax2.annotate(
            f'{height:,}\n({pct:.1f}%)',
            xy = (bar.get_x() + bar.get_width() / 2, height),
            xytext = (0, 5),
            textcoords = 'offset points',
            ha = 'center',
            va = 'bottom',
            fontweight = 'bold'
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi = 300)
    plt.close(fig)
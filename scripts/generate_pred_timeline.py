import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe

# ---------------------------------------------------------
# 1. Load, Clean, and Filter Data
# ---------------------------------------------------------
df = pd.read_parquet('data/task_instance_20260220_095402.parquet')


# Handle missing/empty callsigns
df['callsign'] = df['callsign'].fillna('None (Idle)').replace('', 'None (Idle)')

start_dt = pd.to_datetime(1758705557261, unit='ms')
end_dt = pd.to_datetime(1758705674282, unit='ms')

df = df[(df['timestamp'] >= start_dt) & (df['timestamp'] <= end_dt)].copy()
if df.empty:
    raise ValueError("No data found in the specified timestamp range.")
df = df.sort_values('timestamp')

# ---------------------------------------------------------
# 2. Process into Continuous Blocks
# ---------------------------------------------------------
blocks = []
callsigns = df['callsign'].values
datetimes = df['timestamp'].values 

start_time = datetimes[0]
current_cs = callsigns[0]

for i in range(1, len(df)):
    if callsigns[i] != current_cs:
        blocks.append((start_time, datetimes[i], current_cs))
        start_time = datetimes[i] 
        current_cs = callsigns[i]

median_gap = df['timestamp'].diff().median()
if pd.isna(median_gap):
    median_gap = pd.Timedelta(seconds=1)
blocks.append((start_time, datetimes[-1] + median_gap, current_cs))

# ---------------------------------------------------------
# 3. The "Sophisticated" Palette
# ---------------------------------------------------------
unique_callsigns = sorted([cs for cs in df['callsign'].unique() if cs != 'None (Idle)'])
if 'None (Idle)' in df['callsign'].unique():
    unique_callsigns.append('None (Idle)')

# A manually curated, desaturated palette. 
# These colors are soft on the eyes but distinct from each other.
sophisticated_palette = [
    '#66C2A5', # Muted Teal
    '#FC8D62', # Soft Salmon/Orange
    '#8DA0CB', # Periwinkle Blue
    '#E78AC3', # Dusty Pink
    '#A6D854', # Sage Green
    '#FFD92F', # Muted Yellow
    '#E5C494', # Sand/Tan
    '#8CCBFF', # Sky Blue (replacing the standard grey from Set2)
    '#B3B3B3', # Medium Grey (if needed)
]

color_dict = {}
for i, cs in enumerate(unique_callsigns):
    if cs == 'None (Idle)':
        color_dict[cs] = '#E5E5EA' # System Light Gray for idle
    else:
        color_dict[cs] = sophisticated_palette[i % len(sophisticated_palette)]

# Figure setup
fig, ax = plt.subplots(figsize=(18, 2.5))

# ---------------------------------------------------------
# 4. Draw Timeline Blocks & Inline Text
# ---------------------------------------------------------
for start, end, cs in blocks:
    start_num = mdates.date2num(start)
    width = mdates.date2num(end) - start_num
    
    # Plot horizontal rectangle
    ax.broken_barh([(start_num, width)], (0, 1), 
                   facecolors=color_dict[cs], edgecolors='none')
    
    duration_sec = pd.Timedelta(end - start).total_seconds()
    
    # Heuristic: 1.0 ensures no bleeding
    if cs != 'None (Idle)' and duration_sec > (len(cs) * 1.0):
        center_time = start + (end - start) / 2
        ax.text(center_time, 0.5, cs, 
                ha='center', va='center', 
                color='#2C2C2E',       # Dark Charcoal (softer than black)
                fontsize=9.5,          
                fontweight='bold',
                clip_on=True,
                path_effects=[pe.withStroke(linewidth=3, foreground="white")])

# ---------------------------------------------------------
# 5. Styling & Layout
# ---------------------------------------------------------
# Edge-to-edge
ax.set_xlim(start_dt, end_dt)
ax.margins(x=0)

# Exact ticks
base_date = start_dt.strftime('%Y-%m-%d')
tick_times = ['09:19:28', '09:19:43', '09:19:58', '09:20:13', 
              '09:20:28', '09:20:43', '09:20:58', '09:21:13']
exact_ticks = [pd.to_datetime(f"{base_date} {t}") for t in tick_times]

ax.set_xticks(exact_ticks)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

# Y-axis cleanup
ax.set_ylim(-0.2, 1.2) 
ax.set_yticks([]) 

# Labels
ax.set_xlabel('UTC time', fontsize=10.5, color='#666666', labelpad=8)
ax.tick_params(axis='x', colors='#666666', pad=6, length=0, labelsize=9.5)

# Grid
ax.grid(axis='x', color='#E5E5E5', linestyle='-', linewidth=1)
ax.set_axisbelow(True)

# Spines
for spine in ax.spines.values():
    spine.set_visible(False)

# ---------------------------------------------------------
# 6. Title, Legend, and Save
# ---------------------------------------------------------
ax.set_title('Task Instance Prediction for ATCO 3 / Scenario 3', pad=20, fontsize=15, fontweight='bold', color='#1C1C1E')

legend_patches = [mpatches.Patch(color=color_dict[cs], label=cs) for cs in unique_callsigns]

ax.legend(handles=legend_patches, 
          loc='upper center', 
          bbox_to_anchor=(0.5, -0.30), 
          ncol=len(unique_callsigns), 
          frameon=False, 
          fontsize=10.5,
          columnspacing=2.0)

output_filename = "callsign_timeline.png"
plt.savefig(output_filename, dpi=300, bbox_inches='tight', facecolor='white')
print(f"Chart successfully saved to {output_filename}")

plt.close(fig)
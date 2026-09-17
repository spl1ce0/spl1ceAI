import io
import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def calculate_uptime_stats(hourly_snapshots: list) -> tuple[float, int, str]:
    """
    Calculates 24h uptime percentage, total down minutes, and dynamic 12-block emoji sparkline.
    Each sparkline block represents a 2-hour window.
    """
    total_slots = 24
    PINGS_PER_HOUR = 12.0 # Ping every 5 min = 12 pings/hour
    counts = [0] * total_slots
    now_dt = datetime.datetime.now(datetime.timezone.utc)

    for row in hourly_snapshots:
        ts_val = row[5] if len(row) > 5 else row[-1]
        try:
            dt_str = str(ts_val).replace("Z", "+00:00")
            if "+" not in dt_str and "T" in dt_str:
                dt_str += "+00:00"
            elif "+" not in dt_str and " " in dt_str:
                dt_str = dt_str.split(".")[0] + "+00:00"
            dt = datetime.datetime.fromisoformat(dt_str)
            age_hours = int((now_dt - dt).total_seconds() / 3600)
            if 0 <= age_hours < total_slots:
                idx = total_slots - 1 - age_hours
                counts[idx] += 1
        except Exception:
            pass

    total_expected_pings = total_slots * PINGS_PER_HOUR
    total_received_pings = sum(counts)
    uptime_pct = min(100.0, (total_received_pings / total_expected_pings) * 100) if total_expected_pings > 0 else 0.0

    missing_pings = max(0, int(total_expected_pings - total_received_pings))
    down_minutes = missing_pings * 5

    # 12 discrete 2-hour blocks for the emoji sparkline
    # Slot 0: 24h-22h ago ... Slot 11: 2h ago - Now
    sparkline_emojis = []
    for i in range(12):
        h1 = i * 2
        h2 = h1 + 1
        block_pings = counts[h1] + counts[h2] # Expected: 24 pings
        if block_pings >= 20:
            sparkline_emojis.append("🟩") # Operational
        elif block_pings >= 10:
            sparkline_emojis.append("🟨") # Degraded
        elif block_pings > 0:
            sparkline_emojis.append("🟧") # Partial outage
        else:
            sparkline_emojis.append("🟥") # Major Outage / Offline

    sparkline = "".join(sparkline_emojis)
    return uptime_pct, down_minutes, sparkline


def generate_uptime_chart(hourly_snapshots: list) -> tuple[io.BytesIO, float]:
    """
    Generates a discordstatus.com style 24-hour uptime sparkline chart.
    Features dark statuspage aesthetics, individual bar tracks, and detailed percentage ticks.
    """
    total_slots = 24
    PINGS_PER_HOUR = 12.0
    counts = [0] * total_slots
    now_dt = datetime.datetime.now(datetime.timezone.utc)

    for row in hourly_snapshots:
        ts_val = row[5] if len(row) > 5 else row[-1]
        try:
            dt_str = str(ts_val).replace("Z", "+00:00")
            if "+" not in dt_str and "T" in dt_str:
                dt_str += "+00:00"
            elif "+" not in dt_str and " " in dt_str:
                dt_str = dt_str.split(".")[0] + "+00:00"
            dt = datetime.datetime.fromisoformat(dt_str)
            age_hours = int((now_dt - dt).total_seconds() / 3600)
            if 0 <= age_hours < total_slots:
                idx = total_slots - 1 - age_hours
                counts[idx] += 1
        except Exception:
            pass

    hourly_uptime = [min(100.0, (c / PINGS_PER_HOUR) * 100) for c in counts]
    overall_uptime = sum(hourly_uptime) / total_slots if total_slots > 0 else 0.0

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8.5, 2.6), facecolor='#111214')
    ax.set_facecolor('#111214')

    x_slots = list(range(total_slots))

    # Background track behind each bar for discordstatus.com pill look
    ax.bar(x_slots, [100.0] * total_slots, color='#1e1f22', width=0.68, edgecolor='none')

    # Color each bar based on health
    bar_colors = []
    for u in hourly_uptime:
        if u >= 98.0:
            bar_colors.append('#23a55a') # Discord operational green
        elif u >= 90.0:
            bar_colors.append('#57f287') # Minor degradation
        elif u >= 50.0:
            bar_colors.append('#f0b232') # Partial outage
        elif u > 0.0:
            bar_colors.append('#f23f43') # Outage
        else:
            bar_colors.append('#3c1e22') # Empty slot / offline

    ax.bar(x_slots, hourly_uptime, color=bar_colors, width=0.68, edgecolor='none')

    ax.set_ylim(0, 115)
    ax.set_xlim(-0.8, 23.8)

    # Detailed status ticks on Y-axis
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(['0%', '25%', '50%', '75%', '100%'], color='#80848e', fontsize=8.5, fontweight='bold')

    # Status ticks on X-axis
    ax.set_xticks([0, 6, 12, 18, 23])
    ax.set_xticklabels(['24h ago', '18h ago', '12h ago', '6h ago', 'Now'], color='#80848e', fontsize=8.5, fontweight='bold')

    # Clean borders & discordstatus gridlines
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis='y', color='#ffffff', alpha=0.06, linestyle='-', linewidth=0.8)

    # Status badge title
    if overall_uptime >= 99.0:
        status_label = f"Operational • {overall_uptime:.1f}% 24h Uptime"
        status_color = '#23a55a'
    elif overall_uptime >= 85.0:
        status_label = f"Degraded Performance • {overall_uptime:.1f}% 24h Uptime"
        status_color = '#f0b232'
    else:
        status_label = f"Downtime Recorded • {overall_uptime:.1f}% 24h Uptime"
        status_color = '#f23f43'

    ax.set_title(status_label, loc='left', color=status_color, fontsize=10.5, fontweight='bold', pad=10)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=140, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf, overall_uptime


def generate_servers_chart(growth_data: list, timeframe: str = "1d", current_count: int = 1) -> io.BytesIO:
    """
    Generates a sleek Discord blurple (#5865F2) growth chart of server counts over time.
    """
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8.5, 2.6), facecolor='#111214')
    ax.set_facecolor('#111214')

    y_vals = []
    if growth_data:
        for row in growth_data:
            y_vals.append(row[1] if row[1] is not None else current_count)
    if not y_vals:
        y_vals = [current_count] * 5

    x_vals = list(range(len(y_vals)))

    ax.plot(x_vals, y_vals, color='#5865f2', linewidth=2.5, marker='o', markersize=4, markerfacecolor='#ffffff')
    ax.fill_between(x_vals, y_vals, color='#5865f2', alpha=0.18)

    min_y = max(0, min(y_vals) - 1)
    max_y = max(y_vals) + 2
    ax.set_ylim(min_y, max_y)
    ax.set_xlim(-0.5, max(0.5, len(x_vals) - 0.5))

    # Ticks based on timeframe
    tf_labels = {
        "1d": ['24h ago', '18h ago', '12h ago', '6h ago', 'Now'],
        "1w": ['7d ago', '5d ago', '3d ago', '1d ago', 'Now'],
        "1m": ['30d ago', '20d ago', '10d ago', '5d ago', 'Now'],
        "1y": ['12m ago', '9m ago', '6m ago', '3m ago', 'Now'],
    }
    labels = tf_labels.get(timeframe.lower(), tf_labels["1d"])

    if len(x_vals) >= 5:
        step = (len(x_vals) - 1) / 4.0
        ax.set_xticks([int(step * i) for i in range(5)])
        ax.set_xticklabels(labels, color='#80848e', fontsize=8.5, fontweight='bold')
    else:
        ax.set_xticks([0, len(x_vals) - 1] if len(x_vals) > 1 else [0])
        ax.set_xticklabels([labels[0], labels[-1]] if len(x_vals) > 1 else ['Now'], color='#80848e', fontsize=8.5, fontweight='bold')

    ax.tick_params(axis='y', colors='#80848e', labelsize=8.5)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis='y', color='#ffffff', alpha=0.06, linestyle='-')

    ax.set_title(f"Server Count Growth ({timeframe.upper()}) • Current: {current_count:,}", loc='left', color='#5865f2', fontsize=10, fontweight='bold', pad=10)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=140, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_errors_chart(hourly_errors: list) -> io.BytesIO:
    """
    Generates a 24-hour error volume chart in Discord Red (#f23f43).
    """
    total_slots = 24
    errors = [0] * total_slots
    now_dt = datetime.datetime.now(datetime.timezone.utc)

    for row in hourly_errors:
        bucket = row[0]
        cnt = row[1]
        try:
            dt_str = str(bucket).replace("Z", "+00:00")
            if "+" not in dt_str and "T" in dt_str:
                dt_str += "+00:00"
            elif "+" not in dt_str and " " in dt_str:
                dt_str = dt_str.replace(" ", "T") + ":00+00:00"
            dt = datetime.datetime.fromisoformat(dt_str)
            age_hours = int((now_dt - dt).total_seconds() / 3600)
            if 0 <= age_hours < total_slots:
                idx = total_slots - 1 - age_hours
                errors[idx] = cnt
        except Exception:
            pass

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8.5, 2.6), facecolor='#111214')
    ax.set_facecolor('#111214')

    x_slots = list(range(total_slots))
    max_err = max(errors) if errors and max(errors) > 0 else 5

    # Background track
    ax.bar(x_slots, [max_err * 1.2] * total_slots, color='#1e1f22', width=0.68, edgecolor='none')
    # Error bars
    bar_colors = ['#f23f43' if e > 0 else '#23a55a' for e in errors]
    ax.bar(x_slots, errors, color=bar_colors, width=0.68, edgecolor='none')

    ax.set_ylim(0, max_err * 1.25)
    ax.set_xlim(-0.8, 23.8)

    ax.set_xticks([0, 6, 12, 18, 23])
    ax.set_xticklabels(['24h ago', '18h ago', '12h ago', '6h ago', 'Now'], color='#80848e', fontsize=8.5, fontweight='bold')
    ax.tick_params(axis='y', colors='#80848e', labelsize=8.5)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis='y', color='#ffffff', alpha=0.06, linestyle='-')

    total_errs = sum(errors)
    status_label = f"Incident Telemetry • {total_errs} Errors in last 24h"
    title_color = '#23a55a' if total_errs == 0 else '#f23f43'
    ax.set_title(status_label, loc='left', color=title_color, fontsize=10, fontweight='bold', pad=10)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=140, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_ai_traffic_chart(hourly_traffic: list) -> io.BytesIO:
    """Generates a sleek dark-mode 24-hour AI request volume chart."""
    total_slots = 24
    traffic = [0] * total_slots

    for row in hourly_traffic:
        bucket = row[0]
        cnt = row[1]
        try:
            hour_part = bucket.split(" ")[1].split(":")[0]
            h_idx = int(hour_part)
            if 0 <= h_idx < total_slots:
                traffic[h_idx] = cnt
        except Exception:
            pass

    now_hour = datetime.datetime.now(datetime.timezone.utc).hour
    ordered_traffic = [traffic[(now_hour + 1 + i) % 24] for i in range(24)]

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8.5, 2.6), facecolor='#111214')
    ax.set_facecolor('#111214')

    x = list(range(24))
    ax.plot(x, ordered_traffic, color='#ff1744', linewidth=2.5, marker='o', markersize=4, markerfacecolor='#ffffff')
    ax.fill_between(x, ordered_traffic, color='#ff1744', alpha=0.18)

    max_t = max(ordered_traffic) if ordered_traffic and max(ordered_traffic) > 0 else 10
    ax.set_ylim(0, max_t * 1.25)
    ax.set_xlim(-0.5, 23.5)
    ax.set_xticks([0, 6, 12, 18, 23])
    ax.set_xticklabels(['24h ago', '18h ago', '12h ago', '6h ago', 'Now'], color='#80848e', fontsize=8.5, fontweight='bold')
    ax.tick_params(axis='y', colors='#80848e', labelsize=8.5)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis='y', color='#ffffff', alpha=0.06, linestyle='-')

    ax.set_title("AI Request Volume (24h)", loc='left', color='#ff1744', fontsize=10, fontweight='bold', pad=10)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=140, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf

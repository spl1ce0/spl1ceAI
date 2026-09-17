import io
import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def calculate_uptime_stats(hourly_snapshots: list) -> tuple[float, int]:
    """Calculates overall 24h uptime percentage and total down minutes."""
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

    total_expected_pings = total_slots * PINGS_PER_HOUR
    total_received_pings = sum(counts)
    uptime_pct = min(100.0, (total_received_pings / total_expected_pings) * 100) if total_expected_pings > 0 else 100.0

    missing_pings = max(0, int(total_expected_pings - total_received_pings))
    down_minutes = missing_pings * 5

    return uptime_pct, down_minutes


def generate_uptime_chart(hourly_snapshots: list) -> tuple[io.BytesIO, float]:
    """Generates a headless dark-mode 24-hour uptime sparkline chart."""
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
    overall_uptime = sum(hourly_uptime) / total_slots if total_slots > 0 else 100.0

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8, 2.2), facecolor='#0f1015')
    ax.set_facecolor('#0f1015')

    x_slots = list(range(total_slots))
    colors = ['#10b981' if u >= 95 else '#f59e0b' if u >= 50 else '#ef4444' for u in hourly_uptime]
    ax.bar(x_slots, hourly_uptime, color=colors, width=0.75, edgecolor='none')

    ax.set_ylim(0, 115)
    ax.set_xlim(-0.8, 23.8)
    ax.set_yticks([0, 50, 100])
    ax.set_yticklabels(['0%', '50%', '100%'], color='#8b949e', fontsize=9, fontweight='bold')
    ax.set_xticks([0, 6, 12, 18, 23])
    ax.set_xticklabels(['24h ago', '18h ago', '12h ago', '6h ago', 'Now'], color='#8b949e', fontsize=9)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis='y', color='#ffffff', alpha=0.07, linestyle='--')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=140, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf, overall_uptime


def generate_ai_traffic_chart(hourly_traffic: list) -> io.BytesIO:
    """Generates a sleek dark-mode 24-hour AI request volume chart."""
    total_slots = 24
    hours = [f"{i:02d}:00" for i in range(24)]
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
    fig, ax = plt.subplots(figsize=(8, 2.4), facecolor='#0f1015')
    ax.set_facecolor('#0f1015')

    x = list(range(24))
    ax.plot(x, ordered_traffic, color='#ff1744', linewidth=2.5, marker='o', markersize=4, markerfacecolor='#ffffff')
    ax.fill_between(x, ordered_traffic, color='#ff1744', alpha=0.18)

    max_t = max(ordered_traffic) if ordered_traffic and max(ordered_traffic) > 0 else 10
    ax.set_ylim(0, max_t * 1.25)
    ax.set_xlim(-0.5, 23.5)
    ax.set_xticks([0, 6, 12, 18, 23])
    ax.set_xticklabels(['24h ago', '18h ago', '12h ago', '6h ago', 'Now'], color='#8b949e', fontsize=9)
    ax.tick_params(axis='y', colors='#8b949e', labelsize=9)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis='y', color='#ffffff', alpha=0.07, linestyle='--')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=140, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf

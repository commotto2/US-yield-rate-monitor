import datetime
import io
import os

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import requests
import yfinance as yf

# ── 설정 ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# ── 1. 데이터 수집 (모두 yfinance) ────────────────────
end_date   = datetime.date.today()
start_date = end_date - datetime.timedelta(days=365 + 5)

print("Downloading treasury yield data...")
raw = yf.download(["^IRX", "ZT=F", "^TNX"], start=start_date, end=end_date)["Close"]
data = raw.rename(columns={
    "^IRX": "3M T-Bill",
    "ZT=F": "2Y Treasury",
    "^TNX": "10Y Treasury",
})
data.index = pd.to_datetime(data.index)
print(f"Downloaded columns: {list(data.columns)}")
print(f"Row count: {len(data)}")

# ── 2. 그래프 생성 ────────────────────────────────────
SERIES = [
    ("10Y Treasury", "#4fa3e0", "10Y"),
    ("2Y Treasury",  "#f0a500", "2Y"),
    ("3M T-Bill",    "#e05c7a", "3M"),
]

periods = [
    {"title": "Recent 3 Months", "days": 90},
    {"title": "Recent 1 Year",   "days": 365},
]

fig, axes = plt.subplots(2, 1, figsize=(13, 11))
fig.patch.set_facecolor("#0f1117")

for i, p in enumerate(periods):
    ax       = axes[i]
    cutoff   = end_date - datetime.timedelta(days=p["days"])
    filtered = data.loc[cutoff.strftime("%Y-%m-%d"):]

    ax.set_facecolor("#1a1d27")

    for col, color, label in SERIES:
        if col not in filtered.columns:
            continue
        series = filtered[col].dropna()
        if series.empty:
            continue
        ax.plot(series.index, series,
                label=label, color=color, linewidth=1.8)

    ax.set_title(f"US Treasury Yields — {p['title']}",
                 fontsize=12, fontweight="bold", color="white", pad=8)
    ax.set_ylabel("Yield (%)", fontsize=10, color="#aaaaaa")
    ax.tick_params(colors="#aaaaaa", labelsize=9)
    ax.grid(True, linestyle="--", alpha=0.25, color="#555555")
    ax.legend(loc="upper left", framealpha=0.3,
              labelcolor="white", facecolor="#2a2d3a", fontsize=9)

    for spine in ax.spines.values():
        spine.set_edgecolor("#333344")

    for col, color, label in SERIES:
        if col not in filtered.columns:
            continue
        col_data = filtered[col].dropna()
        if col_data.empty:
            continue
        hi = col_data.max()
        lo = col_data.min()
        ax.axhline(hi, linestyle=":", linewidth=0.8, color=color, alpha=0.45)
        ax.axhline(lo, linestyle=":", linewidth=0.8, color=color, alpha=0.45)
        ax.text(filtered.index[-1], hi,
                f" {label} Hi {hi:.2f}%", color=color,
                fontsize=7.5, va="bottom", ha="right")
        ax.text(filtered.index[-1], lo,
                f" {label} Lo {lo:.2f}%", color=color,
                fontsize=7.5, va="top", ha="right")

    if p["days"] <= 90:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))

    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")

today_str = end_date.strftime("%Y-%m-%d")
fig.suptitle(f"US Treasury Yield Monitor  |  {today_str}",
             fontsize=14, fontweight="bold", color="white", y=1.005)
plt.tight_layout()

# ── 3. 이미지 버퍼 저장 ───────────────────────────────
buf = io.BytesIO()
plt.savefig(buf, format="png", dpi=150,
            bbox_inches="tight", facecolor=fig.get_facecolor())
buf.seek(0)
plt.close()

# ── 4. 텔레그램 전송 ──────────────────────────────────
latest = data.dropna(how="all").iloc[-1]
rate_10y = latest.get("10Y Treasury", float("nan"))
rate_2y  = latest.get("2Y Treasury",  float("nan"))
rate_3m  = latest.get("3M T-Bill",    float("nan"))
spread_10y_2y = rate_10y - rate_2y
spread_10y_3m = rate_10y - rate_3m
sign = lambda x: "▲" if x >= 0 else "▼"

caption = (
    f"📊 *US Treasury Yield Monitor*\n"
    f"📅 {today_str}\n\n"
    f"🔵 10Y: *{rate_10y:.2f}%*\n"
    f"🟠  2Y: *{rate_2y:.2f}%*\n"
    f"🔴  3M: *{rate_3m:.2f}%*\n\n"
    f"📐 Spread 10Y−2Y: *{spread_10y_2y:+.2f}%* {sign(spread_10y_2y)}\n"
    f"📐 Spread 10Y−3M: *{spread_10y_3m:+.2f}%* {sign(spread_10y_3m)}\n\n"
    f"_Powered by GitHub Actions + yfinance_"
)

url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
resp = requests.post(url, data={
    "chat_id":    TELEGRAM_CHAT_ID,
    "caption":    caption,
    "parse_mode": "Markdown",
}, files={"photo": ("chart.png", buf, "image/png")})

if resp.status_code == 200:
    print("✅ Telegram message sent successfully.")
else:
    print(f"❌ Failed: {resp.status_code} {resp.text}")
    raise SystemExit(1)

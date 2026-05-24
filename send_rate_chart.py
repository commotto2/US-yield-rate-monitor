import datetime
import io
import os
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import yfinance as yf
import pandas as pd

# ── 설정 ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# ── 1. 데이터 수집 ────────────────────────────────────
end_date   = datetime.date.today()
start_date = end_date - datetime.timedelta(days=5 * 365)

print("Downloading treasury yield data...")

# 10Y, 5Y: yfinance
raw = yf.download(["^FVX", "^TNX"], start=start_date, end=end_date)["Close"]
data = raw.rename(columns={
    "^FVX": "5Y Treasury",
    "^TNX": "10Y Treasury",
})

# 2Y: FRED via pandas_datareader
print("Downloading 2Y treasury yield from FRED...")
import pandas_datareader.data as web
fred_df = web.DataReader("DGS2", "fred", start_date, end_date)
fred_df.columns = ["2Y Treasury"]
fred_df.index = pd.to_datetime(fred_df.index)

# 합치기
data = data.join(fred_df, how="outer")
data.index = pd.to_datetime(data.index)

# ── 2. 그래프 생성 ────────────────────────────────────
fig, axes = plt.subplots(3, 1, figsize=(12, 16))
fig.patch.set_facecolor("#0f1117")

periods = [
    {"title": "Recent 1 Year",  "days": 365,     "ax": axes[0]},
    {"title": "Recent 3 Years", "days": 3 * 365, "ax": axes[1]},
    {"title": "Recent 5 Years", "days": 5 * 365, "ax": axes[2]},
]

SERIES = [
    ("10Y Treasury", "#4fa3e0", "FRED:DGS10"),
    ("5Y Treasury",  "#50c878", "^FVX"),
    ("2Y Treasury",  "#f0a500", "FRED:DGS2"),
]

for p in periods:
    ax       = p["ax"]
    cutoff   = end_date - datetime.timedelta(days=p["days"])
    filtered = data.loc[cutoff.strftime("%Y-%m-%d"):]

    ax.set_facecolor("#1a1d27")

    for col, color, ticker in SERIES:
        if col not in filtered.columns:
            continue
        ax.plot(filtered.index, filtered[col],
                label=f"{col[:2]}Y ({ticker})", color=color, linewidth=2)

    ax.set_title(f"US Treasury Yields — {p['title']}",
                 fontsize=13, fontweight="bold", color="white", pad=10)
    ax.set_ylabel("Yield (%)", fontsize=11, color="#aaaaaa")
    ax.tick_params(colors="#aaaaaa")
    ax.grid(True, linestyle="--", alpha=0.3, color="#555555")
    ax.legend(loc="upper left", framealpha=0.3,
              labelcolor="white", facecolor="#2a2d3a")

    for spine in ax.spines.values():
        spine.set_edgecolor("#333344")

    for col, color, _ in SERIES:
        if col not in filtered.columns:
            continue
        col_data = filtered[col].dropna()
        if col_data.empty:
            continue
        hi = col_data.max()
        lo = col_data.min()
        ax.axhline(hi, linestyle=":", linewidth=0.8, color=color, alpha=0.5)
        ax.axhline(lo, linestyle=":", linewidth=0.8, color=color, alpha=0.5)
        ax.text(filtered.index[-1], hi,
                f" {col[:2]}Y Hi {hi:.2f}%", color=color,
                fontsize=8, va="bottom", ha="right")
        ax.text(filtered.index[-1], lo,
                f" {col[:2]}Y Lo {lo:.2f}%", color=color,
                fontsize=8, va="top", ha="right")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

today_str = end_date.strftime("%Y-%m-%d")
fig.suptitle(f"US Treasury Yield Monitor  |  {today_str}",
             fontsize=15, fontweight="bold", color="white", y=1.01)
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
rate_5y  = latest.get("5Y Treasury",  float("nan"))
rate_2y  = latest.get("2Y Treasury",  float("nan"))
spread   = rate_10y - rate_2y
spread_sign = "▲" if spread >= 0 else "▼"

caption = (
    f"📊 *US Treasury Yield Monitor*\n"
    f"📅 {today_str}\n\n"
    f"🔵 10Y: *{rate_10y:.2f}%*\n"
    f"🟢  5Y: *{rate_5y:.2f}%*\n"
    f"🟠  2Y: *{rate_2y:.2f}%*\n"
    f"📐 Spread (10Y−2Y): *{spread:+.2f}%* {spread_sign}\n\n"
    f"_Powered by GitHub Actions + yfinance & FRED_"
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

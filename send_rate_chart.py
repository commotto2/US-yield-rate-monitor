import datetime
import io
import os
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import yfinance as yf

# ── 설정 ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# ── 1. 데이터 수집 ────────────────────────────────────
end_date   = datetime.date.today()
start_date = end_date - datetime.timedelta(days=5 * 365)

print("Downloading treasury yield data...")
raw = yf.download(["^IRX", "^TNX"], start=start_date, end=end_date)["Close"]
data = raw.rename(columns={"^IRX": "2Y Treasury", "^TNX": "10Y Treasury"})

# ── 2. 그래프 생성 ────────────────────────────────────
fig, axes = plt.subplots(3, 1, figsize=(12, 16))
fig.patch.set_facecolor("#0f1117")

periods = [
    {"title": "Recent 1 Year",  "days": 365,     "ax": axes[0]},
    {"title": "Recent 3 Years", "days": 3 * 365, "ax": axes[1]},
    {"title": "Recent 5 Years", "days": 5 * 365, "ax": axes[2]},
]

for p in periods:
    ax  = p["ax"]
    cutoff   = end_date - datetime.timedelta(days=p["days"])
    filtered = data.loc[cutoff.strftime("%Y-%m-%d"):]

    ax.set_facecolor("#1a1d27")
    ax.plot(filtered.index, filtered["10Y Treasury"],
            label="10Y (^TNX)", color="#4fa3e0", linewidth=2)
    ax.plot(filtered.index, filtered["2Y Treasury"],
            label="2Y  (^2YR)", color="#f0a500", linewidth=2)

    ax.set_title(f"US Treasury Yields — {p['title']}",
                 fontsize=13, fontweight="bold", color="white", pad=10)
    ax.set_ylabel("Yield (%)", fontsize=11, color="#aaaaaa")
    ax.tick_params(colors="#aaaaaa")
    ax.grid(True, linestyle="--", alpha=0.3, color="#555555")
    ax.legend(loc="upper left", framealpha=0.3,
              labelcolor="white", facecolor="#2a2d3a")

    for spine in ax.spines.values():
        spine.set_edgecolor("#333344")

    # 최고/최저 표시
    for col, color in [("10Y Treasury", "#4fa3e0"), ("2Y Treasury", "#f0a500")]:
        col_data = filtered[col].dropna()
        if col_data.empty:
            continue
        hi = col_data.max()
        lo = col_data.min()
        ax.axhline(hi, linestyle=":", linewidth=0.8, color=color, alpha=0.5)
        ax.axhline(lo, linestyle=":", linewidth=0.8, color=color, alpha=0.5)
        ax.text(filtered.index[-1], hi,
                f" {col[:2]} Hi {hi:.2f}%", color=color,
                fontsize=8, va="bottom", ha="right")
        ax.text(filtered.index[-1], lo,
                f" {col[:2]} Lo {lo:.2f}%", color=color,
                fontsize=8, va="top", ha="right")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

today_str = end_date.strftime("%Y-%m-%d")
fig.suptitle(f"US Treasury Yield Monitor  |  {today_str}",
             fontsize=15, fontweight="bold", color="white", y=1.01)
plt.tight_layout()

# ── 3. 메모리에서 이미지 버퍼로 저장 ─────────────────
buf = io.BytesIO()
plt.savefig(buf, format="png", dpi=150,
            bbox_inches="tight", facecolor=fig.get_facecolor())
buf.seek(0)
plt.close()

# ── 4. 텔레그램 전송 ──────────────────────────────────
# 현재 금리 값 가져오기
latest = data.dropna().iloc[-1]
rate_10y = latest["10Y Treasury"]
rate_2y  = latest["2Y Treasury"]
spread   = rate_10y - rate_2y
spread_sign = "▲" if spread >= 0 else "▼"

caption = (
    f"📊 *US Treasury Yield Monitor*\n"
    f"📅 {today_str}\n\n"
    f"🔵 10Y: *{rate_10y:.2f}%*\n"
    f"🟠  2Y: *{rate_2y:.2f}%*\n"
    f"📐 Spread (10Y−2Y): *{spread:+.2f}%* {spread_sign}\n\n"
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


import streamlit as st
import pandas as pd
import numpy as np
import scipy
import scipy.stats as stats

import matplotlib.pyplot as plt
from datetime import datetime
from scipy.fft import rfft, rfftfreq
import math
# === Color-coded Future Wave Zones ===
from matplotlib.collections import LineCollection

# Add this at the top after imports

# ======================= CONFIG ==========================
st.set_page_config(page_title="CYA Quantum Tracker", layout="wide")
st.title("🔥 CYA MOMENTUM TRACKER: Phase 1 + 2 + 3 + 4")

# ================ SESSION STATE INIT =====================
if "roundsc" not in st.session_state:
    st.session_state.roundsc = []
if "ga_pattern" not in st.session_state:
    st.session_state.ga_pattern = None
if "forecast_msi" not in st.session_state:
    st.session_state.forecast_msi = []

# ================ CONFIGURATION SIDEBAR ==================
with st.sidebar:
    st.header("⚙️ QUANTUM PARAMETERS")
    WINDOW_SIZE = st.slider("MSI Window Size", 5, 100, 20)
    PINK_THRESHOLD = st.number_input("Pink Threshold", value=10.0)
    STRICT_RTT = st.checkbox("Strict RTT Mode", value=False)
    if st.button("🔄 Full Reset", help="Clear all historical data"):
        st.session_state.roundsc = []
        st.rerun()
    # 🔥 Clear cached functions (wave features, FFTs, BBs)
    if st.button("🧹 Clear Cache", help="Force harmonic + MSI recalculation"):
        st.cache_data.clear()  # 💡 Streamlit’s built-in cache clearer
        st.success("Cache cleared — recalculations will run fresh.")
        
# =================== ROUND ENTRY ========================
st.subheader("Manual Round Entry")
mult = st.number_input("Enter round multiplier", min_value=0.01, step=0.01)

if st.button("➕ Add Round"):
    score = 2 if mult >= PINK_THRESHOLD else (1 if mult >= 2.0 else -1)
    st.session_state.roundsc.append({
        "timestamp": datetime.now(),
        "multiplier": mult,
        "score": score
    })

# =================== CONVERT TO DATAFRAME ================
df = pd.DataFrame(st.session_state.roundsc)

def rrqi(df, window=30):
    recent = df.tail(window)
    blues = len(recent[recent['type'] == 'Blue'])
    purples = len(recent[recent['type'] == 'Purple'])
    pinks = len(recent[recent['type'] == 'Pink'])
    quality = (purples + 2*pinks - blues) / window
    return round(quality, 2)

# === TPI CALCULATIONS ===
def calculate_purple_pressure(df, window=10):
    recent = df.tail(window)
    purple_scores = recent[recent['type'] == 'Purple']['score']
    if len(purple_scores) == 0:
        return 0
    return purple_scores.sum() / window

def calculate_blue_decay(df, window=10):
    recent = df.tail(window)
    blue_scores = recent[recent['type'] == 'Blue']['multiplier']
    if len(blue_scores) == 0:
        return 0
    decay = np.mean([2.0 - b for b in blue_scores])  # The lower the blue, the higher the decay
    return decay * (len(blue_scores) / window)

def compute_tpi(df, window=10):
    pressure = calculate_purple_pressure(df, window)
    decay = calculate_blue_decay(df, window)
    return round(pressure - decay, 2)

def bollinger_bands(series, window, num_std=2):
    rolling_mean = series.rolling(window).mean()
    rolling_std = series.rolling(window).std()
    upper_band = rolling_mean + num_std * rolling_std
    lower_band = rolling_mean - num_std * rolling_std
    return rolling_mean, upper_band, lower_band

# === Phase Tracker & Harmonic Channel Assistant ===

def detect_dominant_cycle(scores):
    N = len(scores)
    if N < 20:
        return None
    T = 1
    yf = rfft(scores - np.mean(scores))
    xf = rfftfreq(N, T)
    dominant_freq = xf[np.argmax(np.abs(yf[1:])) + 1]
    if dominant_freq == 0:
        return None
    return round(1 / dominant_freq)

def get_phase_label(position, cycle_length):
    pct = (position / cycle_length) * 100
    if pct <= 16:
        return "Birth Phase", pct
    elif pct <= 33:
        return "Ascent Phase", pct
    elif pct <= 50:
        return "Peak Phase", pct
    elif pct <= 67:
        return "Post-Peak", pct
    elif pct <= 84:
        return "Falling Phase", pct
    else:
        return "End Phase", pct

# Function to map wave position to color
def get_zone_color(pct):
    if pct <= 33:
        return 'green'
    elif pct <= 50:
        return 'gold'
    elif pct <= 67:
        return 'orange'
    else:
        return 'red'


# Only run heavy calculations if new round was added
@st.cache_data(show_spinner=False)
def analyze_data(data, pink_threshold, window_size):
    df = data.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["type"] = df["multiplier"].apply(lambda x: "Pink" if x >= PINK_THRESHOLD else ("Purple" if x >= 2 else "Blue"))
    df["msi"] = df["score"].rolling(WINDOW_SIZE).sum()
    df["momentum"] = df["score"].cumsum()
            # === Define latest_msi safely ===
    latest_msi = df["msi"].iloc[-1] if not df["msi"].isna().all() else 0
    latest_tpi = compute_tpi(df, window=WINDOW_SIZE)
    
# Multi-window BBs on MSI

    df["bb_mid_20"], df["bb_upper_20"], df["bb_lower_20"] = bollinger_bands(df["msi"], 20, 2)
    df["bb_mid_10"], df["bb_upper_10"], df["bb_lower_10"] = bollinger_bands(df["msi"], 10, 1.5)
    df["bb_mid_40"], df["bb_upper_40"], df["bb_lower_40"] = bollinger_bands(df["msi"], 40, 2.5)
    df['bandwidth'] = df["bb_upper_10"] - df["bb_lower_10"]  # Width of the band
    
    # Compute slope (1st derivative) for upper/lower bands
    df['upper_slope'] = df["bb_upper_10"].diff()
    df['lower_slope'] = df["bb_lower_10"].diff()
    
    # Compute acceleration (2nd derivative) for upper/lower bands
    df['upper_accel'] = df['upper_slope'].diff()
    df['lower_accel'] = df['lower_slope'].diff()
    
        # How fast the band is expanding or shrinking
    df['bandwidth_delta'] = df['bandwidth'].diff()
        
        # Pull latest values from the last row
    latest = df.iloc[-1]
    
         # Prepare and safely round/format outputs, avoiding NoneType formatting
    def safe_round(val, precision=4):
        return round(val, precision) if pd.notnull(val) else None
    
        
    if len(df["score"].fillna(0).values) > 20:
            
        upper_slope = round(safe_round(latest['upper_slope'])* 100),
        lower_slope = round(safe_round(latest['lower_slope'])* 100),
        upper_accel = round(safe_round(latest['upper_accel'])* 100),
        lower_accel = round(safe_round(latest['lower_accel'])* 100),
        bandwidth = round(safe_round(latest['bandwidth'])),
        bandwidth_delta = round(safe_round(latest['bandwidth_delta'])* 100),
           
    else:
            upper_slope = safe_round(latest['upper_slope']),
            lower_slope = safe_round(latest['lower_slope']),
            upper_accel = safe_round(latest['upper_accel']),
            lower_accel = safe_round(latest['lower_accel']),
            bandwidth = safe_round(latest['bandwidth']),
            bandwidth_delta = safe_round(latest['bandwidth_delta']),
              
        
    
        
    
        
    df["bb_squeeze"] = df["bb_upper_10"] - df["bb_lower_10"]
    df["bb_squeeze_flag"] = df["bb_squeeze"] < df["bb_squeeze"].rolling(5).quantile(0.25)
    
    
        # === Harmonic Cycle Estimation ===
    
    scores = df["score"].fillna(0).values
    N = len(scores)
    T = 1
        
        # === Harmonic Analysis ===
    dominant_cycle = detect_dominant_cycle(scores)
        
    if dominant_cycle:
        current_round_position = len(scores) % dominant_cycle
        wave_label, wave_pct = get_phase_label(current_round_position, dominant_cycle)
        
            # Recompute FFT for wave fitting
        yf = rfft(scores - np.mean(scores))
        xf = rfftfreq(N, T)
        idx_max = np.argmax(np.abs(yf[1:])) + 1
        dominant_freq = xf[idx_max]
            
            # Harmonic wave fit + forecast
        phase = np.angle(yf[idx_max])
    
            # === Harmonic Fit (Past)
        x_past = np.arange(N)  # Safe, aligned x for past
        harmonic_wave = np.sin(2 * np.pi * dominant_freq * x_past + phase)
        dom_slope = np.polyfit(np.arange(N), harmonic_wave, 1)[0] if N > 1 else 0
    
            # === Harmonic Forecast (Future)
        forecast_len = 5
        future_x = np.arange(N, N + forecast_len)
        harmonic_forecast = np.sin(2 * np.pi * dominant_freq * future_x + phase)
        forecast_times = [df["timestamp"].iloc[-1] + pd.Timedelta(seconds=5 * i) for i in range(forecast_len)]

             # Secondary harmonic (micro-wave) in 8–12 range
        mask_micro = (xf > 0.08) & (xf < 0.15)
        micro_idx = np.argmax(np.abs(yf[mask_micro])) + 1 if np.any(mask_micro) else 0
        micro_freq = xf[micro_idx] if micro_idx < len(xf) else 0
        micro_phase = np.angle(yf[micro_idx]) if micro_idx < len(yf) else 0
        micro_wave = np.sin(2 * np.pi * micro_freq * np.arange(N) + micro_phase)
        micro_slope = np.polyfit(np.arange(N), micro_wave, 1)[0] if N > 1 else 0
        
            # Energy Integrity Score (EIS)
        blues = len(df[df["score"] < 0])
        purples = len(df[(df["score"] == 1.0) | (df["score"] == 1.5)])
        pinks = len(df[df["score"] >= 2.0])
        eis = (purples * 1 + pinks * 2) - blues
        
            # Alignment test
        if dom_slope > 0 and micro_slope > 0:
            interference = "Constructive (Aligned)"
        elif dom_slope * micro_slope < 0:
            interference = "Destructive (Conflict)"
        else:
            interference = "Neutral or Unclear"
        
            # === Channel Bounds (1-STD deviation)
        amplitude = np.std(scores)
        upper_channel = harmonic_forecast + amplitude
        lower_channel = harmonic_forecast - amplitude
    
            
    else:
            current_round_position = None
            harmonic_wave = []
            micro_wave = []
            harmonic_forecast = []
            forecast_times = []
            wave_label = None
            wave_pct = None
            dom_slope = 0
            micro_slope = 0
            eis = 0
            interference = "N/A"


    
            
    return df, latest_msi, latest_tpi, upper_slope, lower_slope, upper_accel, lower_accel, bandwidth, bandwidth_delta, dominant_cycle, current_round_position, wave_label, wave_pct, dom_slope, micro_slope, eis, interference, harmonic_wave, micro_wave, harmonic_forecast, forecast_times
    # === RRQI Calculation ===
    rrqi_val = rrqi(df, 30)
if not df.empty:
    (df, latest_msi, latest_tpi, upper_slope, lower_slope, upper_accel, lower_accel,
 bandwidth, bandwidth_delta, dominant_cycle, current_round_position,
 wave_label, wave_pct, dom_slope, micro_slope, eis, interference,
 harmonic_wave, micro_wave, harmonic_forecast, forecast_times) = analyze_data(df, PINK_THRESHOLD, WINDOW_SIZE)
   
    # === RRQI Calculation ===
    rrqi_val = rrqi(df, 30)

    
    scores = df["score"].fillna(0).values
    N = len(scores)

    

    
    amplitude = np.std(scores)
    upper_channel = harmonic_forecast + amplitude
    lower_channel = harmonic_forecast - amplitude

    
    st.metric("number of rounds", N)
    # ================== MSI CHART =======================
    st.subheader("Momentum Score Index (MSI)")
    fig, ax = plt.subplots(figsize=(12, 4))
    fig.patch.set_facecolor('#0f172a')
    ax.set_facecolor('#EBF5FF')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    ax.spines['bottom'].set_color('white')
    ax.spines['left'].set_color('white')
    # === Zero Axis Line for Orientation ===
    ax.axhline(0, color='black', linestyle='--', linewidth=3, alpha=0.8)
    ax.plot(df["timestamp"], df["msi"], color='black', lw=2, label="MSI")

    # MSI Zones
    ax.fill_between(df["timestamp"], df["msi"], where=(df["msi"] >= 6), color='#905AAF', alpha=0.3, label="Burst Zone")
    ax.fill_between(df["timestamp"], df["msi"], where=((df["msi"] > 3) & (df["msi"] < 6)), color='#00ffff', alpha=0.3, label="Surge Zone")
    ax.fill_between(df["timestamp"], df["msi"], where=(df["msi"] <= -3), color='#ff3333', alpha=0.8, label="Pullback Zone")

    # Plot Bollinger Bands
    ax.plot(df["timestamp"], df["bb_upper_20"], color='maroon', linestyle='--', alpha=1.0, )
    ax.plot(df["timestamp"], df["bb_lower_20"], color='maroon', linestyle='--', alpha=1.0, )
    ax.plot(df["timestamp"], df["bb_mid_20"], color='maroon', linestyle=':', alpha=1.0)
    
    # Optional: Short-term band
    ax.plot(df["timestamp"], df["bb_upper_10"], color='#0AEFFF', linestyle='--', alpha=1.0)
    ax.plot(df["timestamp"], df["bb_lower_10"], color='#0AEFFF', linestyle='--', alpha=1.0)

    # Optional: long-term band
    ax.plot(df["timestamp"], df["bb_upper_40"], color='black', linestyle='--', alpha=1.0)
    ax.plot(df["timestamp"], df["bb_lower_40"], color='black', linestyle='--', alpha=1.0)
    

    # Plot squeeze zones
    for i in range(len(df)):
        if df["bb_squeeze_flag"].iloc[i]:
            ax.axvspan(df["timestamp"].iloc[i] - pd.Timedelta(minutes=0.25),
                       df["timestamp"].iloc[i] + pd.Timedelta(minutes=0.25),
                       color='purple', alpha=0.9)

    # RRQI line (optional bubble)
    if rrqi_val:
        ax.axhline(rrqi_val, color='cyan', linestyle=':', alpha=0.9, label='RRQI Level')
        
    if harmonic_wave is not None and len(harmonic_wave) == N:
        past_times = df["timestamp"].iloc[-N:].tolist()
        ax.plot(past_times, harmonic_wave, label="Harmonic Fit", color='blue', linewidth=2)
        ax.plot(past_times, micro_wave, label="Micro Wave", linestyle='dashdot', color='black')

    # Build future times for forecast
    if harmonic_forecast is not None and len(harmonic_forecast) > 0:
        forecast_times = [df["timestamp"].iloc[-1] + pd.Timedelta(seconds=5 * i) for i in range(len(harmonic_forecast))]
    
        # Forecast Channel
    #if lower_channel is not None and upper_channel is not None:
        #ax.fill_between(forecast_times, lower_channel, upper_channel, color='green', alpha=0.2, label="Forecast Channel")
        
        # Forecast Segments (stepwise)
    for i in range(len(harmonic_forecast) - 1):
        color = 'green'  # Optional: dynamic gradient if needed
        ax.plot([forecast_times[i], forecast_times[i + 1]],
            [harmonic_forecast[i], harmonic_forecast[i + 1]],
                color=color, linewidth=2)
    
        # Dashed forecast overlay
    ax.plot(forecast_times, harmonic_forecast, color='green', linestyle='--', alpha=0.5, label="Forecast (Next)")

    
    #if harmonic_forecast is not None and len(harmonic_forecast) > 0:
        #for i in range(len(future_x)-1):
            #color = 'green' #if harmonic_forecast[i+1] > harmonic_forecast[i] else 'red'
            #ax.plot([df["timestamp"].iloc[-1] + pd.Timedelta(seconds=5*i),
                     #df["timestamp"].iloc[-1] + pd.Timedelta(seconds=5*(i+1))],
                    #[harmonic_forecast[i], harmonic_forecast[i+1]], color=color, linewidth=2)
             #ax.axvline(N - 1, color='red', linestyle=':', label='Now')

         
    ax.set_title("MSI Tactical Map + Harmonics", color='black')
    
    ax.legend()
    plot_slot = st.empty()
    with plot_slot.container():
        st.pyplot(fig)
    

    # RRQI Status
    st.metric("🧠 RRQI", rrqi_val, delta="Last 30 rounds")
    if rrqi_val >= 0.3:
        st.success("🔥 Happy Hour Detected — Tactical Entry Zone")
    elif rrqi_val <= -0.2:
        st.error("⚠️ Dead Zone — Avoid Aggressive Entries")
    else:
        st.info("⚖️ Mixed Zone — Scout Cautiously")

    
        
    if not df["bb_upper_20"].isna().all():
        future_upper = df["bb_upper_20"].iloc[-1]
        future_lower = df["bb_lower_20"].iloc[-1]
        st.info(f"Forecast MSI Range (Next Rounds): {future_lower:.2f} → {future_upper:.2f}")


    # === Streamlit Display ===
    st.subheader("📡 Harmonic Phase Tracker")
    if wave_label is not None and wave_pct is not None:
        st.metric("Dominant Cycle Length", f"{dominant_cycle} rounds")
        st.metric("Wave Position", f"Round {current_round_position} of {dominant_cycle}")
        st.metric("Wave Phase", f"{wave_label} ({wave_pct:.1f}%)")
        st.metric("EIS", eis)
        st.metric("Dominant Slope", f"{dom_slope:.3f}")
        st.metric("Micro Slope", f"{micro_slope:.3f}")
        st.info(f"ℹ️ Wave Interference: {interference}")


        
    else:
        st.metric("Wave Phase", "N/A")

    
    st.subheader("💹 Bollinger Bands stats")
    if upper_slope is not None:
        
        st.metric("upper slope", f"{upper_slope}%")#upper_accel
        st.metric("upper acceleration ", f"{upper_accel }%")
        st.metric("lower slope", f"{lower_slope}%")
        st.metric("lower acceleration ", f"{lower_accel }%")
        st.metric("bandwidth  ", f"{bandwidth } Scale (0-20)")
        st.metric("bandwidth delta  ", f"{bandwidth_delta }% shift from last round")
    else:
        st.metric("Wave Phase", "N/A")



    
    # === TPI INTERPRETATION HUD ===
    st.metric("TPI", f"{latest_tpi}", delta="Trend Pressure")
    
    if latest_msi >= 3:
        if latest_tpi > 0.5:
            st.success("🔥 Valid Surge — Pressure Confirmed")
        elif latest_tpi < -0.5:
            st.warning("⚠️ Hollow Surge — Likely Trap")
        else:
            st.info("🧐 Weak Surge — Monitor Closely")
    else:
        st.info("Trend too soft — TPI not evaluated.")

    
    # Log
    with st.expander("📄 Review / Edit Recent Rounds"):
        edited = st.data_editor(df.tail(30), use_container_width=True, num_rows="dynamic")
        if st.button("✅ Commit Edits"):
            st.session_state.roundsc = edited.to_dict('records')
            st.rerun()

else:
    st.info("Enter at least 1 round to begin analysis.")

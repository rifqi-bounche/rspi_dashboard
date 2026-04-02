import streamlit as st
import pandas as pd
import re
from sqlalchemy import create_engine
import base64
from datetime import date, timedelta

st.set_page_config(page_title="Spreadsheet Dashboard", layout="wide")

st.markdown("""<style>
@media print {
    [data-testid="stSidebar"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    button, .stButton { display: none !important; }
    .main .block-container { padding: 0 !important; max-width: 100% !important; }
    body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
</style>""", unsafe_allow_html=True)

# =========================================================
# LOGIN
# =========================================================
def login_page():
    st.markdown("""
        <div style="max-width:400px;margin:80px auto;padding:40px;
            background:#fff;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,0.10);">
            <h2 style="text-align:center;margin-bottom:8px;">📊 RSPI Dashboard</h2>
            <p style="text-align:center;color:#888;margin-bottom:24px;">Silakan login untuk melanjutkan</p>
        </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        st.markdown("### 🔐 Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        if (username == st.secrets["auth"]["username"] and 
            password == st.secrets["auth"]["password"]):
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.rerun()
        else:
            st.error("❌ Username atau password salah")

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login_page()
    st.stop()

# =========================================================
# DB CONNECTION
# =========================================================
DB_HOST = st.secrets["db"]["host"]
DB_PORT = st.secrets["db"]["port"]
DB_USER = st.secrets["db"]["user"]
DB_PASS = st.secrets["db"]["password"]
DB_NAME = st.secrets["db"]["name"]

TABLE_SENTIMENT = "rspi_instagram"
conn_str = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(conn_str)

# =========================================================
# HELPER FUNCTIONS
# =========================================================
def safe_base64_decode(x):
    try:
        if x is None: return ""
        return base64.b64decode(x).decode("utf-8", errors="ignore")
    except:
        return x

def hhmmss_to_seconds(t):
    try:
        h, m, s = str(t).split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except:
        return 0

def seconds_to_hhmmss(sec):
    sec = int(sec)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02}:{m:02}:{s:02}"

def calc_delta(current, previous):
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100

def extract_hashtags(text):
    try:
        return " ".join(re.findall(r"#\w+", str(text)))
    except:
        return ""

def extract_shortcode(url):
    try:
        parts = [x for x in str(url).rstrip("/").split("/") if x]
        return parts[-1]
    except:
        return ""

# =========================================================
# LOAD DATA
# =========================================================
try:
    df_db = pd.read_sql(f"SELECT * FROM `{TABLE_SENTIMENT}`", engine)
    df_db.columns = df_db.columns.str.lower().str.strip()
except Exception as e:
    st.error(f"❌ Gagal load database: {e}")
    st.stop()

for col in ["caption"]:
    if col in df_db.columns:
        df_db[col] = df_db[col].apply(safe_base64_decode)

for col in ['views', 'ig_reels_avg_watch_time', 'reels_skip_rate']:
    if col in df_db.columns:
        df_db[col] = pd.to_numeric(df_db[col], errors='coerce').fillna(0)

if 'timestamp' in df_db.columns:
    df_db['timestamp'] = pd.to_datetime(df_db['timestamp'], errors='coerce')

df_db['_hashtags']      = df_db['caption'].apply(extract_hashtags)
df_db['_shortcode']     = df_db['permalink'].apply(extract_shortcode)
df_db['_campaign_list'] = df_db['campaign'].apply(
    lambda x: [c.strip() for c in str(x).replace(',', ' ').split() if c.strip().startswith('#')] if pd.notna(x) else []
)

# =========================================================
# SIDEBAR FILTER
# =========================================================
st.title("📊 RSPI Instagram Dashboard")

with st.sidebar:
    st.markdown(f"👤 **{st.session_state['username']}**")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.rerun()

    st.header("🔽 Filter")

    all_campaigns = sorted(set(
        tag for tags in df_db['_campaign_list'] for tag in tags
    ))
    selected_campaign = st.selectbox("Campaign", ["Semua"] + all_campaigns)
    selected_shortcode = st.text_input("Shortcode", placeholder="Masukkan shortcode...")

    st.markdown("#### 📅 Filter Tanggal")
    if 'timestamp' in df_db.columns:
        min_date = df_db['timestamp'].min().date()
        max_date = df_db['timestamp'].max().date()
        today = date.today()
        default_start = today - timedelta(days=29)
        cur_range = st.date_input("Current Period", [default_start, today], key="cur")

        if len(cur_range) == 2:
            delta_days     = (cur_range[1] - cur_range[0]).days + 1
            auto_pre_end   = cur_range[0] - timedelta(days=1)
            auto_pre_start = auto_pre_end - timedelta(days=delta_days - 1)
            st.info(f"🔄 Compare: {auto_pre_start} s/d {auto_pre_end}")
            pre_range = (auto_pre_start, auto_pre_end)
        else:
            pre_range = None
    else:
        cur_range = None
        pre_range = None

# sisa kode (APPLY FILTER, METRICS, TOP 3, TABEL) tetap sama seperti sebelumnya ...
# =========================================================
# APPLY FILTER
# =========================================================
df = df_db.copy()

if selected_campaign != "Semua":
    df = df[df['_campaign_list'].apply(lambda x: selected_campaign in x)]
if selected_shortcode:
    df = df[df['_shortcode'] == selected_shortcode.strip()]

# Current period
if cur_range and len(cur_range) == 2 and 'timestamp' in df.columns:
    df_cur = df[(df['timestamp'].dt.date >= cur_range[0]) & (df['timestamp'].dt.date <= cur_range[1])]
else:
    df_cur = df.copy()

# Previous period
if pre_range and len(pre_range) == 2 and 'timestamp' in df.columns:
    df_pre = df[(df['timestamp'].dt.date >= pre_range[0]) & (df['timestamp'].dt.date <= pre_range[1])]
else:
    df_pre = None

# =========================================================
# HITUNG METRICS
# =========================================================
def get_metrics(df_data):
    return {
        "total_views"         : int(df_data['views'].sum()),
        "total_post"          : df_data['permalink'].nunique(),
        "avg_views"           : int(df_data['views'].mean()) if len(df_data) > 0 else 0,
        "avg_watch_time"      : df_data['ig_reels_avg_watch_time'].mean() if len(df_data) > 0 else 0,
        "avg_watch_total_time": seconds_to_hhmmss(
            df_data['ig_reels_video_view_total_time']
            .apply(hhmmss_to_seconds)
            .mean()
        ) if len(df_data) > 0 else "00:00:00",
        "avg_skip_rate"       : df_data['reels_skip_rate'].mean() if len(df_data) > 0 else 0,
    }

cur = get_metrics(df_cur)
pre = get_metrics(df_pre) if df_pre is not None else None

def fmt_delta(key):
    if pre is None:
        return "+0.0%"
    d = calc_delta(cur[key], pre[key])
    return f"{d:+.1f}%"

def fmt_delta_hhmmss(key):
    if pre is None:
        return "+0.0%"
    cur_sec = hhmmss_to_seconds(cur[key])
    pre_sec = hhmmss_to_seconds(pre[key])
    d = calc_delta(cur_sec, pre_sec)
    return f"{d:+.1f}%"

# =========================================================
# OVERVIEW METRICS
# =========================================================
st.subheader("📊 Overview Metrics")

col1, col2 = st.columns(2)
col1.metric("👀 Total Views", f"{cur['total_views']:,}", fmt_delta("total_views"))
col2.metric("📝 Total Post",  f"{cur['total_post']:,}",  fmt_delta("total_post"))

col1, col2, col3, col4 = st.columns(4)
col1.metric("🎬 Avg Views/Post",       f"{cur['avg_views']:,}",         fmt_delta("avg_views"))
col2.metric("⏱️ Avg Watch Time",       f"{cur['avg_watch_time']:.2f}s", fmt_delta("avg_watch_time"))
skip_delta = calc_delta(cur['avg_skip_rate'], pre['avg_skip_rate']) if pre is not None else 0.0
col3.metric("⏭️ Avg Skip Rate",        f"{cur['avg_skip_rate']:.2f}%",  f"{skip_delta:+.1f}%", delta_color="inverse")
col4.metric("🕒 Avg Video Total Time", cur['avg_watch_total_time'],      fmt_delta_hhmmss("avg_watch_total_time"))

# =========================================================
# TOP 3 BY VIEWS
# =========================================================
st.markdown("### 🔥 Top 3 Instagram Posts by Views")
df_top_views = df_cur[["permalink", "views"]].sort_values("views", ascending=False).head(3)

if not df_top_views.empty:
    cols = st.columns(3)
    for idx, (_, row) in enumerate(df_top_views.iterrows()):
        post_url = row["permalink"].rstrip("/")
        with cols[idx]:
            st.markdown(f"""<div style="background:linear-gradient(135deg,#f093fb 0%,#f5576c 100%);
                color:white;padding:6px 8px;border-radius:6px;text-align:center;
                font-weight:600;font-size:12px;margin-bottom:6px;">
                👀 {int(row["views"]):,} Views</div>""", unsafe_allow_html=True)
            try:
                shortcode = [x for x in post_url.split("/") if x][-1]
                st.components.v1.html(
                    f'<iframe src="https://www.instagram.com/p/{shortcode}/embed/" width="100%" height="460" frameborder="0" scrolling="no" style="border:none;"></iframe>',
                    height=480, scrolling=False)
            except:
                st.markdown(f'<a href="{post_url}" target="_blank">📸 Lihat Post</a>', unsafe_allow_html=True)

# =========================================================
# TOP 3 BY Highest Avg Watch Time
# =========================================================
st.markdown("### 🔥 Top 3 Instagram Posts by Highest Avg Watch Time")
df_top_watch = df_cur[["permalink", "ig_reels_avg_watch_time"]].sort_values("ig_reels_avg_watch_time", ascending=False).head(3)

if not df_top_watch.empty:
    cols = st.columns(3)
    for idx, (_, row) in enumerate(df_top_watch.iterrows()):
        post_url = row["permalink"].rstrip("/")
        with cols[idx]:
            st.markdown(f"""<div style="background:linear-gradient(135deg,#f093fb 0%,#f5576c 100%);
                color:white;padding:6px 8px;border-radius:6px;text-align:center;
                font-weight:600;font-size:12px;margin-bottom:6px;">
                ⏱️ {row['ig_reels_avg_watch_time']:.2f}s Avg Watch Time</div>""", unsafe_allow_html=True)
            try:
                shortcode = [x for x in post_url.split("/") if x][-1]
                st.components.v1.html(
                    f'<iframe src="https://www.instagram.com/p/{shortcode}/embed/" width="100%" height="460" frameborder="0" scrolling="no" style="border:none;"></iframe>',
                    height=480, scrolling=False)
            except:
                st.markdown(f'<a href="{post_url}" target="_blank">📸 Lihat Post</a>', unsafe_allow_html=True)

# =========================================================
# TOP 3 BY Highest Video Total Time
# =========================================================
st.markdown("### 🔥 Top 3 Instagram Posts by Highest Video Total Time")
df_top_totaltime = df_cur[["permalink", "ig_reels_video_view_total_time"]].copy()
df_top_totaltime["_seconds"] = df_top_totaltime["ig_reels_video_view_total_time"].apply(hhmmss_to_seconds)
df_top_totaltime = df_top_totaltime.sort_values("_seconds", ascending=False).head(3)

if not df_top_totaltime.empty:
    cols = st.columns(3)
    for idx, (_, row) in enumerate(df_top_totaltime.iterrows()):
        post_url = row["permalink"].rstrip("/")
        with cols[idx]:
            st.markdown(f"""<div style="background:linear-gradient(135deg,#43e97b 0%,#38f9d7 100%);
                color:white;padding:6px 8px;border-radius:6px;text-align:center;
                font-weight:600;font-size:12px;margin-bottom:6px;">
                🕒 {row['ig_reels_video_view_total_time']} Video Total Time</div>""", unsafe_allow_html=True)
            try:
                shortcode = [x for x in post_url.split("/") if x][-1]
                st.components.v1.html(
                    f'<iframe src="https://www.instagram.com/p/{shortcode}/embed/" width="100%" height="460" frameborder="0" scrolling="no" style="border:none;"></iframe>',
                    height=480, scrolling=False)
            except:
                st.markdown(f'<a href="{post_url}" target="_blank">📸 Lihat Post</a>', unsafe_allow_html=True)

# =========================================================
# TOP 3 BY Lowest Skip Rate
# =========================================================
st.markdown("### 🏆 Top 3 Instagram Posts by Lowest Skip Rate")
df_top_skip = df_cur[["permalink", "reels_skip_rate"]].copy()
df_top_skip["reels_skip_rate"] = pd.to_numeric(df_top_skip["reels_skip_rate"], errors='coerce').fillna(0)
df_top_skip = df_top_skip.sort_values("reels_skip_rate", ascending=True).head(3)

if not df_top_skip.empty:
    cols = st.columns(3)
    for idx, (_, row) in enumerate(df_top_skip.iterrows()):
        post_url = row["permalink"].rstrip("/")
        with cols[idx]:
            st.markdown(f"""<div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                color:white;padding:6px 8px;border-radius:6px;text-align:center;
                font-weight:600;font-size:12px;margin-bottom:6px;">
                ⏭️ {row['reels_skip_rate']:.2f}% Skip Rate</div>""", unsafe_allow_html=True)
            try:
                shortcode = [x for x in post_url.split("/") if x][-1]
                st.components.v1.html(
                    f'<iframe src="https://www.instagram.com/p/{shortcode}/embed/" width="100%" height="460" frameborder="0" scrolling="no" style="border:none;"></iframe>',
                    height=480, scrolling=False)
            except:
                st.markdown(f'<a href="{post_url}" target="_blank">📸 Lihat Post</a>', unsafe_allow_html=True)

# =========================================================
# TABEL BREAKDOWN
# =========================================================
st.subheader("📋 Tabel Breakdown")

df_table = df_cur.copy()
df_table['hashtag'] = df_table['caption'].apply(extract_hashtags)

df_breakdown = df_table[[
    'timestamp',
    'permalink',
    'caption',
    'hashtag',
    'views',
    'ig_reels_avg_watch_time',
    'ig_reels_video_view_total_time',
    'reels_skip_rate'
]].rename(columns={
    'timestamp'                      : 'Date',
    'permalink'                      : 'Link Post',
    'caption'                        : 'Caption',
    'hashtag'                        : 'Hashtag',
    'views'                          : 'Views',
    'ig_reels_avg_watch_time'        : 'Avg Watch Time (s)',
    'ig_reels_video_view_total_time' : 'Total Watch Time',
    'reels_skip_rate'                : 'Skip Rate (%)',
})

df_breakdown['Date'] = pd.to_datetime(df_breakdown['Date']).dt.strftime('%Y-%m-%d')

st.caption(f"Total: {len(df_breakdown):,} baris")
st.dataframe(
    df_breakdown,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Link Post"          : st.column_config.LinkColumn("Link Post",           display_text="🔗 View Post", width="small"),
        "Caption"            : st.column_config.TextColumn("Caption",             width="medium", max_chars=30),
        "Hashtag"            : st.column_config.TextColumn("Hashtag",             width="medium", max_chars=30),
        "Date"               : st.column_config.TextColumn("Date",                width="small"),
        "Views"              : st.column_config.NumberColumn("Views",             width="small"),
        "Avg Watch Time (s)" : st.column_config.NumberColumn("Avg Watch Time (s)", width="small"),
        "Total Watch Time"   : st.column_config.TextColumn("Total Watch Time",    width="small"),
        "Skip Rate (%)"      : st.column_config.NumberColumn("Skip Rate (%)",     width="small"),
    }
)


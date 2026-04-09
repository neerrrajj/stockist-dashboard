"""
app.py  –  Super Stockist Dashboard
Run with:  uv run streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Stockist Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global styles ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Sora:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Sora', sans-serif;
}

/* Remove top padding */
.main .block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 2rem;
    max-width: 1400px;
}

/* Force 2 columns on mobile */
@media (max-width: 768px) {
    /* Target Streamlit column containers in horizontal blocks */
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        width: calc(50% - 1rem) !important;
        min-width: calc(50% - 1rem) !important;
        max-width: calc(50% - 1rem) !important;
        flex: 0 0 calc(50% - 1rem) !important;
    }
}

/* Remove sidebar padding */
section[data-testid="stSidebar"] .block-container {
    padding-top: 0.5rem !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0f0f14;
    border-right: 1px solid #1e1e2e;
}
section[data-testid="stSidebar"] * {
    color: #c9c9d6 !important;
}

/* Nav buttons - no border, left aligned, active highlight */
section[data-testid="stSidebar"] button[kind="secondary"],
section[data-testid="stSidebar"] button[kind="primary"] {
    background: transparent !important;
    border: none !important;
    color: #6b6b80 !important;
    font-size: 0.85rem !important;
    font-weight: 400 !important;
    padding: 0.4rem 0.6rem !important;
    margin-bottom: 0.1rem !important;
    border-radius: 6px !important;
    transition: all 0.15s ease !important;
    width: 100% !important;
}
section[data-testid="stSidebar"] button[kind="primary"] {
    background: #252536 !important;
    color: #e8e8f0 !important;
    font-weight: 500 !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:hover {
    background: #1a1a24 !important;
    color: #c9c9d6 !important;
}
/* Force left alignment on button content */
section[data-testid="stSidebar"] button {
    text-align: left !important;
}
section[data-testid="stSidebar"] button > div {
    justify-content: flex-start !important;
    text-align: left !important;
    width: 100% !important;
    display: flex !important;
    gap: 0.6rem !important;
}
section[data-testid="stSidebar"] button > div > p {
    text-align: left !important;
}

/* Metric cards */
div[data-testid="metric-container"] {
    background: #13131a;
    border: 1px solid #1e1e2e;
    border-radius: 12px;
    padding: 1rem 1.25rem;
}
div[data-testid="metric-container"] label {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.7rem !important;
    letter-spacing: 0.08em !important;
    color: #6b6b80 !important;
    text-transform: uppercase;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: #e8e8f0 !important;
}
div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-size: 0.75rem !important;
    font-family: 'DM Mono', monospace !important;
}

/* Page header */
.page-header {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid #1e1e2e;
    padding-bottom: 0.75rem;
}
.page-header h1 {
    font-size: 1.5rem;
    font-weight: 700;
    color: #e8e8f0;
    margin: 0;
}
.page-header span {
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    color: #6b6b80;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

/* Section label */
.section-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #6b6b80;
    margin-bottom: 0.5rem;
}

/* Alert / status pills */
.pill-red   { background:#2a1015; color:#f87171; border:1px solid #f87171; border-radius:6px; padding:2px 10px; font-size:0.7rem; font-family:'DM Mono',monospace; }
.pill-amber { background:#1f1a0e; color:#fbbf24; border:1px solid #fbbf24; border-radius:6px; padding:2px 10px; font-size:0.7rem; font-family:'DM Mono',monospace; }
.pill-green { background:#0e1f16; color:#4ade80; border:1px solid #4ade80; border-radius:6px; padding:2px 10px; font-size:0.7rem; font-family:'DM Mono',monospace; }

/* Dataframe tweaks */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* Divider */
hr { border-color: #1e1e2e !important; }
</style>
""", unsafe_allow_html=True)

# ── Load data ──────────────────────────────────────────────────────────────────
from data_loader import load_data

with st.spinner("Loading data…"):
    data = load_data()

sales       = data["sales"]
purchase    = data["purchase"]
payments    = data["payments"]
outstanding = data["outstanding"]
inventory   = data["inventory"]
batch       = data["batch"]
pricelist   = data["pricelist"]

# ── Sidebar navigation ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📦 Stockist")
    st.markdown("<div style='font-family:DM Mono,monospace;font-size:0.65rem;color:#6b6b80;letter-spacing:0.08em'>SUPER STOCKIST ANALYTICS</div>", unsafe_allow_html=True)
    st.divider()

    # Simplified page names
    pages = [
        ("home", "🏠", "Home"),
        ("products", "📦", "Products"),
        ("counters", "🏪", "Counters"),
        ("receivables", "📬", "Receivables"),
        ("inventory", "📊", "Inventory"),
    ]
    
    # Get current page from session state or default
    if "page" not in st.session_state:
        st.session_state.page = "home"
    
    # Create button navigation
    for key, icon, name in pages:
        is_active = st.session_state.page == key
        btn_type = "primary" if is_active else "secondary"
        if st.button(f"{icon} {name}", key=f"nav_{key}", use_container_width=True, type=btn_type):
            st.session_state.page = key
            st.rerun()
    
    st.divider()
    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown(f"<div style='font-family:DM Mono,monospace;font-size:0.6rem;color:#3a3a50'>Last loaded: {__import__('datetime').datetime.now().strftime('%d %b %H:%M')}</div>", unsafe_allow_html=True)

# ── Page routing ───────────────────────────────────────────────────────────────
page = st.session_state.page

if page == "home":
    from views import p1_home
    p1_home.render(sales, purchase, payments, outstanding, inventory, batch)
elif page == "products":
    from views import p2_products
    p2_products.render(sales, pricelist)
elif page == "counters":
    from views import p3_counters
    p3_counters.render(sales, payments, outstanding)
elif page == "receivables":
    from views import p4_receivables
    p4_receivables.render(sales, payments, outstanding)
elif page == "inventory":
    from views import p5_inventory
    p5_inventory.render(sales, inventory, batch, pricelist)

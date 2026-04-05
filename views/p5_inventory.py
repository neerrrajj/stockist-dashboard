"""pages/p5_inventory.py  –  Inventory & Restock Planning"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PLOT_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Sora, sans-serif", color="#c9c9d6"),
    xaxis=dict(gridcolor="#1e1e2e", linecolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    yaxis=dict(gridcolor="#1e1e2e", linecolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    margin=dict(l=10, r=10, t=40, b=10),
)

RESTOCK_DAYS = 30  # how many days supply to reorder for


def render(sales, inventory, batch, pricelist):
    st.markdown("""
    <div class='page-header'>
        <h1>Inventory & Restock Planning</h1>
        <span>Stock levels · Days remaining · Capital locked</span>
    </div>
    """, unsafe_allow_html=True)

    # today = pd.Timestamp.today().normalize()

    if sales.empty or inventory.empty:
        st.warning("Insufficient data.")
        return

    # ── Compute avg daily sales per product ───────────────────────────────────
    date_range_days = max((sales["Date"].max() - sales["Date"].min()).days, 1)
    daily_sales = (
        sales.groupby("Product")["Nos"].sum() / date_range_days
    ).reset_index()
    daily_sales.columns = ["Products", "Avg daily units"]

    # Merge with inventory
    inv = inventory.merge(daily_sales, on="Products", how="left")
    inv["Avg daily units"] = inv["Avg daily units"].fillna(0)
    inv["Days of stock"] = (
        inv["Closing Stock"] / inv["Avg daily units"].replace(0, pd.NA)
    )
    inv["Days of stock"] = inv["Days of stock"].apply(lambda x: round(x, 1) if pd.notna(x) else x)
    inv["Days of stock"] = inv["Days of stock"].fillna(999)  # never been sold = treat as infinite

    # Merge with batch for age info
    batch_agg = batch.groupby("Products").agg(
        Batch_days=("Inventory days", "max"),
        Batch_cost=("Discounted rate", "mean"),
    ).reset_index()
    inv = inv.merge(batch_agg, on="Products", how="left")

    # Merge weighted avg cost from pricelist
    inv = inv.merge(
        pricelist.rename(columns={"Product": "Products", "Weighted avg price": "Avg cost"}),
        on="Products", how="left"
    )

    # Restock quantity: enough for RESTOCK_DAYS based on avg velocity
    inv["Suggested restock"] = (inv["Avg daily units"] * RESTOCK_DAYS).round(0).astype(int)
    inv["Suggested restock value"] = (inv["Suggested restock"] * inv["Avg cost"].fillna(0)).round(0)

    # Capital efficiency: days of capital locked = Inventory value / (avg daily revenue)
    # Simpler: days of stock = how long current stock will last
    inv["Status"] = inv["Days of stock"].apply(
        lambda d: "🔴 Critical" if d < 7 else ("🟡 Low" if d < 15 else ("🟢 Good" if d < 60 else "🔵 Excess"))
    )

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_value   = inv["Inventory value"].clip(lower=0).sum()
    critical_cnt  = (inv["Days of stock"] < 7).sum()
    low_cnt       = ((inv["Days of stock"] >= 7) & (inv["Days of stock"] < 15)).sum()
    excess_cnt    = (inv["Days of stock"] >= 60).sum()
    avg_batch_age = inv["Batch_days"].mean()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: 
        st.metric("Total Inventory Value", f"₹{total_value:,.0f}")
    with c2: 
        st.metric("🔴 Critical (< 7d)", str(int(critical_cnt)))
    with c3: 
        st.metric("🟡 Low (7–15d)", str(int(low_cnt)))
    with c4: 
        st.metric("🔵 Excess (60d+)", str(int(excess_cnt)))
    with c5: 
        st.metric("Avg Batch Age", f"{avg_batch_age:.0f} days")

    st.divider()

    # ── Days of stock gauge bar chart ─────────────────────────────────────────
    st.markdown("<div class='section-label'>Days of stock remaining per product</div>", unsafe_allow_html=True)

    inv_plot = inv[inv["Days of stock"] < 200].sort_values("Days of stock")  # cap inf products

    COLOR_MAP = {
        "🔴 Critical": "#f87171",
        "🟡 Low": "#fbbf24",
        "🟢 Good": "#4ade80",
        "🔵 Excess": "#60a5fa",
    }

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=inv_plot["Days of stock"],
        y=inv_plot["Products"],
        orientation="h",
        marker_color=[COLOR_MAP.get(s, "#6b6b80") for s in inv_plot["Status"]],
        marker_line_width=0,
        customdata=inv_plot[["Closing Stock", "Avg daily units", "Status"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Days remaining: %{x:.0f}<br>"
            "Stock: %{customdata[0]:.0f} units<br>"
            "Velocity: %{customdata[1]:.2f} units/day<br>"
            "%{customdata[2]}<extra></extra>"
        ),
    ))
    fig.add_vline(x=15, line_dash="dot", line_color="#fbbf24",
                  annotation_text="15d", annotation_font_color="#fbbf24",
                  annotation_position="top")
    fig.add_vline(x=7, line_dash="dot", line_color="#f87171",
                  annotation_text="7d", annotation_font_color="#f87171",
                  annotation_position="top")
    fig.update_layout(
        **PLOT_THEME,
        height=max(320, len(inv_plot) * 26),
        xaxis_title="Days of stock remaining",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Restock recommendation table ──────────────────────────────────────────
    st.markdown(f"<div class='section-label'>Restock planner – {RESTOCK_DAYS}-day supply target</div>", unsafe_allow_html=True)

    restock_table = inv.sort_values("Days of stock")[[
        "Products", "Status", "Closing Stock", "Avg daily units",
        "Days of stock", "Suggested restock", "Suggested restock value",
    ]].rename(columns={
        "Avg daily units": "Units/Day",
        "Days of stock": "Days Left",
        "Suggested restock": f"Restock Qty ({RESTOCK_DAYS}d)",
        "Suggested restock value": "Restock Value (₹)",
    })

    st.dataframe(
        restock_table, use_container_width=True, hide_index=True,
        column_config={
            "Units/Day":          st.column_config.NumberColumn(format="%.2f"),
            "Days Left":          st.column_config.NumberColumn(format="%.0f"),
            f"Restock Qty ({RESTOCK_DAYS}d)": st.column_config.NumberColumn(format="%.0f"),
            "Restock Value (₹)":  st.column_config.NumberColumn(format="₹%.0f"),
        }
    )

    total_restock_value = inv["Suggested restock value"].sum()
    st.markdown(
        f"<div style='text-align:right;font-family:DM Mono,monospace;font-size:0.8rem;"
        f"color:#a78bfa;margin-top:0.5rem'>Estimated restock capital required: "
        f"<strong>₹{total_restock_value:,.0f}</strong></div>",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Capital locked by product ──────────────────────────────────────────────
    st.markdown("<div class='section-label'>Capital locked per product</div>", unsafe_allow_html=True)

    cap_sorted = inv.sort_values("Inventory value", ascending=False).head(20)

    fig2 = go.Figure(go.Bar(
        x=cap_sorted["Products"],
        y=cap_sorted["Inventory value"].clip(lower=0),
        marker_color="#6366f1",
        marker_line_width=0,
        customdata=cap_sorted[["Days of stock", "Batch_days"]].values,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "₹%{y:,.0f} locked<br>"
            "Days of stock: %{customdata[0]:.0f}<br>"
            "Batch age: %{customdata[1]:.0f} days<extra></extra>"
        ),
    ))
    fig2.update_layout(
        **PLOT_THEME, height=300, xaxis_tickangle=-35,
        yaxis_title="Inventory value (₹)"
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── Batch age tracker ─────────────────────────────────────────────────────
    st.markdown("<div class='section-label'>Batch age tracker</div>", unsafe_allow_html=True)
    st.caption("How long the current batch of each product has been sitting in stock.")

    if not batch.empty:
        batch_display = batch.sort_values("Inventory days", ascending=False)[[
            "Products", "Invoic no", "Date", "Discounted rate", "Inventory days"
        ]].rename(columns={
            "Invoic no": "Purchase Invoice",
            "Discounted rate": "Purchase Cost",
            "Inventory days": "Days in Stock",
        })

        def _age_color(d):
            if d > 90: 
                return "🔴"
            if d > 60: 
                return "🟡"
            return "🟢"

        batch_display["Flag"] = batch_display["Days in Stock"].apply(_age_color)

        st.dataframe(
            batch_display, use_container_width=True, hide_index=True,
            column_config={
                "Purchase Cost": st.column_config.NumberColumn(format="₹%.2f"),
                "Days in Stock": st.column_config.NumberColumn(format="%.0f"),
            }
        )
    else:
        st.info("No batch data available.")

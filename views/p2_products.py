"""pages/p2_products.py  –  Product Intelligence"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from formatters import format_indian_currency, format_indian_number, format_percentage

PLOT_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Sora, sans-serif", color="#c9c9d6"),
    xaxis=dict(gridcolor="#1e1e2e", linecolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    yaxis=dict(gridcolor="#1e1e2e", linecolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    margin=dict(l=10, r=10, t=40, b=10),
)


def render(sales, pricelist):
    st.markdown("""
    <div class='page-header'>
        <h1>Product Intelligence</h1>
        <span>Velocity · Margin · Mix</span>
    </div>
    """, unsafe_allow_html=True)

    if sales.empty:
        st.warning("No sales data available.")
        return

    date_range_days = max((sales["Date"].max() - sales["Date"].min()).days, 1)

    # ── Product-level aggregation ──────────────────────────────────────────────
    prod = (
        sales.groupby("Product")
        .agg(
            Units=("Nos", "sum"),
            Revenue=("Incl Gst", "sum"),
            Profit=("Profit", "sum"),
            Margin_pct=("Margin%", "mean"),
            Invoices=("Invoice no", "nunique"),
        )
        .reset_index()
    )
    prod["Avg daily units"] = (prod["Units"] / date_range_days).round(3)
    prod["Revenue share %"] = (prod["Revenue"] / prod["Revenue"].sum() * 100).round(1)

    # Merge weighted avg cost
    prod = prod.merge(
        pricelist.rename(columns={"Product": "Product", "Weighted avg price": "Avg cost"}),
        on="Product", how="left"
    )

    # ── Filters ────────────────────────────────────────────────────────────────
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        search = st.text_input("🔍 Filter products", placeholder="Type to search…")
    with col_f2:
        sort_by = st.selectbox("Sort by", ["Revenue", "Profit", "Units", "Margin_pct", "Avg daily units"])

    if search:
        prod = prod[prod["Product"].str.lower().str.contains(search.lower())]

    prod_sorted = prod.sort_values(sort_by, ascending=False)

    st.divider()

    # ── Quadrant chart ─────────────────────────────────────────────────────────
    st.markdown("<div class='section-label'>Product Quadrant — Velocity vs Margin</div>", unsafe_allow_html=True)

    med_vel = prod["Avg daily units"].median()
    med_mar = prod["Margin_pct"].median()

    def quadrant_label(row):
        fast = row["Avg daily units"] >= med_vel
        high = row["Margin_pct"] >= med_mar
        if fast and high: 
            return "⭐ Stars"
        if fast and not high: 
            return "🐄 Cash Cows"
        if not fast and high: 
            return "💎 Gems"
        return "💀 Dogs"

    prod["Quadrant"] = prod.apply(quadrant_label, axis=1)

    color_map = {
        "⭐ Stars": "#6366f1",
        "🐄 Cash Cows": "#fbbf24",
        "💎 Gems": "#4ade80",
        "💀 Dogs": "#f87171",
    }

    fig = go.Figure()
    for quad, grp in prod.groupby("Quadrant"):
        fig.add_trace(go.Scatter(
            x=grp["Avg daily units"],
            y=grp["Margin_pct"],
            mode="markers+text",
            name=quad,
            marker=dict(
                size=grp["Revenue"].clip(lower=0) ** 0.4,
                sizemin=8,
                color=color_map.get(quad, "#888"),
                line=dict(width=1, color="#000"),
            ),
            text=grp["Product"].str.split().str[:2].str.join(" "),
            textposition="top center",
            textfont=dict(size=9, color="#c9c9d6"),
            customdata=grp[["Product", "Revenue", "Units", "Margin_pct"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Revenue: ₹%{customdata[1]:,.0f}<br>"
                "Units: %{customdata[2]:.0f}<br>"
                "Margin: %{customdata[3]:.1f}%<extra></extra>"
            ),
        ))

    # Quadrant dividers
    fig.add_vline(x=med_vel, line_dash="dot", line_color="#2a2a40", line_width=1)
    fig.add_hline(y=med_mar, line_dash="dot", line_color="#2a2a40", line_width=1)

    # Quadrant labels
    x_max = prod["Avg daily units"].max() * 1.1
    y_max = prod["Margin_pct"].max() * 1.1
    for txt, x, y in [
        ("STARS ⭐", x_max * 0.85, y_max * 0.92),
        ("CASH COWS 🐄", x_max * 0.85, y_max * 0.08),
        ("GEMS 💎", x_max * 0.05, y_max * 0.92),
        ("DOGS 💀", x_max * 0.05, y_max * 0.08),
    ]:
        fig.add_annotation(
            x=x, y=y, text=txt, showarrow=False,
            font=dict(size=9, color="#3a3a50", family="DM Mono, monospace"),
        )

    fig.update_layout(
        **PLOT_THEME,
        height=440,
        xaxis_title="Avg units / day →  (velocity)",
        yaxis_title="Avg margin %  →  (profitability)",
        legend=dict(orientation="h", y=-0.12),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Revenue Pareto ─────────────────────────────────────────────────────────
    st.markdown("<div class='section-label'>Revenue contribution – Pareto</div>", unsafe_allow_html=True)

    pareto = prod_sorted[["Product", "Revenue", "Revenue share %"]].copy()
    pareto["Cumulative %"] = pareto["Revenue share %"].cumsum().round(1)

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=pareto["Product"], y=pareto["Revenue share %"],
        marker_color="#6366f1", marker_line_width=0, name="Share %",
        hovertemplate="<b>%{x}</b><br>%{y:.1f}%<extra></extra>",
    ))
    fig2.add_trace(go.Scatter(
        x=pareto["Product"], y=pareto["Cumulative %"],
        mode="lines+markers", line=dict(color="#fbbf24", width=2),
        name="Cumulative %", yaxis="y2",
        hovertemplate="%{y:.1f}% cumulative<extra></extra>",
    ))
    fig2.add_hline(y=80, line_dash="dot", line_color="#f87171",
                   line_width=1, yref="y2",
                   annotation_text="80%", annotation_font_color="#f87171",
                   annotation_position="right")
    fig2.update_layout(
        **PLOT_THEME, height=340,
        yaxis2=dict(overlaying="y", side="right", range=[0, 105],
                    gridcolor="#1e1e2e", tickformat=".0f%%"),
        legend=dict(orientation="h", y=1.1),
        xaxis_tickangle=-40,
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── Product table ──────────────────────────────────────────────────────────
    st.markdown("<div class='section-label'>Full product breakdown</div>", unsafe_allow_html=True)

    # Ensure Quadrant column exists (handle empty/filtered case)
    if "Quadrant" not in prod_sorted.columns:
        prod_sorted = prod_sorted.copy()
        prod_sorted["Quadrant"] = ""
    
    display_cols = [
        "Product", "Quadrant", "Units", "Avg daily units",
        "Revenue", "Profit", "Margin_pct", "Revenue share %",
    ]
    # Only select columns that exist
    display_cols = [c for c in display_cols if c in prod_sorted.columns]
    display = prod_sorted[display_cols].rename(columns={
        "Margin_pct": "Avg Margin %",
        "Avg daily units": "Units/Day",
    })

    # Format for Indian style
    display_formatted = display.copy()
    for col in ["Revenue", "Profit"]:
        if col in display_formatted.columns:
            display_formatted[col] = display_formatted[col].apply(lambda x: format_indian_currency(x))
    for col in ["Avg Margin %", "Revenue share %"]:
        if col in display_formatted.columns:
            display_formatted[col] = display_formatted[col].apply(lambda x: format_percentage(x))
    for col in ["Units", "Units/Day"]:
        if col in display_formatted.columns:
            display_formatted[col] = display_formatted[col].apply(lambda x: format_indian_number(x, 2 if 'Day' in col else 0))
    
    st.dataframe(
        display_formatted,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # ── Per-product weekly trend ───────────────────────────────────────────────
    st.markdown("<div class='section-label'>Weekly units trend by product</div>", unsafe_allow_html=True)

    top_products = prod_sorted["Product"].head(12).tolist()
    selected = st.multiselect(
        "Select products to compare",
        options=prod_sorted["Product"].tolist(),
        default=top_products[:5],
    )

    if selected:
        sales_sel = sales[sales["Product"].isin(selected)].copy()
        weekly = (
            sales_sel.set_index("Date")
            .groupby([pd.Grouper(freq="W-MON"), "Product"])["Nos"]
            .sum()
            .reset_index()
        )
        weekly.columns = ["Week", "Product", "Units"]

        fig3 = px.line(
            weekly, x="Week", y="Units", color="Product",
            markers=True,
            color_discrete_sequence=px.colors.qualitative.Bold,
        )
        fig3.update_layout(**PLOT_THEME, height=320,
                           legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # ── Margin variance per product ────────────────────────────────────────────
    st.markdown("<div class='section-label'>Margin range per product (min / avg / max across invoices)</div>", unsafe_allow_html=True)

    margin_range = (
        sales.groupby("Product")["Margin%"]
        .agg(Min="min", Avg="mean", Max="max")
        .reset_index()
        .sort_values("Avg", ascending=False)
    ).head(20)

    fig4 = go.Figure()
    for _, r in margin_range.iterrows():
        fig4.add_trace(go.Scatter(
            x=[r["Min"], r["Avg"], r["Max"]],
            y=[r["Product"]] * 3,
            mode="lines+markers",
            line=dict(color="#6366f1", width=2),
            marker=dict(size=[8, 12, 8], color=["#f87171", "#6366f1", "#4ade80"]),
            showlegend=False,
            hovertemplate=f"<b>{r['Product']}</b><br>Min: {r['Min']:.1f}%  Avg: {r['Avg']:.1f}%  Max: {r['Max']:.1f}%<extra></extra>",
        ))

    fig4.update_layout(
        **PLOT_THEME,
        height=max(300, len(margin_range) * 22),
        xaxis_title="Margin %",
        yaxis_autorange="reversed",
    )
    st.plotly_chart(fig4, use_container_width=True)

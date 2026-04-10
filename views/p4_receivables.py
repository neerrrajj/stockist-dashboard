"""pages/p4_receivables.py  –  Receivables & Cash Flow"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from formatters import format_indian_currency, format_indian_number, format_date_long

PLOT_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Sora, sans-serif", color="#c9c9d6"),
    xaxis=dict(gridcolor="#1e1e2e", linecolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    yaxis=dict(gridcolor="#1e1e2e", linecolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    margin=dict(l=10, r=10, t=40, b=10),
)


def _age_bucket(days):
    if days <= 0:
        return "Current"
    if days <= 15:
        return "0-15 days"
    if days <= 30:
        return "16-30 days"
    if days <= 60:
        return "31-60 days"
    return "60+ days"

BUCKET_ORDER  = ["Current", "0-15 days", "16-30 days", "31-60 days", "60+ days"]
BUCKET_COLORS = ["#4ade80", "#86efac", "#fbbf24", "#f97316", "#f87171"]


def render(sales, payments, outstanding):
    from data_loader import EXCLUDED_CUSTOMERS
    
    st.markdown("""
    """, unsafe_allow_html=True)

    # Include all rows with non-zero balance for totals (including excluded customers)
    unpaid_all = outstanding[outstanding["Sum of balance"].abs() > 0.01].copy()
    
    # Exclude certain customers from list view only
    if EXCLUDED_CUSTOMERS and not outstanding.empty:
        outstanding_display = outstanding[~outstanding["Cust"].str.lower().isin(
            [c.lower() for c in EXCLUDED_CUSTOMERS]
        )].copy()
    else:
        outstanding_display = outstanding.copy()
    unpaid_display = outstanding_display[outstanding_display["Sum of balance"].abs() > 0.01].copy()
    
    # Apply age bucket to display data
    unpaid_display["Age bucket"] = unpaid_display["Days outstanding"].apply(_age_bucket)
    unpaid_display["Age bucket"] = pd.Categorical(unpaid_display["Age bucket"], categories=BUCKET_ORDER, ordered=True)

    # ── Top KPIs ───────────────────────────────────────────────────────────────
    # Use unpaid_all for totals (includes excluded customers)
    unpaid_all["Age bucket"] = unpaid_all["Days outstanding"].apply(_age_bucket)
    total_out  = unpaid_all["Sum of balance"].sum()
    invoices_out = len(unpaid_all)
    oldest_days  = unpaid_all["Days outstanding"].max() if not unpaid_all.empty else 0
    risky = unpaid_all[unpaid_all["Days outstanding"] > 30]["Sum of balance"].sum()

    c1, c2, c3, c4 = st.columns(4)
    with c1: 
        st.metric("Total Outstanding", format_indian_currency(total_out))
    with c2: 
        st.metric("Unpaid Invoices", str(invoices_out))
    with c3: 
        st.metric("Oldest Invoice", f"{oldest_days:.0f} days")
    with c4: 
        st.metric("Risky (> 30d)", format_indian_currency(risky))

    st.divider()

    # ── Ageing waterfall / bucket chart ───────────────────────────────────────
    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("<div class='section-label'>Ageing bucket breakdown</div>", unsafe_allow_html=True)

        buckets = (
            unpaid_display.groupby("Age bucket", observed=True)["Sum of balance"]
            .sum()
            .reindex(BUCKET_ORDER)
            .fillna(0)
            .reset_index()
        )

        fig = go.Figure(go.Bar(
            x=buckets["Age bucket"],
            y=buckets["Sum of balance"],
            marker_color=BUCKET_COLORS,
            marker_line_width=0,
            hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>",
        ))
        fig.update_layout(**PLOT_THEME, height=280, yaxis_title="₹ outstanding")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("<div class='section-label'>By age bucket</div>", unsafe_allow_html=True)
        for i, row in buckets.iterrows():
            pct = row["Sum of balance"] / total_out * 100 if total_out > 0 else 0
            color = BUCKET_COLORS[i]
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;"
                f"border-left:3px solid {color};padding:6px 10px;"
                f"margin-bottom:6px;background:#0f0f14;border-radius:0 6px 6px 0'>"
                f"<span style='color:#c9c9d6;font-size:0.82rem'>{row['Age bucket']}</span>"
                f"<span style='color:{color};font-family:DM Mono,monospace;font-size:0.82rem'>"
                f"₹{row['Sum of balance']:,.0f} <span style='color:#6b6b80'>({pct:.0f}%)</span></span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Outstanding invoice table ──────────────────────────────────────────────
    st.markdown("<div class='section-label'>Outstanding invoice detail</div>", unsafe_allow_html=True)

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cust_filter = st.multiselect(
            "Filter by counter",
            options=sorted(unpaid_display["Cust"].unique()),
            default=[],
        )
    with col_f2:
        bucket_filter = st.multiselect(
            "Filter by age bucket",
            options=BUCKET_ORDER,
            default=[],
        )

    filtered = unpaid_display.copy()
    if cust_filter:
        filtered = filtered[filtered["Cust"].isin(cust_filter)]
    if bucket_filter:
        filtered = filtered[filtered["Age bucket"].isin(bucket_filter)]

    # Select columns (Inv date no longer available in new sheet format)
    display_cols = ["Cust", "Inv no", "Sum of Incl Gst",
                    "Sum of Payments", "Sum of balance", "Days outstanding", "Age bucket"]
    filtered_display = filtered[display_cols].sort_values("Days outstanding", ascending=False)

    # Keep numeric values for proper sorting, use column_config for formatting
    st.dataframe(
        filtered_display, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Sum of Incl Gst": st.column_config.NumberColumn(format="₹%.2f"),
            "Sum of Payments": st.column_config.NumberColumn(format="₹%.2f"),
            "Sum of balance": st.column_config.NumberColumn(format="₹%.2f"),
            "Days outstanding": st.column_config.NumberColumn(format="%.0f"),
        }
    )

    st.divider()

    # ── Payment inflow timeline ────────────────────────────────────────────────
    st.markdown("<div class='section-label'>Cash inflow — payments received over time</div>", unsafe_allow_html=True)

    pay_weekly = (
        payments.set_index("Date")["Credit"]
        .resample("W-MON")
        .sum()
        .reset_index()
    )

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=pay_weekly["Date"], y=pay_weekly["Credit"],
        marker_color="#4ade80", marker_line_width=0, name="Weekly collections",
        hovertemplate="<b>Week %{x|%d %b}</b><br>₹%{y:,.0f}<extra></extra>",
    ))
    fig2.add_trace(go.Scatter(
        x=pay_weekly["Date"],
        y=pay_weekly["Credit"].rolling(3, min_periods=1).mean(),
        mode="lines", line=dict(color="#a78bfa", width=2, dash="dot"),
        name="3-week avg",
    ))
    fig2.update_layout(**PLOT_THEME, height=260, legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── Collection efficiency ─────────────────────────────────────────────────
    st.markdown("<div class='section-label'>Collection efficiency by counter</div>", unsafe_allow_html=True)

    cust_eff = (
        unpaid_display.groupby("Cust")
        .agg(Billed=("Sum of Incl Gst", "sum"), Collected=("Sum of Payments", "sum"))
        .reset_index()
    )
    cust_eff["Collection %"] = (cust_eff["Collected"] / cust_eff["Billed"] * 100).clip(0, 100).round(1)
    cust_eff = cust_eff.sort_values("Collection %", ascending=True)

    fig3 = go.Figure(go.Bar(
        x=cust_eff["Collection %"],
        y=cust_eff["Cust"],
        orientation="h",
        marker_color=[
            "#4ade80" if v >= 90 else "#fbbf24" if v >= 60 else "#f87171"
            for v in cust_eff["Collection %"]
        ],
        marker_line_width=0,
        hovertemplate="<b>%{y}</b><br>%{x:.1f}% collected<extra></extra>",
    ))
    fig3.add_vline(x=90, line_dash="dot", line_color="#4ade80",
                   annotation_text="90%", annotation_font_color="#4ade80")
    fig3.update_layout(
        paper_bgcolor=PLOT_THEME["paper_bgcolor"],
        plot_bgcolor=PLOT_THEME["plot_bgcolor"],
        font=PLOT_THEME["font"],
        margin=PLOT_THEME["margin"],
        height=max(280, len(cust_eff) * 26),
        xaxis=dict(range=[0, 110], gridcolor="#1e1e2e", linecolor="#1e1e2e", zerolinecolor="#1e1e2e", ticksuffix="%"),
        yaxis=dict(gridcolor="#1e1e2e", linecolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    )
    st.plotly_chart(fig3, use_container_width=True)

    # Note: Payment status column removed from sheet
    # st.divider()
    # st.markdown("<div class='section-label'>Paid vs unpaid invoice ratio by month</div>", unsafe_allow_html=True)
    # ... chart code removed due to missing Payment status column

"""pages/p3_counters.py  –  Counter / Customer Intelligence"""

import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from formatters import format_indian_currency, format_percentage

PLOT_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Sora, sans-serif", color="#c9c9d6"),
    xaxis=dict(gridcolor="#1e1e2e", linecolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    yaxis=dict(gridcolor="#1e1e2e", linecolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    margin=dict(l=10, r=10, t=40, b=10),
)

SCORE_COLOR = {"🟢 Reliable": "#4ade80", "🟡 Slow": "#fbbf24", "🔴 Risky": "#f87171"}


def _payment_score(avg_days, pct_unpaid):
    """Simple rule-based reputation score."""
    if avg_days <= 3 and pct_unpaid < 0.1:
        return "🟢 Reliable"
    if avg_days <= 14 and pct_unpaid < 0.4:
        return "🟡 Slow"
    return "🔴 Risky"


def render(sales, payments, outstanding):
    from data_loader import EXCLUDED_CUSTOMERS
    
    st.markdown("""
    """, unsafe_allow_html=True)

    # Exclude certain customers from display lists (but keep in totals)
    if EXCLUDED_CUSTOMERS:
        if not outstanding.empty:
            outstanding = outstanding[~outstanding["Cust"].str.lower().isin(
                [c.lower() for c in EXCLUDED_CUSTOMERS]
            )].copy()
        if not sales.empty:
            sales = sales[~sales["Cust"].str.lower().isin(
                [c.lower() for c in EXCLUDED_CUSTOMERS]
            )].copy()

    # ── Build per-counter stats ────────────────────────────────────────────────
    # Revenue & profit from sales
    cust_sales = (
        sales.groupby("Customer name")
        .agg(
            Total_revenue=("Incl Gst", "sum"),
            Total_profit=("Profit", "sum"),
            Invoices=("Invoice no", "nunique"),
            Units=("Nos", "sum"),
        )
        .reset_index()
    )
    cust_sales["Avg margin %"] = (cust_sales["Total_profit"] / cust_sales["Total_revenue"] * 100).round(1)

    # Payment timing: join invoice date from sales + payment date from payments
    inv_dates = (
        sales.groupby("Invoice no")
        .agg(Inv_date=("Inv date", "first"), Customer=("Customer name", "first"))
        .reset_index()
    )
    pay_timing = payments.merge(inv_dates, left_on="Invoice no", right_on="Invoice no", how="inner")
    pay_timing["Days to pay"] = (pay_timing["Date"] - pay_timing["Inv_date"]).dt.days.clip(lower=0)

    cust_timing = (
        pay_timing.groupby("Customer")
        .agg(Avg_days_to_pay=("Days to pay", "mean"), Payments_received=("Credit", "sum"))
        .reset_index()
        .rename(columns={"Customer": "Customer name"})
    )

    # Outstanding balance per customer
    cust_bal = (
        outstanding[outstanding["Sum of balance"] > 0]
        .groupby("Cust")
        .agg(Outstanding=("Sum of balance", "sum"), Unpaid_invoices=("Inv no", "count"))
        .reset_index()
        .rename(columns={"Cust": "Customer name"})
    )

    # Merge all
    summary = (
        cust_sales
        .merge(cust_timing, on="Customer name", how="left")
        .merge(cust_bal, on="Customer name", how="left")
    )
    summary["Avg_days_to_pay"]  = summary["Avg_days_to_pay"].fillna(99)
    summary["Outstanding"]      = summary["Outstanding"].fillna(0)
    summary["Unpaid_invoices"]  = summary["Unpaid_invoices"].fillna(0).astype(int)
    summary["Pct_unpaid"] = (summary["Unpaid_invoices"] / summary["Invoices"].clip(lower=1)).round(2)
    summary["Score"] = summary.apply(
        lambda r: _payment_score(r["Avg_days_to_pay"], r["Pct_unpaid"]), axis=1
    )
    summary = summary.sort_values("Total_revenue", ascending=False)

    # ── Overview scoreboard ────────────────────────────────────────────────────
    st.markdown("<div class='section-label'>Counter scoreboard</div>", unsafe_allow_html=True)

    display = summary[[
        "Customer name", "Score", "Total_revenue", "Total_profit",
        "Avg margin %", "Invoices", "Avg_days_to_pay", "Outstanding",
    ]].rename(columns={
        "Total_revenue": "Revenue (₹)",
        "Total_profit": "Profit (₹)",
        "Avg_days_to_pay": "Avg days to pay",
    })

    # Format for Indian style
    # Keep numeric values for proper sorting
    st.dataframe(
        display, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Revenue (₹)": st.column_config.NumberColumn(format="₹%.0f"),
            "Profit (₹)": st.column_config.NumberColumn(format="₹%.0f"),
            "Avg margin %": st.column_config.NumberColumn(format="%.1f%%"),
            "Avg days to pay": st.column_config.NumberColumn(format="%.1f"),
            "Outstanding": st.column_config.NumberColumn(format="₹%.0f"),
        }
    )

    st.divider()

    # ── Revenue concentration ──────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<div class='section-label'>Revenue concentration</div>", unsafe_allow_html=True)
        top3_share = summary["Total_revenue"].head(3).sum() / summary["Total_revenue"].sum() * 100
        st.metric("Top 3 counters share", format_percentage(top3_share),
                  delta="Concentration risk" if top3_share > 60 else "Healthy spread",
                  delta_color="inverse" if top3_share > 60 else "normal")

        fig_pie = go.Figure(go.Pie(
            labels=summary["Customer name"],
            values=summary["Total_revenue"],
            hole=0.55,
            textinfo="label+percent",
            textfont=dict(size=10),
            marker=dict(colors=px.colors.qualitative.Bold),
            hovertemplate="<b>%{label}</b><br>₹%{customdata:,.0f}<br>%{percent}<extra></extra>",
        ))
        fig_pie.update_layout(**PLOT_THEME, height=320,
                              showlegend=False,
                              annotations=[dict(text="Revenue", x=0.5, y=0.5,
                                                font_size=11, showarrow=False,
                                                font_color="#6b6b80")])
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.markdown("<div class='section-label'>Payment speed by counter</div>", unsafe_allow_html=True)
        timing_plot = summary[summary["Avg_days_to_pay"] < 90].sort_values("Avg_days_to_pay")

        fig_bar = go.Figure(go.Bar(
            x=timing_plot["Customer name"],
            y=timing_plot["Avg_days_to_pay"],
            marker_color=[SCORE_COLOR.get(s, "#6b6b80") for s in timing_plot["Score"]],
            marker_line_width=0,
            hovertemplate="<b>%{x}</b><br>%{y:.1f} days avg<extra></extra>",
        ))
        fig_bar.add_hline(y=7, line_dash="dot", line_color="#fbbf24",
                          annotation_text="7d", annotation_font_color="#fbbf24")
        fig_bar.update_layout(
            **PLOT_THEME, height=320,
            xaxis_tickangle=-35,
            yaxis_title="Avg days to pay",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # ── Per-counter deep dive ──────────────────────────────────────────────────
    st.markdown("<div class='section-label'>Counter deep dive</div>", unsafe_allow_html=True)

    selected_cust = st.selectbox(
        "Select counter",
        options=summary["Customer name"].tolist(),
    )

    cust_data = sales[sales["Customer name"] == selected_cust].copy()
    cust_out  = outstanding[outstanding["Cust"] == selected_cust].copy()

    if cust_data.empty:
        st.info("No sales data for this counter.")
        return

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Revenue", f"₹{cust_data['Incl Gst'].sum():,.0f}")
    with c2:
        st.metric("Total Profit", f"₹{cust_data['Profit'].sum():,.0f}")
    with c3:
        st.metric("Avg Margin", f"{cust_data['Margin%'].mean():.1f}%")
    with c4:
        bal = cust_out["Sum of balance"].clip(lower=0).sum() if not cust_out.empty else 0
        st.metric("Outstanding", format_indian_currency(bal))

    col_l, col_r = st.columns(2)

    # Product mix for this counter
    with col_l:
        st.markdown("<div class='section-label'>Product mix</div>", unsafe_allow_html=True)
        mix = (
            cust_data.groupby("Product")["Incl Gst"]
            .sum()
            .reset_index()
            .sort_values("Incl Gst", ascending=False)
        )
        fig_mix = go.Figure(go.Bar(
            x=mix["Product"], y=mix["Incl Gst"],
            marker_color="#6366f1", marker_line_width=0,
            hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>",
        ))
        fig_mix.update_layout(**PLOT_THEME, height=280, xaxis_tickangle=-35)
        st.plotly_chart(fig_mix, use_container_width=True)

    # Monthly trend
    with col_r:
        st.markdown("<div class='section-label'>Monthly revenue trend</div>", unsafe_allow_html=True)
        monthly = (
            cust_data.groupby("Month")["Incl Gst"].sum().reset_index()
            .sort_values("Month")
        )
        fig_trend = go.Figure(go.Scatter(
            x=monthly["Month"], y=monthly["Incl Gst"],
            mode="lines+markers",
            line=dict(color="#a78bfa", width=2),
            marker=dict(size=8, color="#6366f1"),
            fill="tozeroy", fillcolor="rgba(99,102,241,0.08)",
            hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>",
        ))
        fig_trend.update_layout(**PLOT_THEME, height=280)
        st.plotly_chart(fig_trend, use_container_width=True)

    # Invoice-level detail for outstanding
    if not cust_out.empty:
        st.markdown("<div class='section-label'>Outstanding invoices</div>", unsafe_allow_html=True)
        # Select available columns (Inv date may not be present in new format)
        display_cols = ["Inv no", "Sum of Incl Gst", "Sum of Payments", "Sum of balance", "Days outstanding"]
        if "Inv date" in cust_out.columns:
            display_cols.insert(1, "Inv date")
        cust_out_display = cust_out[display_cols].copy()
        
        # Keep numeric values for proper sorting
        st.dataframe(
            cust_out_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Sum of Incl Gst": st.column_config.NumberColumn(format="₹%.2f"),
                "Sum of Payments": st.column_config.NumberColumn(format="₹%.2f"),
                "Sum of balance": st.column_config.NumberColumn(format="₹%.2f"),
                "Days outstanding": st.column_config.NumberColumn(format="%.0f"),
            }
        )

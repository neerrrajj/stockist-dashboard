"""pages/p1_home.py  –  Command Center"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from formatters import format_indian_currency, format_indian_number, format_percentage

PLOT_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Sora, sans-serif", color="#c9c9d6"),
    xaxis=dict(gridcolor="#1e1e2e", linecolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    yaxis=dict(gridcolor="#1e1e2e", linecolor="#1e1e2e", zerolinecolor="#1e1e2e"),
    margin=dict(l=10, r=10, t=30, b=10),
)


def render(sales, purchase, payments, outstanding, inventory, batch):
    st.markdown("""
    <div class='page-header'>
        <h1>Command Center</h1>
        <span>Business at a glance</span>
    </div>
    """, unsafe_allow_html=True)

    today = pd.Timestamp.today().normalize()
    
    # =========================================================================
    # CALCULATE ALL METRICS
    # =========================================================================
    
    # Basic totals
    total_revenue = sales["Incl Gst"].sum()
    total_profit = sales["Profit"].sum()
    avg_margin = sales["Margin%"].mean()
    
    # Realized vs Unrealized
    total_payments_received = payments["Credit"].sum() if not payments.empty else 0
    total_outstanding = outstanding["Sum of balance"].sum() if not outstanding.empty else 0
    
    # Realized = payments received (actual cash in hand)
    # For profit, we estimate based on payment proportion
    payment_ratio = total_payments_received / total_revenue if total_revenue > 0 else 0
    realized_revenue = total_payments_received
    realized_profit = total_profit * payment_ratio
    unrealized_revenue = total_outstanding
    unrealized_profit = total_profit - realized_profit
    
    # Collection metrics
    collection_rate = (total_payments_received / total_revenue * 100) if total_revenue > 0 else 0
    avg_days_to_collect = outstanding["Days outstanding"].mean() if not outstanding.empty else 0
    overdue_amount = outstanding[outstanding["Days outstanding"] > 30]["Sum of balance"].sum() if not outstanding.empty else 0
    
    # Inventory metrics
    total_inv_value = inventory["Inventory value"].sum() if not inventory.empty else 0
    total_units_sold = sales["Nos"].sum()
    unique_products_sold = sales["Product"].nunique()
    
    # Top performers
    top_product = sales.groupby("Product")["Incl Gst"].sum().idxmax() if not sales.empty else "N/A"
    top_product_revenue = sales.groupby("Product")["Incl Gst"].sum().max() if not sales.empty else 0
    top_counter = sales.groupby("Cust")["Incl Gst"].sum().idxmax() if not sales.empty else "N/A"
    top_counter_revenue = sales.groupby("Cust")["Incl Gst"].sum().max() if not sales.empty else 0
    
    # Monthly metrics
    this_month = today.to_period("M").strftime("%Y-%m")
    sales_m = sales[sales["Month"] == this_month]
    prev_month = (today - pd.DateOffset(months=1)).to_period("M").strftime("%Y-%m")
    sales_pm = sales[sales["Month"] == prev_month]
    
    rev_m = sales_m["Incl Gst"].sum()
    rev_pm = sales_pm["Incl Gst"].sum()
    prof_m = sales_m["Profit"].sum()
    prof_pm = sales_pm["Profit"].sum()
    
    # =========================================================================
    # SECTION 1: CORE BUSINESS METRICS (4 columns)
    # =========================================================================
    st.markdown("<div class='section-label'>Core Business Metrics</div>", unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Revenue", format_indian_currency(total_revenue))
    with c2:
        st.metric("Total Profit", format_indian_currency(total_profit))
    with c3:
        st.metric("Avg Margin", format_percentage(avg_margin))
    with c4:
        st.metric("Collection Rate", format_percentage(collection_rate))
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # =========================================================================
    # SECTION 2: REALIZED vs UNREALIZED (4 columns) - NO DELTA LABELS
    # =========================================================================
    st.markdown("<div class='section-label'>Realized vs Unrealized</div>", unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Realized Revenue", format_indian_currency(realized_revenue))
    with c2:
        st.metric("Realized Profit", format_indian_currency(realized_profit))
    with c3:
        st.metric("Unrealized Revenue", format_indian_currency(unrealized_revenue))
    with c4:
        st.metric("Unrealized Profit", format_indian_currency(unrealized_profit))
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # =========================================================================
    # SECTION 3: ADDITIONAL METRICS (4 columns in one row)
    # =========================================================================
    st.markdown("<div class='section-label'>Additional Metrics</div>", unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Overdue (>30d)", format_indian_currency(overdue_amount))
    with c2:
        st.metric("Inventory Value", format_indian_currency(total_inv_value))
    with c3:
        rev_delta = rev_m - rev_pm
        st.metric("This Month Revenue", format_indian_currency(rev_m), 
                  delta=f"{format_indian_currency(rev_delta)} vs last month")
    with c4:
        prof_delta = prof_m - prof_pm
        st.metric("This Month Profit", format_indian_currency(prof_m),
                  delta=f"{format_indian_currency(prof_delta)} vs last month")
    
    st.divider()

    # =========================================================================
    # CHARTS & ALERTS (Original content)
    # =========================================================================
    
    # ── Revenue by week ────────────────────────────────────────────────────────
    st.markdown("<div class='section-label'>Revenue trend – weekly</div>", unsafe_allow_html=True)

    weekly = (
        sales.set_index("Date")["Incl Gst"]
        .resample("W-MON")
        .sum()
        .reset_index()
    )
    weekly.columns = ["Week", "Revenue"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=weekly["Week"], y=weekly["Revenue"],
        marker_color="#6366f1",
        marker_line_width=0,
        hovertemplate="<b>Week %{x|%d %b}</b><br>₹%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=weekly["Week"], y=weekly["Revenue"].rolling(3, min_periods=1).mean(),
        mode="lines", line=dict(color="#a78bfa", width=2, dash="dot"),
        name="3-week avg", hovertemplate="₹%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**PLOT_THEME, height=260, showlegend=True,
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Alert cards ────────────────────────────────────────────────────────────
    st.markdown("<div class='section-label'>Active alerts</div>", unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns(3)

    # 1. Low stock (< 15 day supply)
    with col_a:
        st.markdown("**⚠️ Low Stock (< 15 days)**")
        if not sales.empty and not inventory.empty:
            date_range_days = max((sales["Date"].max() - sales["Date"].min()).days, 1)
            daily_sales = (
                sales.groupby("Product")["Nos"].sum() / date_range_days
            ).reset_index()
            daily_sales.columns = ["Products", "Avg daily units"]

            inv_merged = inventory.merge(daily_sales, on="Products", how="left")
            inv_merged["Days of stock"] = (
                inv_merged["Closing Stock"] / inv_merged["Avg daily units"].replace(0, pd.NA)
            ).round(1)
            low = inv_merged[
                inv_merged["Days of stock"].notna() & (inv_merged["Days of stock"] < 15)
            ][["Products", "Closing Stock", "Days of stock"]].sort_values("Days of stock")

            if low.empty:
                st.success("All products have > 15 days stock.")
            else:
                for _, r in low.iterrows():
                    st.markdown(
                        f"<span class='pill-red'>{r['Products']}</span>"
                        f" &nbsp; {format_indian_number(r['Closing Stock'])} units · {r['Days of stock']:.0f}d",
                        unsafe_allow_html=True,
                    )
                    st.markdown("")

    # 2. Overdue payments (> 30 days)
    with col_b:
        st.markdown("**🔴 Overdue > 30 days**")
        if not outstanding.empty:
            overdue = outstanding[
                outstanding["Sum of balance"] > 10
            ].copy()
            overdue = overdue[overdue["Days outstanding"] > 30].sort_values(
                "Days outstanding", ascending=False
            )
            if overdue.empty:
                st.success("No overdue invoices.")
            else:
                for _, r in overdue.head(6).iterrows():
                    st.markdown(
                        f"<span class='pill-red'>{r['Cust']}</span>"
                        f" &nbsp; {format_indian_currency(r['Sum of balance'])} · {r['Days outstanding']:.0f}d",
                        unsafe_allow_html=True,
                    )
                    st.markdown("")

    # 3. Slow-moving (> 60 days in inventory, still have stock)
    with col_c:
        st.markdown("**🐌 Slow-Moving Stock (> 60 days)**")
        if not batch.empty:
            slow = batch[
                (batch["Inventory days"] > 60) &
                inventory.set_index("Products").reindex(batch["Products"].values)["Closing Stock"].fillna(0).values > 0
            ][["Products", "Inventory days"]].sort_values("Inventory days", ascending=False)
        else:
            slow = pd.DataFrame()

        if slow.empty:
            st.success("No slow-moving products flagged.")
        else:
            for _, r in slow.head(6).iterrows():
                label = "pill-red" if r["Inventory days"] > 90 else "pill-amber"
                st.markdown(
                    f"<span class='{label}'>{r['Products']}</span>"
                    f" &nbsp; {r['Inventory days']:.0f} days sitting",
                    unsafe_allow_html=True,
                )
                st.markdown("")

    st.divider()

    # ── Revenue & Profit by month ──────────────────────────────────────────────
    st.markdown("<div class='section-label'>Monthly P&L summary</div>", unsafe_allow_html=True)

    monthly = (
        sales.groupby("Month")
        .agg(Revenue=("Incl Gst", "sum"), Profit=("Profit", "sum"), Invoices=("Invoice no", "nunique"))
        .reset_index()
        .sort_values("Month")
    )
    monthly["Margin%"] = (monthly["Profit"] / monthly["Revenue"] * 100).round(1)

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=monthly["Month"], y=monthly["Revenue"],
        name="Revenue", marker_color="#6366f1", marker_line_width=0,
        hovertemplate="%{x}<br>Revenue ₹%{y:,.0f}<extra></extra>",
    ))
    fig2.add_trace(go.Bar(
        x=monthly["Month"], y=monthly["Profit"],
        name="Profit", marker_color="#4ade80", marker_line_width=0,
        hovertemplate="%{x}<br>Profit ₹%{y:,.0f}<extra></extra>",
    ))
    fig2.update_layout(**PLOT_THEME, height=280, barmode="group",
                       legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig2, use_container_width=True)

    # Summary table
    monthly_display = monthly.rename(columns={"Revenue": "Revenue (₹)", "Profit": "Profit (₹)"}).copy()
    
    st.dataframe(
        monthly_display,
        use_container_width=True, hide_index=True,
        column_config={
            "Revenue (₹)": st.column_config.NumberColumn(format="₹%.0f"),
            "Profit (₹)": st.column_config.NumberColumn(format="₹%.0f"),
            "Margin%": st.column_config.NumberColumn(format="%.1f%%"),
        }
    )

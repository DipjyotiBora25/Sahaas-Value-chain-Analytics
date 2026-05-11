# -*- coding: utf-8 -*-
"""Interactive Sales Dashboard - Phase 1

Dashboard for analyzing sales data with role-based views.
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px

_CUSTOM_CSS = """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.4rem;
    }
    .subtitle {
        font-size: 1.1rem;
        color: #4c566a;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 0.25rem solid #1f77b4;
    }
    .role-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #ff7f0e;
        margin-top: 1rem;
    }
</style>
"""


def load_data(df=None):
    """Load and preprocess the sales data."""
    if df is not None and not df.empty:
        # Use provided data
        data_df = df.copy()
    else:
        try:
            # Use sample data for dashboard performance
            data_df = pd.read_csv('working_sales_req_column_sample.csv')
        except FileNotFoundError:
            st.error("Sample data file 'working_sales_req_column_sample.csv' not found. Please run create_dashboard_sample.py first.")
            return pd.DataFrame()

    # Ensure date columns are datetime
    date_cols = ['Invoice Date', 'Due Date', 'Last Payment Date']
    for col in date_cols:
        if col in data_df.columns:
            data_df[col] = pd.to_datetime(data_df[col], errors='coerce')

    # Add derived columns
    if 'Invoice Date' in data_df.columns:
        data_df['Year'] = data_df['Invoice Date'].dt.year
        data_df['Month'] = data_df['Invoice Date'].dt.month
        data_df['Quarter'] = data_df['Invoice Date'].dt.quarter
        data_df['YearMonth'] = data_df['Invoice Date'].dt.to_period('M').astype(str)

    return data_df


def get_logo_path():
    """Find a usable dashboard logo image path (resolved relative to this module)."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        'saahas_zero_waste_logo.png',
        'SZW_Logo.png',
        'szw_logo.png',
        'logo.png',
    ]
    for name in candidates:
        path = os.path.join(here, name)
        if os.path.exists(path):
            return path
    return None


def get_role_filters(role):
    """Get appropriate filters based on user role."""
    if role == "Leadership":
        return ['Year', 'Quarter', 'CF.Business Verticals', 'Division']
    elif role == "Country/Site Lead":
        return ['Year', 'Month', 'CF.Business Verticals', 'Division', 'Supplier City', 'Customer Name']
    elif role == "Team/Division Lead":
        return ['Year', 'Month', 'Quarter', 'CF.Business Verticals', 'Division', 'Supplier City', 'Customer Name', 'Sales person', 'Item Name']
    return []


def resolve_amount_column(df):
    """Return the revenue-amount column name regardless of exact label variant."""
    if 'Item Total' in df.columns:
        return 'Item Total'
    for c in df.columns:
        if 'total' in str(c).lower():
            return c
    return None


def calculate_metrics(df, role):
    """Calculate key metrics based on role."""
    metrics = {}

    amount_col = resolve_amount_column(df)
    if amount_col:
        metrics['Total Revenue'] = df[amount_col].sum()
        metrics['Average Order Value'] = df[amount_col].mean()
        metrics['Total Orders'] = len(df)

    if role in ["Country/Site Lead", "Team/Division Lead"]:
        if 'Customer Name' in df.columns:
            metrics['Unique Customers'] = df['Customer Name'].nunique()

    if role == "Team/Division Lead":
        if 'Sales person' in df.columns:
            metrics['Active Sales People'] = df['Sales person'].nunique()
        if 'Item Name' in df.columns:
            metrics['Unique Products'] = df['Item Name'].nunique()

    return metrics

def create_charts(df, role):
    """Create charts based on role."""
    charts = {}

    amount_col = resolve_amount_column(df)
    if amount_col is None:
        return charts

    # Revenue Trend
    if 'Invoice Date' in df.columns:
        if role == "Leadership":
            monthly_revenue = df.groupby('YearMonth')[amount_col].sum().reset_index()
            fig_trend = px.line(monthly_revenue, x='YearMonth', y=amount_col,
                              title='Monthly Revenue Trend', markers=True)
        else:
            daily_revenue = df.groupby('Invoice Date')[amount_col].sum().reset_index()
            fig_trend = px.line(daily_revenue, x='Invoice Date', y=amount_col,
                              title='Daily Revenue Trend', markers=True)
        charts['Revenue Trend'] = fig_trend

    # Business Vertical Distribution
    if 'CF.Business Verticals' in df.columns:
        bv_revenue = df.groupby('CF.Business Verticals')[amount_col].sum().reset_index()
        fig_bv = px.pie(bv_revenue, values=amount_col, names='CF.Business Verticals',
                       title='Revenue by Business Vertical')
        charts['Business Vertical Distribution'] = fig_bv

    # Top Customers (for Country/Site and Team leads)
    if role in ["Country/Site Lead", "Team/Division Lead"] and 'Customer Name' in df.columns:
        top_customers = df.groupby('Customer Name')[amount_col].sum().nlargest(10).reset_index()
        fig_customers = px.bar(top_customers, x='Customer Name', y=amount_col,
                              title='Top 10 Customers by Revenue')
        fig_customers.update_xaxes(tickangle=45)
        charts['Top Customers'] = fig_customers

    # Sales Person Performance (for Team leads)
    if role == "Team/Division Lead" and 'Sales person' in df.columns:
        sp_performance = df.groupby('Sales person')[amount_col].sum().reset_index()
        fig_sp = px.bar(sp_performance, x='Sales person', y=amount_col,
                       title='Sales Person Performance')
        fig_sp.update_xaxes(tickangle=45)
        charts['Sales Performance'] = fig_sp

    # Product Performance (for Team leads)
    if role == "Team/Division Lead" and 'Item Name' in df.columns:
        top_products = df.groupby('Item Name')[amount_col].sum().nlargest(10).reset_index()
        fig_products = px.bar(top_products, x='Item Name', y=amount_col,
                            title='Top 10 Products by Revenue')
        fig_products.update_xaxes(tickangle=45)
        charts['Top Products'] = fig_products

    return charts

def main(df=None):
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)
    # Load data
    data_df = load_data(df)
    if data_df.empty:
        st.warning("No sales data available. Please upload sales data in the main dashboard.")
        return

    # Header
    logo_path = get_logo_path()
    header_col1, header_col2 = st.columns([1, 5])
    with header_col1:
        if logo_path:
            st.image(logo_path, width=180)
        else:
            st.markdown('**Saahas Zero Waste**')
            st.warning("Logo image not found. Add 'saahas_zero_waste_logo.png' or 'SZW_Logo.png' to the app folder.")
    with header_col2:
        st.markdown('<div class="main-header">Saahas Zero Waste</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtitle">Interactive Sales Analytics Dashboard</div>', unsafe_allow_html=True)

    # Embedded Controls Section
    st.markdown("---")
    st.markdown("### 🎯 Revenue Insights Controls")

    # Role selection
    role = st.selectbox(
        "Select Your Role:",
        ["Leadership", "Country/Site Lead", "Team/Division Lead"],
        help="Different roles have access to different levels of detail",
        key="revenue_role_select"
    )

    st.markdown(f'<div class="role-header">👤 {role} View</div>', unsafe_allow_html=True)

    # Filters based on role
    available_filters = get_role_filters(role)

    # Create columns for filters
    filter_cols = st.columns(min(len(available_filters) + 1, 4))  # +1 for date range

    # Date range filter (available to all roles)
    with filter_cols[0]:
        if 'Invoice Date' in data_df.columns:
            min_date = data_df['Invoice Date'].min()
            max_date = data_df['Invoice Date'].max()

            date_range = st.date_input(
                "📅 Date Range:",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="revenue_date_range"
            )

            if len(date_range) == 2:
                start_date, end_date = date_range
                df_filtered = data_df[(data_df['Invoice Date'] >= pd.to_datetime(start_date)) &
                               (data_df['Invoice Date'] <= pd.to_datetime(end_date))]
            else:
                df_filtered = data_df
        else:
            df_filtered = data_df

    # Additional filters based on role
    for i, filter_col in enumerate(available_filters):
        with filter_cols[(i + 1) % len(filter_cols)]:
            if filter_col in df_filtered.columns:
                if filter_col in ['Year', 'Month', 'Quarter']:
                    # Numeric filters
                    unique_vals = sorted(df_filtered[filter_col].dropna().unique())
                    selected_vals = st.multiselect(
                        f"📊 {filter_col}:",
                        unique_vals,
                        default=unique_vals[:5] if len(unique_vals) > 5 else unique_vals,
                        key=f"revenue_{filter_col.lower()}_filter"
                    )
                    if selected_vals:
                        df_filtered = df_filtered[df_filtered[filter_col].isin(selected_vals)]
                else:
                    # Categorical filters
                    unique_vals = sorted(df_filtered[filter_col].dropna().unique())
                    selected_vals = st.multiselect(
                        f"📊 {filter_col}:",
                        unique_vals,
                        default=unique_vals[:3] if len(unique_vals) > 3 else unique_vals,
                        key=f"revenue_{filter_col.lower()}_filter"
                    )
                    if selected_vals:
                        df_filtered = df_filtered[df_filtered[filter_col].isin(selected_vals)]

    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    # Key Metrics
    metrics = calculate_metrics(df_filtered, role)

    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Total Revenue", f"₹{metrics.get('Total Revenue', 0):,.0f}")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Average Order Value", f"₹{metrics.get('Average Order Value', 0):,.0f}")
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Total Orders", metrics.get('Total Orders', 0))
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        if 'Unique Customers' in metrics:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Unique Customers", metrics.get('Unique Customers', 0))
            st.markdown('</div>', unsafe_allow_html=True)
        elif 'Active Sales People' in metrics:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Active Sales People", metrics.get('Active Sales People', 0))
            st.markdown('</div>', unsafe_allow_html=True)

    # Charts
    charts = create_charts(df_filtered, role)

    # Display charts in a grid
    chart_cols = st.columns(2)

    chart_idx = 0
    for chart_name, chart_fig in charts.items():
        with chart_cols[chart_idx % 2]:
            st.plotly_chart(chart_fig, use_container_width=True)
        chart_idx += 1

    # Data table for detailed view
    if role in ["Country/Site Lead", "Team/Division Lead"]:
        st.markdown("### 📋 Detailed Data View")
        st.dataframe(df_filtered.head(100), use_container_width=True)

        # Download button
        csv = df_filtered.to_csv(index=False)
        st.download_button(
            label="📥 Download Filtered Data as CSV",
            data=csv,
            file_name="filtered_sales_data.csv",
            mime="text/csv"
        )

    # Footer
    st.markdown("---")
    st.markdown("*Saahas Zero Waste Dashboard - Phase 1*")

def render_revenue_insights(df=None):
    """Render the revenue insights dashboard - for embedding in main app."""
    main(df)

if __name__ == "__main__":
    main()
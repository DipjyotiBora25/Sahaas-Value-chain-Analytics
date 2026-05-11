# -*- coding: utf-8 -*-
"""Interactive Purchase Dashboard - Phase 1

Dashboard for analyzing purchase data with role-based views.
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
    """Load and preprocess the purchase data."""
    if df is not None and not df.empty:
        # Use provided data
        data_df = df.copy()
    else:
        try:
            # Use sample data for dashboard performance
            data_df = pd.read_csv('purchase_data_sample.csv')
        except FileNotFoundError:
            st.error("Sample data file 'purchase_data_sample.csv' not found. Please run create_purchase_dashboard_sample.py first.")
            return pd.DataFrame()

    # Ensure date columns are datetime
    date_cols = ['Invoice Date', 'Submission Date']
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
        return ['Year', 'Quarter', 'Business Vertical', 'Division']
    elif role == "Country/Site Lead":
        return ['Year', 'Month', 'Business Vertical', 'Division', 'City', 'Vendor Name']
    elif role == "Team/Division Lead":
        return ['Year', 'Month', 'Quarter', 'Business Vertical', 'Division', 'City', 'Vendor Name', 'Category', 'Item Name']
    return []


def resolve_amount_column(df):
    """Return the spend-amount column name regardless of exact label variant."""
    for candidate in ['Total Amount', 'Sum of Total Amount', 'Sum of Total Amount ']:
        if candidate in df.columns:
            return candidate
    return None


def calculate_metrics(df, role):
    """Calculate key metrics based on role."""
    metrics = {}

    amount_col = resolve_amount_column(df)
    if amount_col:
        metrics['Total Purchase Spend'] = df[amount_col].sum()
        metrics['Average Order Value'] = df[amount_col].mean()
        metrics['Total Transactions'] = len(df)

    if role in ["Country/Site Lead", "Team/Division Lead"]:
        if 'Vendor Name' in df.columns:
            metrics['Unique Vendors'] = df['Vendor Name'].nunique()

    if role == "Team/Division Lead":
        if 'Category' in df.columns:
            metrics['Product Categories'] = df['Category'].nunique()
        if 'Item Name' in df.columns:
            metrics['Unique Items'] = df['Item Name'].nunique()

    return metrics

def create_charts(df, role):
    """Create charts based on role."""
    charts = {}

    amount_col = resolve_amount_column(df)
    if amount_col is None:
        return charts

    # Purchase Trend
    if 'Invoice Date' in df.columns:
        if role == "Leadership":
            monthly_spend = df.groupby('YearMonth')[amount_col].sum().reset_index()
            fig_trend = px.line(monthly_spend, x='YearMonth', y=amount_col,
                              title='Monthly Purchase Spend Trend', markers=True)
        else:
            daily_spend = df.groupby('Invoice Date')[amount_col].sum().reset_index()
            fig_trend = px.line(daily_spend, x='Invoice Date', y=amount_col,
                              title='Daily Purchase Spend Trend', markers=True)
        charts['Purchase Trend'] = fig_trend

    # Business Vertical Distribution
    if 'Business Vertical' in df.columns:
        bv_spend = df.groupby('Business Vertical')[amount_col].sum().reset_index()
        fig_bv = px.pie(bv_spend, values=amount_col, names='Business Vertical',
                       title='Spend by Business Vertical')
        charts['Business Vertical Distribution'] = fig_bv

    # Top Vendors (for Country/Site and Team leads)
    if role in ["Country/Site Lead", "Team/Division Lead"] and 'Vendor Name' in df.columns:
        top_vendors = df.groupby('Vendor Name')[amount_col].sum().nlargest(10).reset_index()
        fig_vendors = px.bar(top_vendors, x='Vendor Name', y=amount_col,
                            title='Top 10 Vendors by Spend')
        fig_vendors.update_xaxes(tickangle=45)
        charts['Top Vendors'] = fig_vendors

    # Invoice Status Distribution (for Team leads)
    if role == "Team/Division Lead" and 'Invoice Status' in df.columns:
        status_dist = df.groupby('Invoice Status')[amount_col].sum().reset_index()
        fig_status = px.bar(status_dist, x='Invoice Status', y=amount_col,
                           title='Spend by Invoice Status')
        fig_status.update_xaxes(tickangle=45)
        charts['Invoice Status'] = fig_status

    # Category Performance (for Team leads)
    if role == "Team/Division Lead" and 'Category' in df.columns:
        top_categories = df.groupby('Category')[amount_col].sum().nlargest(10).reset_index()
        fig_categories = px.bar(top_categories, x='Category', y=amount_col,
                              title='Top 10 Categories by Spend')
        fig_categories.update_xaxes(tickangle=45)
        charts['Top Categories'] = fig_categories

    return charts

def main(df=None):
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)
    # Load data
    data_df = load_data(df)
    if data_df.empty:
        st.warning("No purchase data available. Please upload purchase data in the main dashboard.")
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
        st.markdown('<div class="subtitle">Interactive Purchase Analytics Dashboard</div>', unsafe_allow_html=True)

    # Embedded Controls Section
    st.markdown("---")
    st.markdown("### 🎯 Spend Analysis Controls")

    # Role selection
    role = st.selectbox(
        "Select Your Role:",
        ["Leadership", "Country/Site Lead", "Team/Division Lead"],
        help="Different roles have access to different levels of detail",
        key="spend_role_select"
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
                key="spend_date_range"
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
                        key=f"spend_{filter_col.lower()}_filter"
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
                        key=f"spend_{filter_col.lower()}_filter"
                    )
                    if selected_vals:
                        df_filtered = df_filtered[df_filtered[filter_col].isin(selected_vals)]

    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    # Key Metrics
    metrics = calculate_metrics(df_filtered, role)

    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Total Purchase Spend", f"₹{metrics.get('Total Purchase Spend', 0):,.0f}")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Average Order Value", f"₹{metrics.get('Average Order Value', 0):,.0f}")
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Total Transactions", metrics.get('Total Transactions', 0))
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        if 'Unique Vendors' in metrics:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Unique Vendors", metrics.get('Unique Vendors', 0))
            st.markdown('</div>', unsafe_allow_html=True)
        elif 'Product Categories' in metrics:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Product Categories", metrics.get('Product Categories', 0))
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
            file_name="filtered_purchase_data.csv",
            mime="text/csv"
        )

    # Footer
    st.markdown("---")
    st.markdown("*Saahas Zero Waste Purchase Dashboard - Phase 1*")

def render_spend_analysis(df=None):
    """Render the spend analysis dashboard - for embedding in main app."""
    main(df)

if __name__ == "__main__":
    main()

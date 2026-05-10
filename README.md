# Waste Management Analytics Dashboard

This Streamlit app provides a four-tab dashboard for sales, purchase, data editing, and combined analytics.

## Files
- `app.py`: main Streamlit dashboard
- `requirements.txt`: Python dependencies
- `Purchase/Item_Cat_Update .csv`: legacy purchase lookup data

## Data sources
- Sales data is loaded from Desktop `Working_sales Sahaas`:

- Purchase data is loaded from Desktop `Working_Purchase Sahaas`:
  

## Run the app

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start Streamlit:

```bash
streamlit run app.py
```

## Notes
- Sales data is loaded automatically from the desktop folder `Working_sales Sahaas` when available.
- Purchase data is loaded automatically from the desktop folder `Working_Purchase Sahaas` when available.
- The Update Data tab allows editing and downloading updated datasets from the current session.
- The Combined Analytics tab links sales and purchase data using item matching and waste-management business insights.

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

## Performance tuning (local Ollama)

For low-latency chatbot responses when using a local Ollama server, use the included startup script to tune VRAM and caching before running the app:

```bash
./start_ollama.sh   # macOS / zsh
# or on Windows PowerShell: start_ollama.ps1
```

Environment toggles (optional):
- `OLLAMA_KV_CACHE_TYPE=q8_0` — quantized KV cache to reduce VRAM use
- `OLLAMA_NUM_PARALLEL=1` — dedicate parallelism to single requests
- `OLLAMA_PRELOAD_MODEL=1` — warm model on client init
- `OLLAMA_RESPONSE_CACHE=1` — enable local disk response cache (default)
- `OLLAMA_RESPONSE_CACHE_TTL` — cache TTL in seconds (default `3600`)

These optimizations reduce cold-start latency and repeated identical prompt overhead.

## Notes
- Sales data is loaded automatically from the desktop folder `Working_sales Sahaas` when available.
- Purchase data is loaded automatically from the desktop folder `Working_Purchase Sahaas` when available.
- The Update Data tab allows editing and downloading updated datasets from the current session.
- The Combined Analytics tab links sales and purchase data using item matching and waste-management business insights.

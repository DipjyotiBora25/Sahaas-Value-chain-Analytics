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

## Cloud deployment with an external Ollama server

If you host this app on Streamlit Cloud or another web host, the app cannot use a local Ollama server. Instead:

1. Deploy an external Ollama server on RunPod, Lambda Labs, or your own GPU host.
2. Pull the model weights on that external host, e.g. `ollama pull llama3.2`.
3. Set `OLLAMA_API_URL` as a Streamlit secret or environment variable for the app.

Example Streamlit secret:

```toml
OLLAMA_API_URL = "https://your-remote-ollama-server.example"
```

The app now reads `OLLAMA_API_URL` from Streamlit secrets, so it will use the remote Ollama host instead of local `http://localhost:11434`.


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

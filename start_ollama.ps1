# Optimized Ollama launcher for single-user data-assistant workloads.
# Run this BEFORE launching the Streamlit app, in its own PowerShell window.
# Close the window to stop Ollama.

Write-Host ""
Write-Host "Starting Ollama with optimized settings" -ForegroundColor Cyan
Write-Host "----------------------------------------" -ForegroundColor Cyan

# Stop any Ollama already running so the new env vars actually take effect.
$existing = Get-Process ollama -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Stopping existing ollama process(es)..." -ForegroundColor Yellow
    $existing | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# -- Speed tuning ----------------------------------------------------------
# Single-user setup: drop parallel slots to 1 so each request gets the full
# KV-cache budget (default is 4, which fragments VRAM and shrinks usable ctx).
$env:OLLAMA_NUM_PARALLEL = "1"
Write-Host "  OLLAMA_NUM_PARALLEL     = 1       [OK]" -ForegroundColor Green

# Flash attention: ~20% faster prompt eval on supported GPUs (CUDA / Metal).
# Harmless if unsupported -- Ollama falls back automatically.
$env:OLLAMA_FLASH_ATTENTION = "1"
Write-Host "  OLLAMA_FLASH_ATTENTION  = 1       [OK]" -ForegroundColor Green

# Quantized KV cache: halves VRAM cost of the context window, freeing headroom
# to keep more layers on GPU. Requires flash-attn (above).
$env:OLLAMA_KV_CACHE_TYPE = "q8_0"
Write-Host "  OLLAMA_KV_CACHE_TYPE    = q8_0    [OK]" -ForegroundColor Green

# Hold one model resident for 30 minutes after last use -- eliminates the
# cold-load lag (5-30s) on the next request.
$env:OLLAMA_KEEP_ALIVE = "30m"
Write-Host "  OLLAMA_KEEP_ALIVE       = 30m     [OK]" -ForegroundColor Green

# Cap models loaded simultaneously to 1: avoids VRAM thrash when switching.
$env:OLLAMA_MAX_LOADED_MODELS = "1"
Write-Host "  OLLAMA_MAX_LOADED_MODELS= 1       [OK]" -ForegroundColor Green

Write-Host ""
Write-Host "Launching 'ollama serve' (leave this window open)..." -ForegroundColor Cyan
Write-Host ""

ollama serve

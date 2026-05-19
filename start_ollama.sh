#!/usr/bin/env bash
# Optimized Ollama launcher for single-user data-assistant workloads (macOS / zsh)
# Run this BEFORE launching the Streamlit app, in its own terminal.

set -euo pipefail

echo "Starting Ollama with optimized environment"
export OLLAMA_NUM_PARALLEL="1"
export OLLAMA_FLASH_ATTENTION="1"
export OLLAMA_KV_CACHE_TYPE="q8_0"
export OLLAMA_KEEP_ALIVE="30m"
export OLLAMA_MAX_LOADED_MODELS="1"

echo "  OLLAMA_NUM_PARALLEL     = ${OLLAMA_NUM_PARALLEL}"
echo "  OLLAMA_FLASH_ATTENTION  = ${OLLAMA_FLASH_ATTENTION}"
echo "  OLLAMA_KV_CACHE_TYPE    = ${OLLAMA_KV_CACHE_TYPE}"
echo "  OLLAMA_KEEP_ALIVE       = ${OLLAMA_KEEP_ALIVE}"
echo "  OLLAMA_MAX_LOADED_MODELS= ${OLLAMA_MAX_LOADED_MODELS}"

echo
echo "Launching 'ollama serve' (leave this window open)..."
echo
ollama serve

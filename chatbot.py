"""Floating Ollama-powered chatbot for interpreting uploaded sales & purchase data.

Renders a circular robot button fixed to the bottom-right corner. The button
pulses and shows a "Need help?" nudge after the user has been idle for 60s.
Clicking opens a popover with a chat interface that streams responses from a
local Ollama server (default http://localhost:11434).

Setup:
    Install Ollama (https://ollama.com), then in a terminal:
        ollama pull llama3.2:3b     # or qwen2.5:3b for a lighter model
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

MODELFILE_PATH = Path(__file__).resolve().parent / "Modelfile.saahas-analyst"
CUSTOM_MODEL_NAME = "saahas-analyst"

DEFAULT_HOST = "http://localhost:11434"
FALLBACK_MODELS = ["llama3.2", "qwen2.5:3b", "phi3", "mistral", "gemma2:2b"]
IDLE_MS = 60_000

# ── Performance tuning sent with every chat request ───────────────────────
# keep_alive holds the model resident on GPU between turns, killing the
# 5-30s cold-load lag. Matches the OLLAMA_KEEP_ALIVE=30m server setting.
KEEP_ALIVE = "30m"
# Generation options: low temperature for factual data analysis, capped
# response length, larger context for full data summary + chat history.
GEN_OPTIONS = {
    "temperature": 0.2,
    "top_p": 0.9,
    "top_k": 40,
    "num_predict": 512,
    "num_ctx": 8192,
}
# History compaction: keep the last N user/assistant turns to avoid
# re-evaluating the entire transcript every request.
MAX_HISTORY_TURNS = 8

# Reasoning models burn 1–5k tokens on internal <think>...</think> before
# answering. Default generation budget would truncate them mid-thought, so
# we widen num_predict and num_ctx whenever the model name matches.
REASONING_HINTS = ("deepseek-r1", "r1-distill", "qwq", "reasoning", "o1-", "marco-o1")
REASONING_OPTIONS = {
    "temperature": 0.3,
    "top_p": 0.95,
    "top_k": 40,
    "num_predict": 4096,
    "num_ctx": 16384,
}


def _is_reasoning_model(name: str) -> bool:
    nl = (name or "").lower()
    return any(h in nl for h in REASONING_HINTS)


def _options_for(model: str) -> dict:
    return REASONING_OPTIONS if _is_reasoning_model(model) else GEN_OPTIONS


_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)


def _format_reasoning(text: str) -> str:
    """Collapse <think>…</think> blocks into expandable HTML <details> so the
    final answer is visible up front but the reasoning trail is still
    inspectable. Trailing unterminated <think> tags (mid-stream) become an
    open 'thinking…' marker."""
    def repl(m: re.Match) -> str:
        body = m.group(1).strip()
        return (
            "<details style='margin:0.25rem 0;color:#64748b;'>"
            "<summary style='cursor:pointer;'>💭 Reasoning</summary>\n\n"
            f"{body}\n\n</details>\n\n"
        )

    out = _THINK_RE.sub(repl, text)
    if "<think>" in out and "</think>" not in out:
        out = out.replace("<think>", "_💭 thinking…_\n\n", 1)
    return out


# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------

def list_ollama_models(host: str) -> list[str]:
    try:
        r = requests.get(f"{host.rstrip('/')}/api/tags", timeout=3)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", []) if "name" in m]
    except Exception:
        return []


def _stream_chat(host: str, model: str, messages: list[dict]) -> Iterable[str]:
    url = f"{host.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "keep_alive": KEEP_ALIVE,
        "options": _options_for(model),
    }
    with requests.post(url, json=payload, stream=True, timeout=300) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "error" in obj:
                raise RuntimeError(obj["error"])
            chunk = obj.get("message", {}).get("content", "")
            if chunk:
                yield chunk
            if obj.get("done"):
                break


def build_saahas_analyst_model() -> tuple[bool, str]:
    """Run `ollama create saahas-analyst -f Modelfile.saahas-analyst`.
    Requires the base model in the Modelfile's FROM line to already be pulled."""
    if not MODELFILE_PATH.exists():
        return False, f"Modelfile not found at {MODELFILE_PATH}"
    try:
        proc = subprocess.run(
            ["ollama", "create", CUSTOM_MODEL_NAME, "-f", str(MODELFILE_PATH)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode == 0:
            return True, (
                f"✅ Built `{CUSTOM_MODEL_NAME}`. Select it from the model dropdown."
            )
        err = (proc.stderr or proc.stdout or "").strip()
        if "not found" in err.lower() or "pull" in err.lower():
            return False, (
                f"Base model in Modelfile is not pulled yet. Open it and check the "
                f"`FROM` line, then run `ollama pull <that model>` first.\n\n```\n{err}\n```"
            )
        return False, f"`ollama create` failed:\n\n```\n{err}\n```"
    except FileNotFoundError:
        return False, "`ollama` command not found on PATH. Install Ollama and restart the app."
    except subprocess.TimeoutExpired:
        return False, "`ollama create` timed out after 5 minutes."


def warm_up_model(host: str, model: str) -> tuple[bool, str]:
    """Preload the model into memory so the first real query is fast.
    Sends an empty prompt with keep_alive — Ollama loads the model without
    generating anything."""
    try:
        r = requests.post(
            f"{host.rstrip('/')}/api/generate",
            json={"model": model, "prompt": "", "keep_alive": KEEP_ALIVE},
            timeout=120,
        )
        r.raise_for_status()
        return True, f"Model `{model}` is loaded and will stay warm for {KEEP_ALIVE}."
    except requests.exceptions.ConnectionError:
        return False, f"Could not reach Ollama at {host}."
    except Exception as e:
        return False, f"Warm-up failed: {e}"


# ---------------------------------------------------------------------------
# Data context — turns the uploaded dataframes into a compact text summary
# ---------------------------------------------------------------------------

def _amount_col(df: pd.DataFrame, prefer: list[str]) -> str | None:
    for c in prefer:
        if c in df.columns:
            return c
    for c in df.columns:
        cl = c.lower()
        if "total" in cl or "amount" in cl:
            return c
    return None


def _top_summary(df: pd.DataFrame, group_col: str, value_col: str, n: int = 5) -> str:
    if group_col not in df.columns or value_col not in df.columns:
        return ""
    agg = (
        df.groupby(group_col, dropna=False)[value_col]
        .sum()
        .sort_values(ascending=False)
        .head(n)
    )
    if agg.empty:
        return ""
    return "; ".join(f"{idx}: ₹{val:,.0f}" for idx, val in agg.items())


def build_data_context(sales_df: pd.DataFrame, purchase_df: pd.DataFrame) -> str:
    parts: list[str] = []

    if sales_df is None or sales_df.empty:
        parts.append("SALES DATA: none uploaded.")
    else:
        sa = _amount_col(sales_df, ["Item Total"])
        rows = len(sales_df)
        total_rev = float(pd.to_numeric(sales_df[sa], errors="coerce").sum()) if sa else 0.0
        cust_n = sales_df["Customer Name"].nunique() if "Customer Name" in sales_df.columns else 0
        inv_n = sales_df["Invoice Number"].nunique() if "Invoice Number" in sales_df.columns else rows
        date_range = ""
        if "Invoice Date" in sales_df.columns:
            d = pd.to_datetime(sales_df["Invoice Date"], errors="coerce").dropna()
            if not d.empty:
                date_range = f" Date range: {d.min().date()} to {d.max().date()}."
        parts.append(
            f"SALES DATA: {rows:,} rows, {inv_n:,} invoices, {cust_n:,} unique customers. "
            f"Total revenue: ₹{total_rev:,.0f}.{date_range}"
        )
        parts.append(f"Sales columns: {', '.join(map(str, sales_df.columns))}")
        if sa:
            top_cust = _top_summary(sales_df, "Customer Name", sa, 5)
            if top_cust:
                parts.append(f"Top 5 customers by revenue: {top_cust}")
            top_item = _top_summary(sales_df, "Item Name", sa, 5)
            if top_item:
                parts.append(f"Top 5 selling items: {top_item}")
            top_vert = _top_summary(sales_df, "CF.Business Verticals", sa, 5)
            if top_vert:
                parts.append(f"Revenue by business vertical: {top_vert}")
            if "YearMonth" in sales_df.columns:
                monthly = _top_summary(sales_df, "YearMonth", sa, 12)
                if monthly:
                    parts.append(f"Monthly revenue: {monthly}")

    if purchase_df is None or purchase_df.empty:
        parts.append("PURCHASE DATA: none uploaded.")
    else:
        pa = _amount_col(purchase_df, ["Sum of Total Amount", "Total Amount"])
        rows = len(purchase_df)
        total_sp = float(pd.to_numeric(purchase_df[pa], errors="coerce").sum()) if pa else 0.0
        ven_n = purchase_df["Vendor Name"].nunique() if "Vendor Name" in purchase_df.columns else 0
        inv_n = purchase_df["Invoice #"].nunique() if "Invoice #" in purchase_df.columns else rows
        date_range = ""
        if "Invoice Date" in purchase_df.columns:
            d = pd.to_datetime(purchase_df["Invoice Date"], errors="coerce").dropna()
            if not d.empty:
                date_range = f" Date range: {d.min().date()} to {d.max().date()}."
        parts.append(
            f"PURCHASE DATA: {rows:,} rows, {inv_n:,} invoices, {ven_n:,} unique vendors. "
            f"Total spend: ₹{total_sp:,.0f}.{date_range}"
        )
        parts.append(f"Purchase columns: {', '.join(map(str, purchase_df.columns))}")
        if pa:
            top_ven = _top_summary(purchase_df, "Vendor Name", pa, 5)
            if top_ven:
                parts.append(f"Top 5 vendors by spend: {top_ven}")
            top_cat = _top_summary(purchase_df, "Category", pa, 5)
            if top_cat:
                parts.append(f"Top categories by spend: {top_cat}")
            top_vert = _top_summary(purchase_df, "Business Vertical", pa, 5)
            if top_vert:
                parts.append(f"Spend by business vertical: {top_vert}")
            if "YearMonth" in purchase_df.columns:
                monthly = _top_summary(purchase_df, "YearMonth", pa, 12)
                if monthly:
                    parts.append(f"Monthly spend: {monthly}")

    if (sales_df is not None and not sales_df.empty) and (
        purchase_df is not None and not purchase_df.empty
    ):
        sa = _amount_col(sales_df, ["Item Total"])
        pa = _amount_col(purchase_df, ["Sum of Total Amount", "Total Amount"])
        if sa and pa:
            rev = float(pd.to_numeric(sales_df[sa], errors="coerce").sum())
            spd = float(pd.to_numeric(purchase_df[pa], errors="coerce").sum())
            profit = rev - spd
            margin = (profit / rev * 100) if rev else 0
            parts.append(
                f"COMBINED: gross profit ₹{profit:,.0f} ({margin:.1f}% margin on revenue)."
            )

    return "\n".join(parts)


def _df_fingerprint(df: pd.DataFrame | None) -> tuple | None:
    """Cheap signature: shape + columns + a sample row. Used to detect when
    the data context needs to be rebuilt — otherwise we keep the identical
    system prompt across turns so Ollama can reuse its prefix KV cache."""
    if df is None or df.empty:
        return None
    try:
        sample = tuple(df.iloc[0].astype(str).tolist())
    except Exception:
        sample = ()
    return (df.shape, tuple(map(str, df.columns)), sample)


def get_data_context_cached(sales_df: pd.DataFrame, purchase_df: pd.DataFrame) -> str:
    fp = (_df_fingerprint(sales_df), _df_fingerprint(purchase_df))
    if st.session_state.get("_ctx_fp") == fp and "_ctx" in st.session_state:
        return st.session_state["_ctx"]
    ctx = build_data_context(sales_df, purchase_df)
    st.session_state["_ctx_fp"] = fp
    st.session_state["_ctx"] = ctx
    return ctx


# ---------------------------------------------------------------------------
# Floating UI: CSS to pin the popover bottom-right + JS to detect idle
# ---------------------------------------------------------------------------

_FLOATING_CSS = """
<style>
    /* Pin the LAST popover on the page (our robot) to the bottom-right corner */
    div[data-testid="stPopover"]:last-of-type {
        position: fixed !important;
        bottom: calc(24px + 1cm);
        right: 24px;
        z-index: 9999;
        width: auto !important;
    }
    /* Style the trigger button as a floating circular paperclip (Clippy vibe) */
    div[data-testid="stPopover"]:last-of-type > div > button {
        width: 120px !important;
        height: 120px !important;
        border-radius: 50% !important;
        background: linear-gradient(135deg, #fde68a 0%, #f59e0b 60%, #d97706 100%) !important;
        color: #1e293b !important;
        font-size: 64px !important;
        line-height: 1 !important;
        border: 4px solid #ffffff !important;
        box-shadow: 0 18px 42px rgba(217,119,6,0.55) !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: transform 0.2s ease;
    }
    div[data-testid="stPopover"]:last-of-type > div > button:hover {
        transform: scale(1.08) rotate(-6deg);
    }
    /* Idle: pulse the button and show a speech-bubble nudge */
    body.szw-idle div[data-testid="stPopover"]:last-of-type > div > button {
        animation: szw-pulse 1.8s ease-in-out infinite;
    }
    body.szw-idle div[data-testid="stPopover"]:last-of-type::before {
        content: "Need help with your data?";
        position: absolute;
        bottom: 132px;
        right: 0;
        background: #ffffff;
        padding: 10px 16px;
        border-radius: 14px;
        box-shadow: 0 6px 18px rgba(15,23,42,0.18);
        font-size: 13px;
        font-weight: 600;
        color: #0f172a;
        white-space: nowrap;
        animation: szw-float 2.4s ease-in-out infinite;
    }
    body.szw-idle div[data-testid="stPopover"]:last-of-type::after {
        content: "";
        position: absolute;
        bottom: 122px;
        right: 48px;
        width: 12px;
        height: 12px;
        background: #ffffff;
        transform: rotate(45deg);
        box-shadow: 3px 3px 6px rgba(15,23,42,0.08);
    }
    @keyframes szw-pulse {
        0%, 100% { box-shadow: 0 18px 42px rgba(217,119,6,0.55), 0 0 0 0 rgba(245,158,11,0.75); }
        50%      { box-shadow: 0 18px 42px rgba(217,119,6,0.55), 0 0 0 28px rgba(245,158,11,0); }
    }
    @keyframes szw-float {
        0%, 100% { transform: translateY(0); }
        50%      { transform: translateY(-4px); }
    }
    /* Tighten the popover panel */
    div[data-testid="stPopoverBody"] {
        min-width: 380px;
        max-width: 440px;
    }
</style>
"""

_IDLE_JS = f"""
<script>
(function() {{
    const parentWin = window.parent;
    if (parentWin.__szwIdleSetup) return;
    parentWin.__szwIdleSetup = true;

    const doc = parentWin.document;
    const body = doc.body;
    parentWin.__szwLastActivity = Date.now();

    const reset = () => {{
        parentWin.__szwLastActivity = Date.now();
        body.classList.remove('szw-idle');
    }};
    ['mousemove', 'keydown', 'scroll', 'click', 'touchstart'].forEach(ev =>
        doc.addEventListener(ev, reset, {{ passive: true, capture: true }})
    );

    setInterval(() => {{
        if (Date.now() - parentWin.__szwLastActivity > {IDLE_MS}) {{
            body.classList.add('szw-idle');
        }}
    }}, 4000);
}})();
</script>
"""


def _inject_floating_assets() -> None:
    st.markdown(_FLOATING_CSS, unsafe_allow_html=True)
    components.html(_IDLE_JS, height=0)


# ---------------------------------------------------------------------------
# Chat handling — explicit accumulator so streaming is reliable
# ---------------------------------------------------------------------------

def _process_query(prompt: str, host: str, model: str, data_context: str) -> str:
    system_msg = {
        "role": "system",
        "content": (
            "You are a data analyst embedded in the Saahas Zero Waste Analytics dashboard. "
            "Answer the user's question using ONLY the DATA CONTEXT below. "
            "Quote concrete numbers in ₹ where helpful, prefer short bullet points, "
            "and if the answer is not in the context, say so plainly and suggest which "
            "dashboard tab to look at (Overview, Sales, Purchase, Revenue Insights, Spend Analysis).\n\n"
            f"=== DATA CONTEXT ===\n{data_context}\n=== END CONTEXT ==="
        ),
    }
    # Trim to last N turns (user + assistant pairs) so we don't re-evaluate
    # an ever-growing transcript. The current user prompt is already at the end.
    history = st.session_state["chat_messages"][-(MAX_HISTORY_TURNS * 2):]
    api_messages = [system_msg] + [
        {"role": m["role"], "content": m["content"]} for m in history
    ]

    placeholder = st.empty()
    placeholder.markdown("_Thinking…_")
    accumulated = ""
    try:
        for chunk in _stream_chat(host, model, api_messages):
            accumulated += chunk
            placeholder.markdown(
                _format_reasoning(accumulated) + "▌", unsafe_allow_html=True
            )
        if accumulated:
            placeholder.markdown(_format_reasoning(accumulated), unsafe_allow_html=True)
            return accumulated
        msg = "_(empty response from model — try a different model or rephrase)_"
        placeholder.markdown(msg)
        return msg
    except requests.exceptions.ConnectionError:
        msg = (
            f"❌ Could not connect to Ollama at `{host}`.\n\n"
            "Make sure Ollama is installed and running:\n"
            "1. Install: https://ollama.com\n"
            "2. Run: `ollama serve` (Windows app starts it automatically)\n"
            "3. Pull a model: `ollama pull llama3.2`"
        )
        placeholder.error(msg)
        return msg
    except requests.exceptions.HTTPError as e:
        try:
            err = e.response.json().get("error", str(e))
        except Exception:
            err = str(e)
        if "not found" in err.lower() or "pull" in err.lower():
            msg = f"❌ Model `{model}` is not installed.\n\nRun: `ollama pull {model}`"
        else:
            msg = f"❌ Ollama error: {err}"
        placeholder.error(msg)
        return msg
    except RuntimeError as e:
        msg = f"❌ Ollama returned an error: {e}"
        placeholder.error(msg)
        return msg
    except Exception as e:
        msg = f"❌ Unexpected error: {e}"
        placeholder.error(msg)
        return msg


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_floating_chatbot(sales_df: pd.DataFrame, purchase_df: pd.DataFrame) -> None:
    _inject_floating_assets()

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    data_context = get_data_context_cached(sales_df, purchase_df)
    no_data = (sales_df is None or sales_df.empty) and (
        purchase_df is None or purchase_df.empty
    )

    with st.popover("📎", help="Ask the data assistant"):
        st.markdown("### 📎 Saahas Data Assistant")
        st.caption("Runs locally via Ollama — your data never leaves this machine.")

        with st.expander("⚙️ Settings", expanded=False):
            host = st.text_input(
                "Ollama host",
                value=st.session_state.get("ollama_host", DEFAULT_HOST),
                key="ollama_host_input",
            )
            st.session_state["ollama_host"] = host

            available = list_ollama_models(host)
            if available:
                prev = st.session_state.get("ollama_model")
                idx = available.index(prev) if prev in available else 0
                model = st.selectbox("Model", available, index=idx, key="ollama_model_select")
            else:
                st.warning(
                    "Ollama unreachable. Start it and pull a model "
                    "(`ollama pull llama3.2`)."
                )
                model = st.selectbox(
                    "Model (typed — not verified)",
                    FALLBACK_MODELS,
                    index=0,
                    key="ollama_model_fallback",
                )
            st.session_state["ollama_model"] = model

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🗑️ Clear chat", use_container_width=True):
                    st.session_state["chat_messages"] = []
                    st.rerun()
            with col_b:
                if st.button("🔥 Warm up model", use_container_width=True,
                             help=f"Preload {model} into memory (keep-alive {KEEP_ALIVE})"):
                    with st.spinner(f"Loading {model}…"):
                        ok, msg = warm_up_model(host, model)
                    (st.success if ok else st.error)(msg)

            show_ctx = st.toggle(
                "Show data context", value=st.session_state.get("show_ctx", False)
            )
            st.session_state["show_ctx"] = show_ctx

            st.markdown("---")
            st.markdown("**📦 Specialized Saahas analyst model**")
            st.caption(
                "Wraps a small base model with a Saahas-specific system prompt + "
                "tuned parameters, registered as a named Ollama model. "
                f"Edit `{MODELFILE_PATH.name}` to swap the base (e.g. `deepseek-r1:1.5b` "
                "for a reasoning model)."
            )
            if st.button(f"🔨 Build `{CUSTOM_MODEL_NAME}` model", use_container_width=True):
                with st.spinner("Running `ollama create`…"):
                    ok, msg = build_saahas_analyst_model()
                (st.success if ok else st.error)(msg)

            opts = _options_for(model)
            mode = "🧠 reasoning preset" if _is_reasoning_model(model) else "⚡ fast preset"
            st.caption(
                f"{mode}: temp={opts['temperature']}, ctx={opts['num_ctx']}, "
                f"max_tokens={opts['num_predict']}, keep_alive={KEEP_ALIVE}, "
                f"history={MAX_HISTORY_TURNS} turns. "
                "Server-side tuning (flash_attn, q8_0 KV cache, num_parallel=1) "
                "comes from `start_ollama.ps1`."
            )

        if no_data:
            st.info("📂 Upload sales or purchase data above to chat about it.")
        elif st.session_state.get("show_ctx"):
            with st.expander("Data context sent to model", expanded=False):
                st.code(data_context, language="text")

        # Suggested prompts as quick buttons
        if not st.session_state["chat_messages"] and not no_data:
            st.markdown("**Try asking:**")
            suggestions = [
                "Summarize the key revenue and spend numbers.",
                "Which vendors should I review first?",
                "What's driving profit or loss?",
                "Top 3 categories by spend?",
            ]
            cols = st.columns(2)
            for i, s in enumerate(suggestions):
                if cols[i % 2].button(s, key=f"sugg_{i}", use_container_width=True):
                    st.session_state["_pending_prompt"] = s

        # Render history
        msg_box = st.container(height=320)
        with msg_box:
            for msg in st.session_state["chat_messages"]:
                with st.chat_message(msg["role"]):
                    if msg["role"] == "assistant":
                        st.markdown(
                            _format_reasoning(msg["content"]),
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(msg["content"])

        # Input form (more reliable inside a popover than st.chat_input)
        prompt = st.session_state.pop("_pending_prompt", None)
        with st.form(key="chatbot_form", clear_on_submit=True):
            typed = st.text_input(
                "Question",
                placeholder="Ask about revenue, vendors, categories, trends…",
                label_visibility="collapsed",
                key="chatbot_input",
            )
            submitted = st.form_submit_button("Send", use_container_width=True)
        if submitted and typed and typed.strip():
            prompt = typed.strip()

        if prompt:
            st.session_state["chat_messages"].append({"role": "user", "content": prompt})
            with msg_box:
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    reply = _process_query(
                        prompt,
                        st.session_state["ollama_host"],
                        st.session_state["ollama_model"],
                        data_context,
                    )
            st.session_state["chat_messages"].append({"role": "assistant", "content": reply})

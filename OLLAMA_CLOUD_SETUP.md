# Cloud Deployment Guide: Ollama External API Setup

## Overview
This guide explains how to deploy your Saahas dashboard to **Streamlit Cloud** with **external Ollama AI** (Option 3).

Why external Ollama?
- ✅ Streamlit Cloud doesn't support GPU compute
- ✅ Ollama needs significant computational resources
- ✅ Host Ollama separately, connect via API
- ✅ Cost-effective: ~$200-400/month for reliable AI

---

## Architecture

```
Your Computer
    ↓
Streamlit Cloud (Frontend) ←→ External Ollama Server (AI Engine)
    ↓                                ↓
  Dashboard                     RunPod/Lambda Labs GPU
   (Python)                      (Ollama Service)
```

---

## Part 1: Set Up External Ollama Server

### Option A: RunPod (Recommended - Easiest)

**Why RunPod?**
- Pre-built Ollama container available
- Easy one-click deployment
- Public API access
- ~$0.29/hr for RTX 4090

**Steps:**

1. **Create RunPod Account**
   - Go to https://www.runpod.io/
   - Sign up (use referral code for credits)
   - Add payment method

2. **Deploy Ollama Pod**
   - Click "Community Cloud" → Search "Ollama"
   - Select official Ollama template
   - Choose GPU: RTX 4090 (recommended) or RTX 3090
   - Click "Rent GPU"
   - Wait 2-3 minutes for pod to start

3. **Get Public URL**
   - Once pod starts, note the public API URL
   - Example: `https://abc123def456-11434.proxy.runpod.io`
   - This is your `OLLAMA_API_URL`

4. **Pull Models** (Optional but recommended)
   - In pod terminal, run: `ollama pull llama2`
   - This pre-loads the model for faster first request

5. **Cost Tracking**
   - Pod costs ~$210/month if left running 24/7
   - You can pause when not in use ($0.01/hr storage)

---

### Option B: Lambda Labs

**Alternative to RunPod:**

1. Go to https://lambdalabs.com/
2. Create account
3. Launch GPU instance with Ubuntu + Python
4. SSH and install Ollama:
   ```bash
   curl https://ollama.ai/install.sh | sh
   ollama serve &
   ollama pull llama2
   ```
5. Get public IP as API endpoint

---

### Option C: Your Own GPU Machine

**If you have a local GPU:**

1. Install Ollama: https://ollama.ai
2. Start server: `ollama serve`
3. Expose to internet (ngrok, cloudflare tunnel, or port forward)
4. Use public URL as `OLLAMA_API_URL`

---

## Part 2: Deploy to Streamlit Cloud

### Step 1: Push Code to GitHub

Ensure your repo has these files:
```
requirements.txt              ✅ (includes python-dotenv)
ollama_client.py             ✅ 
app.py                       ✅ (unchanged)
.env.example                 ✅
.streamlit/secrets.toml.example ✅
```

```bash
git add .
git commit -m "Add Ollama cloud setup"
git push origin main
```

### Step 2: Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io/
2. Click "New app"
3. Connect GitHub repo
4. Select:
   - Repository: `DipjyotiBora25/Saahas-Value-chain-Analytics`
   - Branch: `main`
   - Main file path: `app.py`
5. Click "Deploy"

### Step 3: Add Secrets

**Critical:** Your Ollama URL must be in Streamlit Secrets (NOT in code)

1. After deployment, click ⋮ (menu) → Settings
2. Click "Secrets"
3. Paste this TOML (replace with your RunPod URL):

```toml
OLLAMA_API_URL = "https://your-runpod-pod-id-11434.proxy.runpod.io"
OLLAMA_MODEL = "llama2"
```

4. Click "Save"
5. App restarts automatically ✅

---

## Part 3: Verify Setup

### Test Connection

Once deployed:

1. Open your Streamlit app
2. If Ollama is working, you should see:
   - ✅ No error messages in logs
   - ✅ AI chatbot loads without errors
   - ✅ Models available in chatbot dropdown

### View Logs

```
App → ⋮ → View logs
```

Look for:
- ✅ "Ollama server available" 
- ❌ "Ollama server unreachable" → Check URL & RunPod pod status

---

## Troubleshooting

### Issue: "Ollama server unreachable"

**Causes & Fixes:**

| Issue | Fix |
|-------|-----|
| RunPod pod is stopped | Go to RunPod dashboard → Start pod |
| Wrong URL format | Check URL ends with `:11434`, starts with `https://` |
| Firewall blocking | RunPod pods use `proxy.runpod.io` which is public by default |
| Network timeout | Ollama server is slow; give it 30+ seconds |

### Issue: "Model not found"

- SSH to RunPod pod
- Run: `ollama pull llama2`
- Verify: `ollama list`

### Issue: Slow responses

- Increase pod GPU (RTX 4090 is faster than 3090)
- Use smaller model: `mistral` instead of `llama2-13b`
- Cold start? First request loads model (~5-30 sec is normal)

---

## Cost Breakdown

### Monthly Costs (Example)

| Component | Cost | Notes |
|-----------|------|-------|
| RunPod GPU (RTX 4090) | $210 | 24/7 usage. Can pause for $0.01/hr |
| Streamlit Cloud | $0 | Free tier included |
| **Total** | **~$210** | Can reduce by pausing pod |

### Cost Optimization

- **Option 1:** Pause pod when not in use
  - Running: $0.29/hr
  - Paused: $0.01/hr storage only
  - Example: 8 hrs/day usage = ~$70/month

- **Option 2:** Smaller GPU (RTX 3090)
  - ~$0.18/hr instead of $0.29/hr
  - Still good performance

- **Option 3:** Smaller models (Mistral instead of Llama2)
  - Faster inference
  - Less VRAM needed

---

## Security Notes

**DO NOT:**
- ❌ Hardcode `OLLAMA_API_URL` in `app.py`
- ❌ Commit `.env` file with real URLs
- ❌ Share RunPod public URLs in public repos

**DO:**
- ✅ Use Streamlit Secrets (encrypted in Streamlit Cloud)
- ✅ Keep `.env` local only (add to `.gitignore`)
- ✅ Use environment variables for all sensitive config

---

## Next Steps

1. **Deploy Ollama on RunPod** (10 min)
2. **Deploy App to Streamlit Cloud** (5 min)
3. **Add Secrets** (2 min)
4. **Test AI Features** (verify working)

**Total Setup Time: ~20 minutes**

---

## FAQ

**Q: Can I use free tier?**
A: Streamlit Cloud is free. Ollama requires paid GPU ($200+/month).

**Q: What if I pause the RunPod pod?**
A: App shows "Ollama server unreachable" message but doesn't crash. Start pod to resume AI features.

**Q: Can I use different models?**
A: Yes! Change `OLLAMA_MODEL` secret. Ensure model is pulled on Ollama server: `ollama pull mistral`

**Q: How long do requests take?**
A: First request: 5-30 sec (model loading). Subsequent: 2-10 sec depending on model size.

**Q: Can I use the same Ollama for multiple apps?**
A: Yes! Multiple Streamlit apps can share one RunPod Ollama server.

---

## Support

- **RunPod Issues:** https://docs.runpod.io/
- **Ollama Docs:** https://ollama.ai/
- **Streamlit Docs:** https://docs.streamlit.io/

---

**✅ Setup Complete!** Your dashboard is now AI-powered in the cloud.

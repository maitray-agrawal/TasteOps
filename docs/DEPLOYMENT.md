# TasteOps Production Deployment Guide

**Target Runtime:** Render Web Service (Docker)  
**FastAPI ASGI Entrypoint:** `tasteops.api.main:app`  
**Automated CI Gates:** GitHub Actions (`.github/workflows/ci.yml`)

---

## 1. Prerequisites

- A GitHub repository containing the latest `main` branch.
- A [Render](https://render.com) account.
- A valid **Qloo Hackathon API Key**.

---

## 2. One-Click Blueprint Deployment (`render.yaml`)

TasteOps provides a native Render Blueprint specification ([`render.yaml`](file:///d:/TasteOps/render.yaml)).

1. Log into your **Render Dashboard**.
2. Click **Blueprints** → **New Blueprint Instance**.
3. Select the `TasteOps` repository.
4. Render will parse [`render.yaml`](file:///d:/TasteOps/render.yaml) and configure:
   - **Service Name:** `tasteops-backend`
   - **Runtime:** `Docker` (using [`Dockerfile`](file:///d:/TasteOps/Dockerfile))
   - **Health Check Path:** `/health`
   - **Environment Variables:** `ENVIRONMENT=production`, `QLOO_BASE_URL=https://hackathon.api.qloo.com`, etc.
5. In the blueprint variables screen, enter your secret `QLOO_API_KEY`.
6. Click **Apply**.

---

## 3. Manual Render Web Service Setup

If configuring manually without blueprints:

1. Click **New +** → **Web Service**.
2. Connect `https://github.com/maitray-agrawal/TasteOps.git`.
3. Choose branch: `main`.
4. Select **Docker** runtime.
5. Set **Region:** `Oregon (US West)`.
6. Add the following **Environment Variables**:

| Variable | Value | Notes |
|---|---|---|
| `ENVIRONMENT` | `production` | Enables production settings. |
| `QLOO_BASE_URL` | `https://hackathon.api.qloo.com` | Official hackathon API base URL. |
| `QLOO_API_KEY` | *(Your actual Qloo key)* | Marked as sensitive secret. |
| `CORS_ORIGINS` | `http://localhost:3000,https://<your-vercel-domain>.vercel.app` | Comma-separated allowed frontend origins. |
| `TASTEOPS_STORAGE_DIR` | `/app/storage/workflows` | Filesystem persistence path. |
| `LOG_LEVEL` | `INFO` | Standard structured logging. |

7. Expand **Advanced Settings**:
   - Set **Health Check Path:** `/health`
8. Click **Create Web Service**.

---

## 4. Verifying Deployment

Once deployed, verify container health:

```bash
# Liveness probe (<5ms, zero upstream calls)
curl -i https://<your-app>.onrender.com/health
# Expected: HTTP 200 OK {"status": "ok", "version": "0.1.0"}

# Readiness probe (verifies key & storage)
curl -i https://<your-app>.onrender.com/ready
# Expected: HTTP 200 OK {"status": "ready", "qloo_configured": true, ...}
```

---

## 5. Local Docker Container Testing

To test the production container locally:

```bash
# 1. Build container image
docker build -t tasteops-backend .

# 2. Run container
docker run -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e QLOO_API_KEY="your_qloo_key_here" \
  tasteops-backend

# 3. Test liveness in another terminal
curl http://localhost:8000/health
```

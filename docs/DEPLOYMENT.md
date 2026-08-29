# 🚀 100% Free Production Deployment Guide

Deploy the **Code Review App** 24/7 with zero hosting costs using:
* **Render.com** — Free Web Service (FastAPI + Celery Worker in a unified Docker container)
* **UptimeRobot** — Free automated health monitor (prevents Render from sleeping)
* **Neon** — Serverless PostgreSQL 16 (0.5 GB free storage)
* **Upstash** — Serverless Redis (10,000 commands/day free)

---

## 📑 Prerequisites Checklist
1. A GitHub account with access to [`MehulKauGit/Code-Review-App`](https://github.com/MehulKauGit/Code-Review-App).
2. A free [Neon Account](https://neon.tech).
3. A free [Upstash Account](https://upstash.com).
4. A free [Render Account](https://render.com).
5. A free [UptimeRobot Account](https://uptimerobot.com).

---

## 🛠️ Step 1: Provision Free PostgreSQL on Neon

1. Log in to [Neon Console](https://console.neon.tech).
2. Click **"Create Project"**, name it `code-review-db`, and select your nearest region.
3. In the project dashboard, locate the **Connection Details** box.
4. Copy the connection string (e.g. `postgres://user:password@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require`).
5. **Convert to Asyncpg URL:** Change prefix from `postgres://` to `postgresql+asyncpg://`:
   ```
   postgresql+asyncpg://user:password@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   *(Save this as your `DATABASE_URL`)*.

---

## 🛠️ Step 2: Provision Free Redis on Upstash

1. Log in to [Upstash Console](https://console.upstash.com).
2. Click **"Create Database"**, name it `code-review-redis`, and choose your region.
3. In the dashboard, scroll down to the **"Connect"** section and select the **"Node / Python" / "redis-cli"** tab.
4. Copy the `rediss://...` TCP connection URL (e.g. `rediss://default:password@xyz.upstash.io:6379`).
   *(Save this as your `REDIS_URL`)*.

---

## 🛠️ Step 3: Deploy on Render.com (100% Free)

### Option A: 1-Click Blueprint Deploy (Recommended)
1. In [Render Dashboard](https://dashboard.render.com), click **"New +"** -> **"Blueprint"**.
2. Connect your repository `MehulKauGit/Code-Review-App`.
3. Render will detect [`render.yaml`](file:///d:/Trash/git/Code-Review-App/render.yaml) automatically.
4. Fill in the environment variable values when prompted (from Step 1 & 2) and click **"Apply"**.

### Option B: Manual Web Service Deploy
1. Click **"New +"** -> **"Web Service"** -> Choose your GitHub repository `MehulKauGit/Code-Review-App`.
2. Configure settings:
   * **Runtime:** `Docker`
   * **Instance Type:** `Free` ($0/month)
   * **Health Check Path:** `/health`
3. Under **"Environment Variables"**, add:

| Key | Value | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Neon PostgreSQL Connection string |
| `REDIS_URL` | `rediss://...` | Upstash Redis Connection string |
| `API_KEY` | `your-secret-api-key` | Token used to authenticate `/review` calls |
| `LLM_API_KEY` | `gsk_...` | Groq or Gemini API key |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Target LLM model |
| `GITHUB_WEBHOOK_SECRET` | `your-webhook-secret` | Secret configured in GitHub App |
| `GITHUB_APP_ID` | `12345` | GitHub App ID (optional) |
| `GITHUB_APP_INSTALLATION_ID` | `67890` | GitHub App Installation ID (optional) |
| `GITHUB_APP_PRIVATE_KEY` | `"-----BEGIN RSA..."` | Raw PEM string (optional) |
| `RATE_LIMIT_REVIEW_MAX` | `10` | Max requests per window |
| `RATE_LIMIT_REVIEW_WINDOW_SECONDS` | `60` | Rate limit window in seconds |

4. Click **"Create Web Service"**.

---

## 🛠️ Step 4: Keep Render Awake 24/7 with UptimeRobot (Free)

Render free instances spin down after 15 minutes of inactivity. To keep your API and Celery worker running **24/7 without ever sleeping**:

1. Log in to [UptimeRobot](https://uptimerobot.com).
2. Click **"+ Add New Monitor"**.
3. Fill in:
   * **Monitor Type:** `HTTP(s)`
   * **Friendly Name:** `Code Review App Health`
   * **URL (or IP):** `https://your-app-name.onrender.com/health`
   * **Monitoring Interval:** `Every 10 minutes` (or 5 minutes)
4. Click **"Create Monitor"**.

> [!TIP]
> This ping keeps your Render free container permanently awake at **$0.00 cost**, ensuring zero cold-start delay for GitHub PR reviews and webhook delivery.

---

## 🛠️ Step 5: Verify Deployment

### 1. Test Health & Readiness:
```powershell
curl https://your-app-name.onrender.com/health
# Output: {"status":"healthy"}

curl https://your-app-name.onrender.com/ready
# Output: {"status":"ready","database":"healthy","redis":"healthy"}
```

### 2. Test Authenticated Review Submission:
```powershell
curl -X POST "https://your-app-name.onrender.com/review" `
  -H "X-API-Key: your-secret-api-key" `
  -H "Content-Type: application/json" `
  -d '{"diff": "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-print(\"hi\")\n+print(\"hello\")\n"}'
```

### 3. Connect GitHub App Webhook:
* Set your GitHub App **Webhook URL** to:
  ```
  https://your-app-name.onrender.com/webhook
  ```
* Set **Webhook Secret** to match `GITHUB_WEBHOOK_SECRET`.

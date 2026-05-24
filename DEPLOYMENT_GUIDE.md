# Deploying Yahoo Mail Cleanup Agent

## Architecture Overview

This application requires **two components** to work:
1. **Frontend** - Next.js web interface (deploys to Vercel)
2. **Backend** - Python Flask server for IMAP access (requires persistent server)

### Why Two Components?

Vercel is a **serverless platform** - it runs code temporarily when requested and then stops. But **IMAP connections need to stay open** to work with emails. This means the Python backend must run on a **persistent server**.

---

## Option 1: Recommended - Split Deployment

### Frontend → Vercel (https://vercel.com)
- Next.js React application
- User interface
- Static files and API calls

### Backend → Railway (https://railway.app) or Render (https://render.com)
- Python Flask server
- IMAP connection to Yahoo
- Runs 24/7 on a persistent server
- **FREE tier available** on both platforms

---

## Option 2: Single Server (Beginner Friendly)

### Both Frontend + Backend → Railway or Render

You can deploy both parts together on platforms that support Python.

---

## Step-by-Step: Option 1 (Recommended)

### Part A: Deploy Backend to Railway

1. **Create GitHub Repository** (for the backend)
   - Create a new repo: `yahoo-mail-cleanup-backend`
   - Copy the `/backend` folder contents to this repo
   - Include `requirements.txt` and `app.py`

2. **Deploy to Railway**
   - Go to: https://railway.app
   - Sign up with GitHub
   - Click **New Project** → **Deploy from GitHub**
   - Select your `yahoo-mail-cleanup-backend` repo
   - Railway auto-detects Python

3. **Set Environment Variables**
   In Railway dashboard, add:
   - `PORT` = `5000`
   - (No other env vars needed - credentials entered in the app)

4. **Get Your Backend URL**
   - After deployment, Railway gives you a URL like:
   - `https://yahoo-mail-cleanup-backend.up.railway.app`
   - Or custom domain if you set one

5. **Update Frontend Code**
   - Edit `vercel-app/src/lib/api.ts` to use your Railway URL:
   ```typescript
   const API_BASE = 'https://your-railway-app.railway.app';
   ```

### Part B: Deploy Frontend to Vercel

1. **Create GitHub Repository** (for the frontend)
   - Create a new repo: `yahoo-mail-cleanup-frontend`
   - Copy the `/vercel-app` folder contents to this repo

2. **Deploy to Vercel**
   - Go to: https://vercel.com
   - Sign up with GitHub
   - Click **Add New Project**
   - Select your `yahoo-mail-cleanup-frontend` repo
   - Vercel auto-detects Next.js

3. **Configure**
   - Framework Preset: **Next.js**
   - Root Directory: `.` (default)
   - Build Command: `npm run build`
   - Output Directory: `.next`

4. **Deploy!**
   - Vercel gives you a URL like:
   - `https://yahoo-mail-cleanup.vercel.app`

---

## Alternative: Deploy Everything to Render

### Why Render?

Render offers both Python and Next.js hosting with a **free tier** that works well for this project.

### Step-by-Step on Render

1. **Create GitHub Repository**
   - Include both `/backend` and `/vercel-app` folders
   - Create a `render.yaml` for configuration

2. **Create Two Services on Render:**

#### Service 1: Backend (Python)
- **New** → **Blueprint**
- Select `render.yaml` from your repo

#### Service 2: Frontend (Static)
- **New** → **Static Site**
- Build Command: `npm run build`
- Publish Directory: `.next`

---

## File Structure for GitHub

```
yahoo-mail-cleanup/
├── backend/                    # Python Flask backend
│   ├── app.py                 # Main Flask application
│   ├── triage.py             # Email triage utilities
│   ├── unsubscribe_service.py # Unsubscribe HTTP service
│   └── requirements.txt       # Python dependencies
├── frontend/                   # Original static HTML version
│   └── index.html
├── vercel-app/                 # Next.js version for Vercel
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx       # Main page
│   │   │   └── layout.tsx    # Layout
│   │   ├── components/        # React components
│   │   └── lib/
│   │       └── api.ts        # API client
│   ├── public/
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── next.config.js
├── vercel.json               # Vercel config
└── README.md
```

---

## Important Notes

### Security

1. **App Passwords**: Each user needs their own Yahoo app password
2. **Session Storage**: Credentials are NOT stored on the server
3. **IMAP Connection**: Each user connects directly from their browser to Yahoo

### Limitations

- **Backend Must Run 24/7**: IMAP connections require persistent server
- **Rate Limits**: Yahoo may throttle connections if too many requests
- **Session Timeout**: Inactive connections may time out

### Recommended Workflow

1. **Start backend** → Connect with email + app password
2. **Do email cleanup** → Browse, delete, unsubscribe
3. **Disconnect** → Click "Disconnect" when done
4. **Start again later** → Credentials are entered fresh each time

---

## Quick Reference

### Free Tier Services

| Service | Type | Free Tier | Notes |
|---------|------|-----------|-------|
| Railway | Python hosting | 500 hrs/month | Sleeps after 5 min inactivity |
| Render | Python/Static | Free forever | No sleep, but slower |
| Vercel | Next.js hosting | 100 hrs/month | Sleeps after 10 min inactivity |

### Recommended Combination
- **Frontend**: Vercel (fast, reliable)
- **Backend**: Railway (easy Python deployment) or Render

---

## Troubleshooting

### "Connection Refused" on Frontend
- Check your backend URL is correct in `api.ts`
- Ensure backend server is running
- Check Railway/Render logs for errors

### "IMAP Connection Failed"
- Verify Yahoo app password is correct
- Check Yahoo account security settings
- Try generating a new app password

### "Backend Timeout"
- Some free tiers sleep after inactivity
- Wake it up by making a request or visiting the URL

---

## Getting Help

If stuck:
1. Check Railway/Render documentation
2. Verify all files are correctly copied
3. Check environment variables are set
4. Review server logs for errors
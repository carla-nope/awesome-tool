# Yahoo Mail Cleanup Agent

A web-based tool for managing your Yahoo Mail inbox with AI-powered triage and true unsubscribe capabilities.

## Features

- **Search & Browse** - View, search, and filter emails
- **Bulk Delete** - Delete multiple emails at once
- **True Unsubscribe** - Actually visit unsubscribe URLs to opt-out of mailing lists
- **AI Triage Mode** - Leverage AI to categorize and batch-process emails
- **Extract Links** - Automatically detect unsubscribe links

## Quick Start

### 1. Get Yahoo App Password

1. Go to: https://login.yahoo.com/myaccount/security
2. Sign in with your Yahoo email
3. Find **"App passwords"** section
4. Generate a new app password for "Mail"
5. Copy the password (shown only once)

### 2. Run Locally

```bash
# Clone or download the project

# Option A: Use the Flask backend (single folder, local only)
cd backend
pip install -r requirements.txt
python app.py

# Option B: Use the Next.js frontend with separate backend
cd vercel-app
npm install
npm run dev
```

### 3. Open Browser

Navigate to: http://localhost:5000 (Flask) or http://localhost:3000 (Next.js)

### 4. Connect

Enter your Yahoo email and app password to connect.

## Deployment (For Multiple Users)

This application requires **two components** for cloud deployment:

### Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Browser  │───▶│   Frontend  │───▶│   Backend   │
│   (You)     │◀───│   (Vercel)  │◀───│   (Railway) │
└─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                        ┌─────────────┐
                                        │  Yahoo Mail │
                                        │    (IMAP)   │
                                        └─────────────┘
```

### Deploy to Cloud (Multiple Computers)

#### Part 1: Deploy Backend to Railway

1. Create a GitHub repository for the backend
2. Copy the `/backend` folder to the repo
3. Deploy to [Railway](https://railway.app):
   - Sign up with GitHub
   - Create new project → Deploy from GitHub
   - Railway auto-detects Python
4. Get your Railway URL (e.g., `https://yahoo-mail-cleanup.up.railway.app`)

#### Part 2: Deploy Frontend to Vercel

1. Create a GitHub repository for the frontend
2. Copy the `/vercel-app` folder to the repo
3. Deploy to [Vercel](https://vercel.com):
   - Sign up with GitHub
   - Import the repo
   - Vercel auto-detects Next.js
4. In `src/lib/api.ts`, update `API_BASE` to your Railway URL

### After Deployment

Both you and your boyfriend can access the app at the Vercel URL:
- Enter your own Yahoo email + app password
- Each person connects with their own credentials

## File Structure

```
yahoo-mail-cleanup/
├── backend/                    # Python Flask backend (deploy to Railway)
│   ├── app.py                 # Main Flask application
│   ├── triage.py             # Email triage utilities
│   ├── unsubscribe_service.py # HTTP unsubscribe service
│   └── requirements.txt       # Python dependencies
├── vercel-app/                 # Next.js frontend (deploy to Vercel)
│   ├── src/
│   │   ├── app/              # Next.js app
│   │   ├── components/        # React components
│   │   └── lib/              # API client
│   ├── package.json
│   └── ...
├── frontend/                   # Original static HTML version
├── SPEC.md                    # Technical specification
├── SETUP_GUIDE.md            # Full setup guide
├── QUICK_START.md             # Quick reference
└── DEPLOYMENT_GUIDE.md       # Cloud deployment instructions
```

## Security Notes

- **App Passwords**: Each user needs their own Yahoo app password
- **No Server Storage**: Credentials are never stored on the server
- **Direct IMAP**: Connections go directly from browser to Yahoo
- **Revocable**: You can revoke app passwords anytime from Yahoo Account Security

## Troubleshooting

### "Invalid Credentials"
- Use an App Password, not your regular password
- Generate a new app password if needed

### Connection Timeout
- Check your internet connection
- Try restarting the backend server

### Backend Won't Start
- Ensure port 5000 is not in use
- Run: `python backend/app.py`

## Tech Stack

- **Backend**: Python, Flask, IMAP (Yahoo Mail)
- **Frontend**: Next.js 14, React, Tailwind CSS
- **Cloud**: Vercel (frontend), Railway (backend)
- **HTTP**: requests library, BeautifulSoup

## License

MIT License - Use freely for personal email management

## Support

For issues or questions, check:
1. [SETUP_GUIDE.md](SETUP_GUIDE.md) - Full setup instructions
2. [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Cloud deployment
3. [QUICK_START.md](QUICK_START.md) - Quick reference
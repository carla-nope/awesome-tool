# Yahoo Mail Cleanup Agent - Quick Start Checklist

## Pre-Setup Checklist

- [ ] I have Python 3.8+ installed
  - Run: `python --version` (Windows) or `python3 --version` (Mac/Linux)
- [ ] I have a Yahoo Mail account
- [ ] I have access to https://login.yahoo.com/myaccount/security

---

## Step 1: Get Yahoo App Password

1. Go to: https://login.yahoo.com/myaccount/security
2. Sign in with your Yahoo email and password
3. Find **"App passwords"** section
4. Click **Generate app password** (or similar)
5. Select app: **Mail** or **Other apps**
6. Name it: `Yahoo Mail Cleanup`
7. Click **Create**
8. ✅ **COPY THE PASSWORD IMMEDIATELY** (shown only once!)
9. Paste it somewhere safe

---

## Step 2: Install Dependencies

**Windows (PowerShell):**
```powershell
cd path\to\yahoo-mail-cleanup
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

**Mac/Linux (Terminal):**
```bash
cd path/to/yahoo-mail-cleanup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Step 3: Start the Server

```bash
python backend/app.py
```

Expected output:
```
* Running on http://0.0.0.0:5000
* Press CTRL+C to quit
```

---

## Step 4: Open in Browser

1. Open Chrome/Firefox/Edge/Safari
2. Go to: http://localhost:5000
3. You'll see the login screen

---

## Step 5: Connect

1. Enter your **Yahoo email** (e.g., `yourname@yahoo.com`)
2. Enter your **App Password** (the 16-char one from Step 1)
3. Click **Connect to Yahoo Mail**
4. ✅ You should see the dashboard!

---

## Quick Feature Reference

| What You Want | How To Do It |
|--------------|--------------|
| Delete emails | Checkbox + Delete Selected |
| Search emails | Use search bar or Advanced Search |
| Filter by type | Use Quick Filters sidebar |
| Full unsubscribe | Open email → Full Unsubscribe button |
| AI batch process | Click "AI Triage Mode" tab → Extract Batch |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Invalid credentials" | Use App Password, not regular password |
| "Connection timeout" | Check internet, try again in a few minutes |
| Server won't start | Port 5000 may be in use; close other apps |
| Can't find app password | Go to Yahoo Account Security → App passwords |

---

## Quick Tips

- ✅ Use **AI Triage Mode** for processing many emails quickly
- ✅ Use **Full Unsubscribe** to actually stop future emails
- ✅ Emails go to **Trash** first - can recover for 7 days
- ✅ Disconnect when done to clear session

---

## Done! You're Ready to Clean Up Your Inbox 🚀
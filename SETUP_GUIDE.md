# Yahoo Mail Cleanup Agent - Setup & User Guide

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Step 1: Get Yahoo App Password](#step-1-get-yahoo-app-password)
4. [Step 2: Install Dependencies](#step-2-install-dependencies)
5. [Step 3: Run the Application](#step-3-run-the-application)
6. [Step 4: Access the Interface](#step-4-access-the-interface)
7. [Feature Guide](#feature-guide)
   - [Browse & Delete Mode](#browse--delete-mode)
   - [AI Triage Mode](#ai-triage-mode)
   - [True Unsubscribe](#true-unsubscribe)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The **Yahoo Mail Cleanup Agent** is a web-based tool that helps you manage your Yahoo inbox efficiently. It provides:
- Search and browse emails
- Bulk delete emails
- **True Unsubscribe** - actually visits unsubscribe URLs to opt-out of mailing lists
- **AI Triage Mode** - leverage AI to categorize and action emails in batches
- Extract unsubscribe links
- Move emails to folders

---

## Prerequisites

Before starting, ensure you have:
- A Yahoo Mail account
- Python 3.8 or higher installed
- Internet connection
- A web browser (Chrome, Firefox, Safari, Edge)

---

## Step 1: Get Yahoo App Password

Yahoo requires an **App Password** for IMAP access. This is different from your regular password for security.

### Generate App Password:

1. **Open Yahoo Account Security**
   - Go to: https://login.yahoo.com/myaccount/security
   - Sign in with your Yahoo email and regular password

2. **Navigate to App Passwords**
   - Scroll down to **App passwords**
   - Click **Generate app password** or **Create new app password**

3. **Create App Password**
   - Select app type: Choose **Mail** or **Other apps**
   - Name it something like: `Yahoo Mail Cleanup`
   - Click **Create**
   - **Copy the generated password** (16 characters, no spaces)

   > ⚠️ **Important:** Yahoo only shows this password ONCE. Copy it immediately to a secure location.

4. **Store Your App Password**
   - Write it down or copy to a password manager
   - You'll need it to connect the application

---

## Step 2: Install Dependencies

### For Windows (PowerShell or Command Prompt):

```powershell
# Navigate to the yahoo-mail-cleanup folder
cd path\to\yahoo-mail-cleanup

# Create a virtual environment (recommended)
python -m venv venv

# Activate the virtual environment
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### For macOS/Linux (Terminal):

```bash
# Navigate to the yahoo-mail-cleanup folder
cd path/to/yahoo-mail-cleanup

# Create a virtual environment (recommended)
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### What Gets Installed:
- **Flask** - Web framework
- **Werkzeug** - WSGI utilities
- **requests** - HTTP library (for visiting unsubscribe URLs)
- **beautifulsoup4** - HTML parsing (for extracting unsubscribe links)

---

## Step 3: Run the Application

### Start the Server:

```bash
# With virtual environment active
python backend/app.py
```

You should see output like:
```
* Running on http://0.0.0.0:5000
* Press CTRL+C to quit
```

### Keep Server Running:
- The server must stay running while you use the application
- Open a **new terminal window** if you need to run other commands
- To stop the server: Press `Ctrl+C` in the terminal running it

---

## Step 4: Access the Interface

1. **Open Your Web Browser**

2. **Navigate to:**
   ```
   http://localhost:5000
   ```

3. **Connect to Yahoo:**
   - Enter your **Yahoo email address** (e.g., `yourname@yahoo.com`)
   - Enter your **App Password** (the 16-character password you generated)
   - Click **Connect to Yahoo Mail**

4. **You're In!** The dashboard will load showing your email statistics.

---

## Feature Guide

### Browse & Delete Mode

This is the default mode for manual email management.

**To Delete Emails:**
1. Browse your email list in the left panel
2. Click the **checkbox** next to emails you want to delete
3. Click **Delete Selected** button (red)
4. Confirm the deletion

**To Search:**
1. Use the search bar at the top of the sidebar
2. Click **Advanced Search** for more filters:
   - Filter by sender (from address)
   - Filter by subject keyword
   - Filter by date range
   - Full-text search in email body

**Quick Filters:**
- All Emails
- Unread
- Have Unsubscribe Link
- Marketing/Promotional

---

### AI Triage Mode

This mode lets you process emails in batches using AI analysis.

**Workflow:**

```
┌─────────────────────────────────────────────────────────────┐
│  1. EXTRACT BATCH                                           │
│     Click "Extract Batch" to get emails formatted for AI   │
├─────────────────────────────────────────────────────────────┤
│  2. COPY TO AI                                              │
│     Click "Copy to Clipboard"                               │
│     Paste into Chat/Minimax with the system prompt         │
├─────────────────────────────────────────────────────────────┤
│  3. AI ANALYSIS                                             │
│     AI returns a Markdown table with recommendations        │
├─────────────────────────────────────────────────────────────┤
│  4. APPROVE                                                  │
│     Review the table                                        │
│     Type: "Approved. Please generate the JSON execution block"
│     Copy the JSON block that appears                        │
├─────────────────────────────────────────────────────────────┤
│  5. EXECUTE                                                  │
│     Paste JSON into the text area                          │
│     Click "Execute Approved Commands"                       │
│     Confirm the action                                       │
└─────────────────────────────────────────────────────────────┘
```

**Configuration:**
- **Batch Start**: Which email in your inbox to start from (0 = newest)
- **Batch Size**: How many emails per batch (5-50 recommended)

---

### True Unsubscribe

This feature actually visits unsubscribe URLs to opt-out of mailing lists.

**To Unsubscribe from a Sender:**

1. **Open any email** from the sender you want to unsubscribe from

2. **Click "Full Unsubscribe"** button in the email detail panel

3. **Review the confirmation:**
   - System will visit the unsubscribe URL from that email
   - System will delete ALL emails from that sender
   - Future emails should stop

4. **Confirm** to proceed

**What Happens:**
- System extracts the unsubscribe URL from the email
- System visits the URL via HTTP to complete opt-out
- System deletes all emails from that sender
- System reports success/failure

> ⚠️ **Note:** Some mailing lists may take 24-48 hours to process unsubscribe requests. You may still receive a few emails before they stop completely.

---

## Troubleshooting

### "Connection Failed" or "Invalid Credentials"

**Solutions:**
1. Double-check you're using an **App Password**, not your regular password
2. Verify your Yahoo email address is correct
3. Ensure you copied the app password correctly (no spaces)
4. Check if your Yahoo account has 2-step verification enabled
5. Try generating a new app password

### "Connection Timeout"

**Solutions:**
1. Check your internet connection
2. Try restarting the application
3. Yahoo may be experiencing temporary issues - wait a few minutes and retry

### "Failed to Extract Batch"

**Solutions:**
1. Ensure you're connected to Yahoo
2. Check your internet connection
3. Try a smaller batch size (e.g., 10 instead of 20)

### "Unsubscribe URL Not Found"

**Solutions:**
1. Some emails don't have visible unsubscribe links
2. Try a different email from the same sender
3. Look for unsubscribe links in the email footer

### Server Won't Start

**Solutions:**
1. Ensure port 5000 is not in use by another application
2. Try running: `python backend/app.py`
3. Check for Python installation: `python --version`

---

## Security Notes

- **App Password**: Keep it secure. It provides full access to your Yahoo Mail.
- **Data Storage**: All data stays on your local machine during the session.
- **Session**: Logout (click Disconnect) when done to clear session data.
- **Revoke Access**: You can revoke app passwords anytime at Yahoo Account Security.

---

## Quick Reference

### Commands
```bash
# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Start server
python backend/app.py

# Install dependencies
pip install -r requirements.txt
```

### Access URLs
- **Application**: http://localhost:5000
- **Yahoo Account Security**: https://login.yahoo.com/myaccount/security

### Keyboard Shortcuts
- `Ctrl+C` in terminal - Stop the server
- Refresh page - Reload the application

---

## Getting Help

If you encounter issues:
1. Check the Troubleshooting section above
2. Verify all prerequisites are met
3. Try restarting the application
4. Ensure your Yahoo app password is valid

---

**Document Version:** 1.0
**Last Updated:** 2024
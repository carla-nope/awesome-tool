# Yahoo Mail Cleanup Agent - Specification

## Project Overview
- **Project Name**: Yahoo Mail Cleanup Agent
- **Type**: Web-based email management tool
- **Core Functionality**: Help users search, review, extract data, unsubscribe, and delete emails from Yahoo Mail
- **Target Users**: Yahoo Mail users who want to clean up their inbox efficiently

## Technical Stack
- **Backend**: Python with Flask
- **Email Access**: IMAP (Yahoo Mail)
- **Frontend**: HTML/Tailwind CSS with vanilla JavaScript
- **HTTP Client**: requests library (for visiting unsubscribe URLs)
- **HTML Parser**: BeautifulSoup (for extracting unsubscribe links)

## Functionality Specification

### 1. Authentication & Connection
- Connect to Yahoo Mail using IMAP
- Store credentials securely (environment variables)
- Support application-specific passwords
- Connection status indicator

### 2. Email Search & Browse
- Search emails by:
  - Sender (From field)
  - Subject keywords
  - Date range (start/end date)
  - Full-text search
- Display results with pagination (20 emails per page)
- Show email preview (sender, subject, date, snippet)
- Sort options (date, sender, subject)

### 3. Email Review & Details
- View full email content
- Display email metadata (from, to, date, subject, headers)
- Show extracted links and URLs
- Identify unsubscribe links automatically
- Highlight marketing/bulk emails

### 4. Data Extraction
- Extract all URLs from emails
- Detect and highlight unsubscribe links
- Extract sender domain statistics
- Identify email categories (promotional, transactional, social, etc.)

### 5. Unsubscribe Management (ENHANCED - True Unsubscribe)
- List detected unsubscribe links
- **NEW: Visit unsubscribe URL to complete opt-out at sender's server**
- One-click unsubscribe action
- Track unsubscribe status
- Option to open unsubscribe page in browser
- **NEW: Full Unsubscribe workflow:**
  - Extract unsubscribe URL from email body
  - Visit URL via HTTP to complete mailing list opt-out
  - Delete all emails from that sender
  - Report success/failure status

### 6. Email Deletion
- Select multiple emails for deletion
- Confirm before deletion
- Move to trash or permanent delete
- Bulk delete by sender or date range
- Undo capability (Yahoo trash)

### 7. Statistics Dashboard
- Total emails count
- Unread emails count
- Emails by category breakdown
- Top senders
- Cleanup suggestions

### 8. AI Triage Mode (NEW)
A powerful batch-processing workflow that leverages AI for intelligent email categorization:

**Workflow:**
1. Extract batches of emails (configurable size, 5-50)
2. Emails are formatted as readable text for AI analysis
3. Copy formatted batch to Chat/Minimax with system prompt
4. AI analyzes and returns Markdown table with:
   - Urgency (High/Medium/Low/None)
   - Category (Action Required, Newsletter, Reference, Junk, Urgent)
   - Suggested Action (Delete, Unsubscribe, Move to Folder, Archive)
   - Reasoning
5. User reviews and approves ("Approved. Generate JSON execution block")
6. AI outputs JSON commands that tool can execute
7. Paste JSON into app and execute with confirmation

**System Prompt Features:**
- Pre-configured triage instructions
- Folder organization awareness (Action, Archive, Newsletters, Reference, Urgent)
- Human-in-the-loop safety (requires explicit approval)
- Grant manager context (hyper-vigilant for grant recovery emails)
- JSON command output format for automation

**API Endpoints for Triage:**
```
GET  /api/triage/batch        - Export batch formatted for AI analysis
POST /api/triage/execute     - Execute JSON commands from AI
GET  /api/triage/system-prompt - Get triage system prompt

## UI Design

### Color Palette
- Primary: Blue (#3B82F6)
- Secondary: Gray (#6B7280)
- Accent: Red (#EF4444 for delete actions)
- Background: White (#FFFFFF)
- Text: Dark (#1F2937)

### Layout
- Sidebar navigation
- Main content area
- Email list panel (left)
- Email detail panel (right)
- Modal dialogs for confirmations

### Typography
- Font: Inter/System font stack
- Headings: Bold, 1.25-2rem
- Body: Regular, 14-16px

## API Endpoints

### Core Endpoints
```
POST /api/connect          - Connect to Yahoo Mail
GET  /api/status           - Check connection status
POST /api/search           - Search emails
GET  /api/emails           - Get email list
GET  /api/email/<id>       - Get email details
POST /api/delete           - Delete selected emails
POST /api/unsubscribe      - Unsubscribe from sender (delete all emails)
GET  /api/stats            - Get email statistics
POST /api/disconnect       - Disconnect from Yahoo Mail
```

### True Unsubscribe Endpoints (NEW)
```
POST /api/unsubscribe/find-url  - Extract unsubscribe URL from email
POST /api/unsubscribe/visit    - Visit unsubscribe URL via HTTP
POST /api/unsubscribe/full     - Full unsubscribe workflow (URL + delete)
```

### AI Triage Endpoints
```
GET  /api/triage/batch          - Export batch formatted for AI analysis
POST /api/triage/execute       - Execute JSON commands from AI
GET  /api/triage/system-prompt - Get triage system prompt
```

## Data Flow

### Standard Mode
1. User enters Yahoo email and app password
2. Backend establishes IMAP connection
3. User searches/browses emails
4. System extracts unsubscribe links and categorizes
5. User selects emails to delete or actions to take
6. System performs actions via IMAP

### True Unsubscribe Workflow (NEW)
```
1. User views email with unsubscribe link
2. Clicks "Full Unsubscribe" button
3. System extracts unsubscribe URL from email body
4. System visits unsubscribe URL via HTTP
5. System deletes ALL emails from that sender
6. System reports success/failure status
7. Future emails from this sender will STOP
```

### AI Triage Mode
1. Extract batch of emails (configurable count)
2. Format emails as readable text for AI
3. Copy to AI chat with system prompt
4. AI analyzes and outputs Markdown table
5. User reviews and approves
6. AI outputs JSON commands
7. Execute JSON commands via API

## Edge Cases
- Invalid credentials handling
- Connection timeout handling
- Large mailbox performance (pagination limits)
- Rate limiting from Yahoo
- Missing unsubscribe links
- Encrypted/multipart email handling
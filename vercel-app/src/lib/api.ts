const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

export async function connectToYahoo(email: string, password: string) {
  const response = await fetch(`${API_BASE}/api/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  return response.json();
}

export async function checkStatus() {
  const response = await fetch(`${API_BASE}/api/status`);
  return response.json();
}

export async function disconnect() {
  const response = await fetch(`${API_BASE}/api/disconnect`, { method: 'POST' });
  return response.json();
}

export async function searchEmails(params: {
  query?: string;
  sender?: string;
  subject?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  per_page?: number;
}) {
  const response = await fetch(`${API_BASE}/api/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  return response.json();
}

export async function getEmail(id: string) {
  const response = await fetch(`${API_BASE}/api/email/${id}`);
  return response.json();
}

export async function deleteEmails(emailIds: string[], permanent: boolean = false) {
  const response = await fetch(`${API_BASE}/api/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email_ids: emailIds, permanent }),
  });
  return response.json();
}

export async function unsubscribe(sender: string) {
  const response = await fetch(`${API_BASE}/api/unsubscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sender }),
  });
  return response.json();
}

export async function getStats() {
  const response = await fetch(`${API_BASE}/api/stats`);
  return response.json();
}

// True Unsubscribe
export async function findUnsubscribeUrl(emailId: string) {
  const response = await fetch(`${API_BASE}/api/unsubscribe/find-url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email_id: emailId }),
  });
  return response.json();
}

export async function visitUnsubscribeUrl(url: string, emailId: string) {
  const response = await fetch(`${API_BASE}/api/unsubscribe/visit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, email_id: emailId }),
  });
  return response.json();
}

export async function fullUnsubscribe(sender: string, emailId: string, unsubscribeUrl?: string) {
  const response = await fetch(`${API_BASE}/api/unsubscribe/full`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sender, email_id: emailId, unsubscribe_url: unsubscribeUrl }),
  });
  return response.json();
}

// AI Triage
export async function getTriageBatch(start: number = 0, limit: number = 20) {
  const response = await fetch(`${API_BASE}/api/triage/batch?start=${start}&limit=${limit}`);
  return response.json();
}

export async function executeTriageCommands(commands: any[]) {
  const response = await fetch(`${API_BASE}/api/triage/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ commands }),
  });
  return response.json();
}

export async function getSystemPrompt() {
  const response = await fetch(`${API_BASE}/api/triage/system-prompt`);
  return response.json();
}

export { API_BASE };
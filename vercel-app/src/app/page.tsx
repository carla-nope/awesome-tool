'use client';

import { useState, useEffect } from 'react';
import * as api from '@/lib/api';

interface Email {
  id: string;
  subject: string;
  sender: string;
  date: string;
  snippet: string;
  has_unsubscribe: boolean;
  unsubscribe_links: string[];
  body?: string;
  urls?: string[];
  category?: string;
}

interface Stats {
  total_emails: number;
  unread_count: number;
  categories: Record<string, number>;
  top_senders: Array<{ sender: string; count: number }>;
}

export default function Home() {
  const [connected, setConnected] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [currentMode, setCurrentMode] = useState<'browse' | 'triage'>('browse');
  const [emails, setEmails] = useState<Email[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [currentEmail, setCurrentEmail] = useState<Email | null>(null);
  const [selectedEmails, setSelectedEmails] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [currentFilter, setCurrentFilter] = useState('all');
  const [currentSearch, setCurrentSearch] = useState({});
  const [loading, setLoading] = useState(false);
  const [toasts, setToasts] = useState<Array<{ id: number; message: string; type: string }>>([]);
  const [confirmModal, setConfirmModal] = useState<{ show: boolean; title: string; message: string; callback?: () => void }>({ show: false, title: '', message: '' });

  // Triage state
  const [batchText, setBatchText] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [commandsInput, setCommandsInput] = useState('');

  useEffect(() => {
    checkConnection();
  }, []);

  const showToast = (message: string, type: 'info' | 'success' | 'error' = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3000);
  };

  const checkConnection = async () => {
    try {
      const result = await api.checkStatus();
      if (result.connected) {
        setConnected(true);
        setEmail(result.email);
        loadEmails();
        loadStats();
      }
    } catch (e) {
      // Not connected
    }
  };

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    try {
      const result = await api.connectToYahoo(email, password);
      if (result.success) {
        setConnected(true);
        setEmail(result.email);
        loadEmails();
        loadStats();
      } else {
        setLoginError(result.error || 'Connection failed');
      }
    } catch (e) {
      setLoginError('Connection failed. Please try again.');
    }
  };

  const handleDisconnect = () => {
    setConfirmModal({
      show: true,
      title: 'Disconnect',
      message: 'Are you sure you want to disconnect?',
      callback: async () => {
        await api.disconnect();
        setConnected(false);
        setEmail('');
        setPassword('');
      }
    });
  };

  const loadEmails = async () => {
    setLoading(true);
    try {
      let result;
      if (Object.keys(currentSearch).length > 0) {
        result = await api.searchEmails({ ...currentSearch, page: currentPage });
      } else {
        result = await api.searchEmails({ page: currentPage });
      }
      setEmails(result.emails || []);
      setTotalPages(result.pages || 1);
    } catch (e) {
      showToast('Failed to load emails', 'error');
    }
    setLoading(false);
  };

  const loadStats = async () => {
    try {
      const result = await api.getStats();
      setStats(result);
    } catch (e) {
      console.error('Failed to load stats');
    }
  };

  const toggleSelection = (id: string) => {
    const newSelected = new Set(selectedEmails);
    if (newSelected.has(id)) newSelected.delete(id);
    else newSelected.add(id);
    setSelectedEmails(newSelected);
  };

  const viewEmail = async (id: string) => {
    try {
      const result = await api.getEmail(id);
      setCurrentEmail(result);
    } catch (e) {
      showToast('Failed to load email', 'error');
    }
  };

  const handleDeleteSelected = () => {
    if (selectedEmails.size === 0) return;
    setConfirmModal({
      show: true,
      title: 'Delete Emails',
      message: `Delete ${selectedEmails.size} selected email(s)?`,
      callback: async () => {
        try {
          const result = await api.deleteEmails(Array.from(selectedEmails));
          if (result.success) {
            showToast(`${result.deleted} email(s) deleted`, 'success');
            setSelectedEmails(new Set());
            loadEmails();
            loadStats();
          }
        } catch (e) {
          showToast('Delete failed', 'error');
        }
      }
    });
  };

  const handleFullUnsubscribe = (sender: string, emailId: string) => {
    setConfirmModal({
      show: true,
      title: 'Full Unsubscribe',
      message: `This will:\n1. Visit the unsubscribe URL from this email\n2. Delete ALL emails from ${sender.split('<')[0].trim()}\n\nContinue?`,
      callback: async () => {
        try {
          const result = await api.fullUnsubscribe(sender, emailId);
          if (result.success) {
            const r = result.result;
            let message = `Emails deleted: ${r.emails_deleted}`;
            if (r.unsubscribe_attempted) {
              message += `\nUnsubscribe URL: ${r.unsubscribe_success ? 'SUCCESS' : 'visited (check manually)'}`;
            }
            showToast(message, r.unsubscribe_success ? 'success' : 'info');
            setCurrentEmail(null);
            loadEmails();
            loadStats();
          }
        } catch (e) {
          showToast('Unsubscribe failed', 'error');
        }
      }
    });
  };

  const extractBatch = async () => {
    setLoading(true);
    try {
      const result = await api.getTriageBatch(0, 20);
      if (result.success) {
        setBatchText(result.formatted_text);
        setSystemPrompt(result.system_prompt);
        showToast(`Loaded batch: ${result.batch.emails.length} emails`, 'success');
      }
    } catch (e) {
      showToast('Failed to extract batch', 'error');
    }
    setLoading(false);
  };

  const copyBatchToClipboard = () => {
    navigator.clipboard.writeText(batchText).then(() => {
      showToast('Copied to clipboard!', 'success');
    });
  };

  const executeCommands = () => {
    if (!commandsInput.trim()) {
      showToast('Please paste JSON commands first', 'error');
      return;
    }
    try {
      const commands = JSON.parse(commandsInput);
      setConfirmModal({
        show: true,
        title: 'Execute Commands',
        message: `Execute ${commands.length} commands? This action cannot be undone.`,
        callback: async () => {
          try {
            const result = await api.executeTriageCommands(commands);
            showToast(`Executed ${result.successful} commands`, 'success');
            setCommandsInput('');
          } catch (e) {
            showToast('Execution failed', 'error');
          }
        }
      });
    } catch (e) {
      showToast('Invalid JSON format', 'error');
    }
  };

  const escapeHtml = (text: string) => {
    if (!text) return '';
    const div = typeof document !== 'undefined' ? document.createElement('div') : null;
    if (div) {
      div.textContent = text;
      return div.innerHTML;
    }
    return text;
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  if (!connected) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="bg-white rounded-xl shadow-2xl p-8 w-full max-w-md mx-4">
          <div className="text-center mb-6">
            <svg className="w-16 h-16 mx-auto mb-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <h1 className="text-2xl font-bold text-gray-900">Carla's Awesome Yahoo Tool that Gus is allowed to use.</h1>
            <p className="text-gray-500 mt-2">Connect your Yahoo account to get started</p>
          </div>
          <form onSubmit={handleConnect} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Yahoo Email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="yourname@yahoo.com"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">App Password</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} required placeholder="xxxxxxxxxxxxxxxx"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition" />
              <p className="text-xs text-gray-500 mt-1">
                Need an app password?
                <a href="https://login.yahoo.com/myaccount/security/comparison" target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline"> Create one here</a>
              </p>
            </div>
            {loginError && <div className="text-red-500 text-sm">{loginError}</div>}
            <button type="submit" className="w-full bg-blue-500 hover:bg-blue-600 text-white font-medium py-3 px-4 rounded-lg transition">
              Connect to Yahoo Mail
            </button>
          </form>
        </div>

        {/* Toast Container */}
        <div className="fixed bottom-4 right-4 z-50 space-y-2">
          {toasts.map(toast => (
            <div key={toast.id} className={`${toast.type === 'success' ? 'bg-green-500' : toast.type === 'error' ? 'bg-red-500' : 'bg-blue-500'} text-white px-4 py-3 rounded-lg shadow-lg`}>
              {toast.message}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-4">
            <svg className="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <h1 className="text-xl font-bold text-gray-900">Carla's Awesome Yahoo Tool</h1>
            <span className="text-sm text-gray-500">{email}</span>
          </div>
          <div className="flex items-center gap-4">
            <button onClick={() => { loadEmails(); loadStats(); }} className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition" title="Refresh">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
            <button onClick={handleDisconnect} className="px-4 py-2 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition">
              Disconnect
            </button>
          </div>
        </div>
      </header>

      {/* Stats */}
      <div className="bg-white border-b border-gray-200">
        <div className="px-6 py-4 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-4">
            <p className="text-sm text-blue-600 font-medium">Total Emails</p>
            <p className="text-2xl font-bold text-blue-700">{stats?.total_emails?.toLocaleString() || '-'}</p>
          </div>
          <div className="bg-gradient-to-br from-amber-50 to-amber-100 rounded-xl p-4">
            <p className="text-sm text-amber-600 font-medium">Unread</p>
            <p className="text-2xl font-bold text-amber-700">{stats?.unread_count?.toLocaleString() || '-'}</p>
          </div>
          <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-4">
            <p className="text-sm text-green-600 font-medium">With Unsubscribe</p>
            <p className="text-2xl font-bold text-green-700">-</p>
          </div>
          <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-4">
            <p className="text-sm text-purple-600 font-medium">Top Category</p>
            <p className="text-2xl font-bold text-purple-700">-</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="px-6 flex gap-6">
          <button onClick={() => setCurrentMode('browse')} className={`py-3 px-1 text-sm font-medium border-b-2 ${currentMode === 'browse' ? 'text-blue-600 border-blue-500' : 'text-gray-500 border-transparent'}`}>
            Browse & Delete
          </button>
          <button onClick={() => setCurrentMode('triage')} className={`py-3 px-1 text-sm font-medium border-b-2 ${currentMode === 'triage' ? 'text-blue-600 border-blue-500' : 'text-gray-500 border-transparent'}`}>
            AI Triage Mode
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex h-[calc(100vh-240px)]">
        {currentMode === 'browse' ? (
          <div className="flex-1 flex">
            {/* Email List */}
            <div className="flex-1 flex flex-col">
              {selectedEmails.size > 0 && (
                <div className="bg-blue-50 border-b border-blue-100 px-4 py-2 flex items-center justify-between">
                  <span className="text-sm text-blue-700">{selectedEmails.size} selected</span>
                  <div className="flex items-center gap-2">
                    <button onClick={handleDeleteSelected} className="px-3 py-1 text-sm text-red-700 hover:bg-red-100 rounded-lg transition">Delete Selected</button>
                    <button onClick={() => setSelectedEmails(new Set())} className="px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition">Clear</button>
                  </div>
                </div>
              )}
              <div className="flex-1 overflow-y-auto scrollbar-thin">
                {loading ? (
                  <div className="flex items-center justify-center h-32"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div></div>
                ) : emails.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                    <p className="text-lg font-medium">No emails found</p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-100">
                    {emails.map(emailItem => (
                      <div key={emailItem.id} className={`p-4 hover:bg-gray-50 cursor-pointer transition ${selectedEmails.has(emailItem.id) ? 'bg-blue-50' : ''}`} onClick={() => viewEmail(emailItem.id)}>
                        <div className="flex items-start gap-3">
                          <input type="checkbox" checked={selectedEmails.has(emailItem.id)} onChange={() => toggleSelection(emailItem.id)} onClick={e => e.stopPropagation()}
                            className="mt-1 w-4 h-4 rounded border-gray-300 text-blue-500" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium text-gray-900 truncate">{escapeHtml(emailItem.sender.split('<')[0].trim()) || 'Unknown Sender'}</span>
                              {emailItem.has_unsubscribe && <span className="px-2 py-0.5 text-xs bg-red-100 text-red-600 rounded">Unsubscribe</span>}
                            </div>
                            <p className="text-sm text-gray-700 truncate">{escapeHtml(emailItem.subject) || '(No Subject)'}</p>
                            <p className="text-xs text-gray-500 mt-1 truncate">{escapeHtml(emailItem.snippet)}</p>
                            <p className="text-xs text-gray-400 mt-1">{formatDate(emailItem.date)}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="bg-white border-t border-gray-200 px-4 py-3 flex items-center justify-between">
                <button onClick={() => { if (currentPage > 1) { setCurrentPage(p => p - 1); loadEmails(); } }} disabled={currentPage <= 1} className="px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50">Previous</button>
                <span className="text-sm text-gray-500">Page {currentPage} of {totalPages}</span>
                <button onClick={() => { if (currentPage < totalPages) { setCurrentPage(p => p + 1); loadEmails(); } }} disabled={currentPage >= totalPages} className="px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50">Next</button>
              </div>
            </div>

            {/* Email Detail Panel */}
            {currentEmail && (
              <div className="w-96 bg-white border-l border-gray-200 flex flex-col">
                <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                  <h2 className="font-semibold text-gray-900">Email Details</h2>
                  <button onClick={() => setCurrentEmail(null)} className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-4">
                  <div>
                    <h3 className="font-semibold text-gray-900 mb-2">{escapeHtml(currentEmail.subject) || '(No Subject)'}</h3>
                    <div className="space-y-1 text-sm">
                      <p><span className="text-gray-500">From:</span> {escapeHtml(currentEmail.sender)}</p>
                      <p><span className="text-gray-500">Date:</span> {formatDate(currentEmail.date)}</p>
                    </div>
                  </div>
                  {currentEmail.body && (
                    <div className="border-t border-gray-200 pt-4">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Message</h4>
                      <div className="text-sm text-gray-600 whitespace-pre-wrap break-words max-h-64 overflow-y-auto scrollbar-thin bg-gray-50 p-3 rounded">
                        {escapeHtml(currentEmail.body)}
                      </div>
                    </div>
                  )}
                  {currentEmail.unsubscribe_links && currentEmail.unsubscribe_links.length > 0 && (
                    <div className="border-t border-gray-200 pt-4">
                      <h4 className="text-sm font-medium text-red-600 mb-2">Unsubscribe Links</h4>
                      <div className="space-y-2">
                        {currentEmail.unsubscribe_links.map((link, i) => (
                          <div key={i} className="flex items-center gap-2">
                            <a href={escapeHtml(link)} target="_blank" rel="noopener noreferrer" className="block text-sm text-blue-500 hover:underline break-all flex-1">{escapeHtml(link)}</a>
                          </div>
                        ))}
                      </div>
                      <button onClick={() => handleFullUnsubscribe(currentEmail.sender, currentEmail.id)}
                        className="mt-3 w-full px-4 py-2 bg-green-500 hover:bg-green-600 text-white text-sm font-medium rounded-lg transition">
                        Full Unsubscribe (Visit URL + Delete All)
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          // AI Triage Mode
          <div className="flex-1 flex">
            {/* Triage Instructions */}
            <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
              <div className="p-4 border-b border-gray-200">
                <h2 className="font-semibold text-gray-900 mb-2">AI Triage Mode</h2>
                <p className="text-sm text-gray-500">Get batches of emails, paste to AI for analysis, then execute approved actions.</p>
              </div>
              <div className="p-4 space-y-4 flex-1 overflow-y-auto scrollbar-thin">
                <div className="bg-blue-50 rounded-lg p-4">
                  <h3 className="font-medium text-blue-900 mb-2">How it works:</h3>
                  <ol className="text-sm text-blue-800 space-y-2">
                    <li className="flex gap-2"><span className="font-bold">1.</span><span>Click "Extract Batch" to get emails formatted for AI</span></li>
                    <li className="flex gap-2"><span className="font-bold">2.</span><span>Copy the formatted text and paste to AI</span></li>
                    <li className="flex gap-2"><span className="font-bold">3.</span><span>Review the AI's analysis table</span></li>
                    <li className="flex gap-2"><span className="font-bold">4.</span><span>Type "Approved" and copy the JSON command block</span></li>
                    <li className="flex gap-2"><span className="font-bold">5.</span><span>Paste JSON below and click "Execute Commands"</span></li>
                  </ol>
                </div>
                <button onClick={extractBatch} className="w-full px-4 py-2 bg-green-500 hover:bg-green-600 text-white text-sm font-medium rounded-lg transition">
                  Extract Batch
                </button>
              </div>
            </div>

            {/* Triage Content */}
            <div className="flex-1 flex flex-col bg-gray-50">
              <div className="flex-1 p-4">
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 h-full flex flex-col">
                  <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                    <h3 className="font-semibold text-gray-900">Extracted Email Batch</h3>
                    <button onClick={copyBatchToClipboard} className="px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition">Copy to Clipboard</button>
                  </div>
                  <div className="flex-1 p-4 overflow-auto scrollbar-thin">
                    {batchText ? (
                      <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono bg-gray-50 p-4 rounded-lg">{escapeHtml(batchText)}</pre>
                    ) : (
                      <p className="text-gray-400 text-center mt-8">Click "Extract Batch" to load emails for AI analysis...</p>
                    )}
                  </div>
                </div>
              </div>
              <div className="p-4 pt-0">
                <div className="bg-white rounded-xl shadow-sm border border-gray-200">
                  <div className="p-4 border-b border-gray-200">
                    <h3 className="font-semibold text-gray-900">JSON Commands (from AI)</h3>
                  </div>
                  <div className="p-4">
                    <textarea value={commandsInput} onChange={e => setCommandsInput(e.target.value)} rows={8} placeholder='Paste JSON commands here after AI approval...'
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono resize-none" />
                    <button onClick={executeCommands} className="mt-3 w-full px-4 py-2 bg-red-500 hover:bg-red-600 text-white text-sm font-medium rounded-lg transition">
                      Execute Approved Commands
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Confirm Modal */}
      {confirmModal.show && (
        <div className="fixed inset-0 bg-gray-900/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md mx-4">
            <h2 className="text-xl font-bold text-gray-900 mb-2">{confirmModal.title}</h2>
            <p className="text-gray-600 mb-6 whitespace-pre-line">{confirmModal.message}</p>
            <div className="flex gap-3">
              <button onClick={() => setConfirmModal({ show: false, title: '', message: '' })} className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50">Cancel</button>
              <button onClick={() => { if (confirmModal.callback) confirmModal.callback(); setConfirmModal({ show: false, title: '', message: '' }); }} className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600">Confirm</button>
            </div>
          </div>
        </div>
      )}

      {/* Toast Container */}
      <div className="fixed bottom-4 right-4 z-50 space-y-2">
        {toasts.map(toast => (
          <div key={toast.id} className={`${toast.type === 'success' ? 'bg-green-500' : toast.type === 'error' ? 'bg-red-500' : 'bg-blue-500'} text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-2`}>
            <span>{toast.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
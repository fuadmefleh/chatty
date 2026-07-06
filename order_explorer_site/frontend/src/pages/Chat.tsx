import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  WS_CHAT_URL,
  getStoredApiKey,
  fetchChatSessions,
  fetchSessionMessages,
  deleteSession,
  renameSession,
  chatMediaUrl,
  uploadChatAttachment,
  type ChatSession,
  type ChatAttachment,
} from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Badge from '../components/ui/Badge';
import PulseDot from '../components/ui/PulseDot';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import MarkdownContent from '../components/ui/MarkdownContent';
import { useToast } from '../hooks/useToast';

interface Message {
  id: number;
  role: 'user' | 'assistant' | 'error' | 'system';
  content: string;
  streaming?: boolean;
  attachment?: ChatAttachment;
}

// A file the user picked but hasn't sent yet: `previewUrl` is a local object
// URL (instant preview while `uploading`); `id`/`kind`/`url` come back from
// POST /api/chatty/chat/attachments once the upload completes, and are what
// actually gets sent (as `attachment_id`) with the next message.
interface StagedAttachment {
  previewUrl: string;
  previewKind: 'image' | 'video'; // known immediately from the picked File, before upload finishes
  uploading: boolean;
  id?: string;
  kind?: 'image' | 'video';
  url?: string;
}

let msgId = 0;

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

// Backward scan, not a fixed positional offset — the array shape varies
// (a trailing system banner, error bubble, etc.) so "the last user message"
// isn't reliably `messages.length - 2`.
const getLastUserMessage = (msgs: Message[]): Message | undefined => {
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'user') return msgs[i];
  }
  return undefined;
};

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [showSessions, setShowSessions] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [activeSessionSummary, setActiveSessionSummary] = useState<string | null>(null);
  const [isEditingLast, setIsEditingLast] = useState(false);
  const [editDraft, setEditDraft] = useState('');
  const [renamingSessionId, setRenamingSessionId] = useState<number | null>(null);
  const [renameDraft, setRenameDraft] = useState('');
  const [stagedAttachment, setStagedAttachment] = useState<StagedAttachment | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pendingIdRef = useRef<number | null>(null);
  const messagesRef = useRef<Message[]>([]);
  const editDraftRef = useRef('');
  const intentionalCloseRef = useRef(false);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(RECONNECT_BASE_MS);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const clearReconnectTimer = () => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  };

  const connect = useCallback((sessionId?: number, summary?: string) => {
    // Clear any previous state
    setMessages([]);
    setActiveSessionId(sessionId ?? null);
    setActiveSessionSummary(summary ?? null);
    clearReconnectTimer();

    const apiKey = getStoredApiKey();
    const url = sessionId !== undefined
      ? `${WS_CHAT_URL}?api_key=${encodeURIComponent(apiKey)}&session_id=${sessionId}`
      : `${WS_CHAT_URL}?api_key=${encodeURIComponent(apiKey)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setConnecting(true);

    ws.onopen = () => {
      setConnected(true);
      setConnecting(false);
      intentionalCloseRef.current = false;
      backoffRef.current = RECONNECT_BASE_MS;
    };

    ws.onclose = () => {
      setConnected(false);
      setConnecting(false);
      if (!intentionalCloseRef.current) {
        const delay = backoffRef.current;
        backoffRef.current = Math.min(backoffRef.current * 2, RECONNECT_MAX_MS);
        reconnectTimerRef.current = setTimeout(() => {
          connect(sessionId, summary);
        }, delay);
      }
    };

    ws.onerror = () => {
      setConnected(false);
      setConnecting(false);
      showToast('Chat connection error — check your link.', 'red');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'session_loaded') {
          // Session context loaded — fetch and display its messages
          if (data.session_id !== null && data.message_count > 0) {
            loadSessionMessages(data.session_id);
          }
        } else if (data.type === 'chunk') {
          setMessages((prev) => {
            if (pendingIdRef.current === null) return prev;
            return prev.map((m) =>
              m.id === pendingIdRef.current
                ? { ...m, content: m.content + data.text, streaming: true }
                : m
            );
          });
        } else if (data.type === 'done' || data.type === 'stopped') {
          // Capture-then-clear: setMessages' updater may run asynchronously
          // (React batches updates from non-React callbacks like this one), so
          // nulling the ref right after calling setMessages could beat the
          // updater to it and make it see `null`, leaving `streaming` stuck.
          const targetId = pendingIdRef.current;
          pendingIdRef.current = null;
          if (targetId !== null) {
            setMessages((prev) =>
              prev.map((m) => (m.id === targetId ? { ...m, streaming: false } : m))
            );
          }
        } else if (data.type === 'error') {
          const targetId = pendingIdRef.current;
          pendingIdRef.current = null;
          setMessages((prev) => {
            let resolved = prev;
            if (targetId !== null) {
              const pending = prev.find((m) => m.id === targetId);
              resolved = pending && pending.content === ''
                ? prev.filter((m) => m.id !== targetId)
                : prev.map((m) => (m.id === targetId ? { ...m, streaming: false } : m));
            }
            return [...resolved, { id: ++msgId, role: 'error', content: data.text, streaming: false }];
          });
        }
      } catch {
        // ignore parse errors
      }
    };

    return ws;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load session messages into chat view
  const loadSessionMessages = useCallback(async (sessionId: number) => {
    try {
      const msgs = await fetchSessionMessages(sessionId);
      const systemMsgId = ++msgId;
      const systemMsg: Message = {
        id: systemMsgId,
        role: 'system',
        content: `Session ${sessionId} loaded (${msgs.length} messages)`,
      };
      const historyMessages: Message[] = msgs.map((m) => ({
        id: ++msgId,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        streaming: false,
        attachment: m.attachment,
      }));
      setMessages([systemMsg, ...historyMessages]);
    } catch {
      // If fetch fails, just continue with empty chat
    }
  }, []);

  // Initial connection — resume the most recent session if one exists,
  // otherwise start a fresh chat.
  useEffect(() => {
    let ws: WebSocket | null = null;
    let cancelled = false;

    (async () => {
      let sessions: ChatSession[] = [];
      try {
        sessions = await fetchChatSessions();
      } catch {
        // fall through to a fresh session
      }
      if (cancelled) return;
      ws = sessions.length > 0 ? connect(sessions[0].id, sessions[0].title || sessions[0].summary) : connect();
    })();

    return () => {
      cancelled = true;
      intentionalCloseRef.current = true;
      clearReconnectTimer();
      ws?.close();
    };
  }, [connect]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, showSessions]);

  const clearStagedAttachment = useCallback(() => {
    setStagedAttachment((prev) => {
      if (prev) URL.revokeObjectURL(prev.previewUrl);
      return null;
    });
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const handleAttachFile = useCallback(async (file: File) => {
    const previewUrl = URL.createObjectURL(file);
    const previewKind: 'image' | 'video' = file.type.startsWith('video/') ? 'video' : 'image';
    setStagedAttachment({ previewUrl, previewKind, uploading: true });
    try {
      const uploaded = await uploadChatAttachment(file);
      setStagedAttachment((prev) =>
        prev && prev.previewUrl === previewUrl ? { ...prev, uploading: false, ...uploaded } : prev
      );
    } catch {
      showToast('Failed to upload attachment', 'red');
      setStagedAttachment((prev) => {
        if (prev?.previewUrl === previewUrl) URL.revokeObjectURL(previewUrl);
        return prev?.previewUrl === previewUrl ? null : prev;
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showToast]);

  const onFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleAttachFile(file);
  };

  const sendMessage = () => {
    const text = input.trim();
    const attachment = stagedAttachment?.id ? stagedAttachment : null;
    if ((!text && !attachment) || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    // Add user message
    const userId = ++msgId;
    setMessages((prev) => [
      ...prev,
      {
        id: userId,
        role: 'user',
        content: text,
        attachment: attachment ? { kind: attachment.kind!, url: attachment.url! } : undefined,
      },
    ]);

    // Add placeholder assistant message
    const assistantId = ++msgId;
    pendingIdRef.current = assistantId;
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', streaming: true },
    ]);

    wsRef.current.send(JSON.stringify({ type: 'message', text, attachment_id: attachment?.id }));
    setInput('');
    clearStagedAttachment();
  };

  const stopGeneration = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: 'stop' }));
  }, []);

  const regenerateLast = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    const prev = messagesRef.current;
    const last = prev[prev.length - 1];
    if (!last || last.role !== 'assistant' || last.streaming) return;

    const assistantId = ++msgId;
    pendingIdRef.current = assistantId;
    setMessages([
      ...prev.slice(0, -1),
      { id: assistantId, role: 'assistant', content: '', streaming: true },
    ]);
    wsRef.current.send(JSON.stringify({ type: 'regenerate' }));
  }, []);

  // Shared by both "edit last message and resend" and "retry a failed send" —
  // retry is just an edit-resend with the text left unchanged.
  const submitEditOrRetry = useCallback((newText: string) => {
    const text = newText.trim();
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    const prev = messagesRef.current;
    let lastUserIdx = -1;
    for (let i = prev.length - 1; i >= 0; i--) {
      if (prev[i].role === 'user') {
        lastUserIdx = i;
        break;
      }
    }
    if (lastUserIdx === -1) return;

    const base = prev.slice(0, lastUserIdx);
    const userId = ++msgId;
    const assistantId = ++msgId;
    pendingIdRef.current = assistantId;

    setMessages([
      ...base,
      { id: userId, role: 'user', content: text },
      { id: assistantId, role: 'assistant', content: '', streaming: true },
    ]);
    setIsEditingLast(false);
    wsRef.current.send(JSON.stringify({ type: 'edit_resend', text }));
  }, []);

  const startEdit = useCallback(() => {
    const last = getLastUserMessage(messagesRef.current);
    if (!last) return;
    editDraftRef.current = last.content;
    setEditDraft(last.content);
    setIsEditingLast(true);
  }, []);

  const cancelEdit = useCallback(() => setIsEditingLast(false), []);

  const changeEditDraft = useCallback((v: string) => {
    editDraftRef.current = v;
    setEditDraft(v);
  }, []);

  const submitEdit = useCallback(() => {
    submitEditOrRetry(editDraftRef.current);
  }, [submitEditOrRetry]);

  const retryLast = useCallback(() => {
    const last = getLastUserMessage(messagesRef.current);
    if (last) submitEditOrRetry(last.content);
  }, [submitEditOrRetry]);

  const copyMessage = useCallback((content: string) => {
    navigator.clipboard.writeText(content).then(
      () => showToast('Copied to clipboard', 'green'),
      () => showToast('Could not copy', 'red')
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // iOS Safari fires its viewport resize (for the on-screen keyboard) AFTER
  // the focus event, so we nudge the input into view once focused to avoid
  // it being hidden behind the keyboard on first tap.
  const handleInputFocus = (e: React.FocusEvent<HTMLTextAreaElement>) => {
    e.target.scrollIntoView({ block: 'end', behavior: 'smooth' });
  };

  // ── Session management ──────────────────────────────────────────────────
  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const data = await fetchChatSessions();
      setSessions(data);
    } catch {
      setSessions([]);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  const joinSession = (sessionId: number, summary: string) => {
    setShowSessions(false);
    intentionalCloseRef.current = true;
    clearReconnectTimer();
    wsRef.current?.close();
    connect(sessionId, summary);
  };

  const startNewChat = () => {
    setShowSessions(false);
    intentionalCloseRef.current = true;
    clearReconnectTimer();
    wsRef.current?.close();
    connect();
  };

  const manualReconnect = () => {
    clearReconnectTimer();
    backoffRef.current = RECONNECT_BASE_MS;
    connect(activeSessionId ?? undefined, activeSessionSummary ?? undefined);
  };

  const openSessionPicker = async () => {
    setShowSessions(true);
    await loadSessions();
  };

  const handleDeleteSession = async (sess: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Delete this session? This cannot be undone.')) return;
    try {
      await deleteSession(sess.id);
      await loadSessions();
      if (sess.id === activeSessionId) {
        startNewChat();
      }
    } catch {
      showToast('Failed to delete session', 'red');
    }
  };

  const startRenameSession = (sess: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setRenamingSessionId(sess.id);
    setRenameDraft(sess.title || sess.summary || '');
  };

  const submitRenameSession = async (sess: ChatSession) => {
    const title = renameDraft.trim();
    setRenamingSessionId(null);
    if (!title) return;
    try {
      await renameSession(sess.id, title);
      await loadSessions();
      if (sess.id === activeSessionId) {
        setActiveSessionSummary(title);
      }
    } catch {
      showToast('Failed to rename session', 'red');
    }
  };

  const formatSessionTime = (ts: string): string => {
    try {
      const d = new Date(ts);
      const now = new Date();
      const diffMs = now.getTime() - d.getTime();
      const diffMin = Math.floor(diffMs / 60000);
      const diffHr = Math.floor(diffMs / 3600000);
      const diffDay = Math.floor(diffMs / 86400000);

      if (diffMin < 1) return 'just now';
      if (diffMin < 60) return `${diffMin}m ago`;
      if (diffHr < 24) return `${diffHr}h ago`;
      if (diffDay < 7) return `${diffDay}d ago`;
      return d.toLocaleDateString();
    } catch {
      return ts;
    }
  };

  const isGenerating = messages.some((m) => m.streaming);
  const lastUserMessage = getLastUserMessage(messages);
  const trailingMessage = messages[messages.length - 1];
  const canInteract = connected && !isGenerating;

  return (
    // `h-full` fills whatever height AppShell's <main> makes available — on
    // mobile that's already (100dvh - TopBar - bottom tab bar clearance)
    // thanks to AppShell's own `min-h-dvh` + `pb-16 md:pb-0`, and on desktop
    // it's the full column height. Because it's all percentage-based off a
    // dvh root (not a hardcoded 100vh here), this reflows correctly when the
    // mobile on-screen keyboard opens/closes. Only the message list scrolls;
    // header and input bar stay put.
    <div className="relative flex h-full flex-col">
      {/* Header / session bar */}
      <div className="shrink-0 border-b border-line px-4 pt-4 md:px-6 md:pt-5">
        <PageHeader
          eyebrow="Assistant / Chat"
          title={activeSessionSummary ? `Chat — ${activeSessionSummary}` : 'Chat'}
          actions={
            <>
              <span className="inline-flex items-center gap-1.5">
                {connecting ? (
                  <Spinner size="sm" label="Connecting" />
                ) : (
                  <>
                    {connected && <PulseDot tone="signal" />}
                    <Badge tone={connected ? 'teal' : 'danger'}>
                      {connected ? 'Connected' : 'Disconnected'}
                    </Badge>
                  </>
                )}
              </span>
              {!connected && !connecting && (
                <button
                  onClick={manualReconnect}
                  className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink-dim hover:border-signal hover:text-ink"
                >
                  Reconnect
                </button>
              )}
              <button
                onClick={openSessionPicker}
                className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink-dim hover:border-signal hover:text-ink"
              >
                History
              </button>
              {activeSessionId !== null && (
                <button
                  onClick={startNewChat}
                  className="rounded-lg bg-signal px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
                >
                  + New Chat
                </button>
              )}
            </>
          }
        />
      </div>

      {/* Sessions Panel (overlay) */}
      {showSessions && (
        <div
          className="absolute inset-0 z-50 flex items-start justify-center bg-ink/40 pt-10 backdrop-blur-sm"
          onClick={() => setShowSessions(false)}
        >
          <div
            className="flex max-h-[70vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-line bg-surface"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Panel header */}
            <div className="flex items-center justify-between border-b border-line px-5 py-4">
              <div>
                <div className="font-mono text-[11px] uppercase tracking-wider text-signal">Chat History</div>
                <div className="mt-1 text-sm text-ink">
                  {sessionsLoading ? 'Loading…' : `${sessions.length} session${sessions.length !== 1 ? 's' : ''}`}
                </div>
              </div>
              <button
                onClick={() => setShowSessions(false)}
                aria-label="Close"
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg p-0 text-muted hover:bg-surface-dim hover:text-ink"
              >
                ✕
              </button>
            </div>

            {/* Session list */}
            <div className="flex-1 overflow-y-auto py-2">
              {sessionsLoading && sessions.length === 0 ? (
                <div className="flex justify-center px-6 py-10">
                  <Spinner label="Loading sessions…" />
                </div>
              ) : sessions.length === 0 ? (
                <div className="px-6 py-6">
                  <EmptyState title="No chat history yet" description="Start a conversation to see it appear here." />
                </div>
              ) : (
                sessions.map((sess) => (
                  <div key={sess.id} className="group relative w-full border-b border-line hover:bg-surface-dim">
                    {renamingSessionId === sess.id ? (
                      // Not nested inside the join <button> below — an <input> inside a
                      // <button> can have Enter bubble up and trigger the button's click.
                      <div className="px-5 py-3 pr-20">
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <span className="font-mono text-[13px] font-semibold text-signal">#{sess.id}</span>
                          <span className="whitespace-nowrap font-mono text-[11px] text-muted">
                            {formatSessionTime(sess.last_ts)} · {sess.message_count} msgs
                          </span>
                        </div>
                        <input
                          autoFocus
                          value={renameDraft}
                          onChange={(e) => setRenameDraft(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') { e.preventDefault(); submitRenameSession(sess); }
                            if (e.key === 'Escape') { e.preventDefault(); setRenamingSessionId(null); }
                          }}
                          onBlur={() => submitRenameSession(sess)}
                          className="w-full rounded border border-line bg-bg px-2 py-1 text-[13px] text-ink outline-none focus:border-signal"
                        />
                      </div>
                    ) : (
                      <button
                        onClick={() => joinSession(sess.id, sess.title || sess.summary)}
                        className="block w-full px-5 py-3 pr-20 text-left"
                      >
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <span className="font-mono text-[13px] font-semibold text-signal">#{sess.id}</span>
                          <span className="whitespace-nowrap font-mono text-[11px] text-muted">
                            {formatSessionTime(sess.last_ts)} · {sess.message_count} msgs
                          </span>
                        </div>
                        <div className="overflow-hidden text-ellipsis whitespace-nowrap text-[13px] text-ink-dim">
                          {sess.title || sess.summary || '(empty session)'}
                        </div>
                      </button>
                    )}
                    {renamingSessionId !== sess.id && (
                      <div className="absolute right-3 top-1/2 hidden -translate-y-1/2 items-center gap-1 group-hover:flex">
                        <button
                          onClick={(e) => startRenameSession(sess, e)}
                          aria-label="Rename session"
                          title="Rename"
                          className="rounded p-1 text-muted hover:bg-surface hover:text-ink"
                        >
                          ✎
                        </button>
                        <button
                          onClick={(e) => handleDeleteSession(sess, e)}
                          aria-label="Delete session"
                          title="Delete"
                          className="rounded p-1 text-muted hover:bg-surface hover:text-alert-red"
                        >
                          🗑
                        </button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Panel footer */}
            <div className="flex items-center justify-between border-t border-line px-5 py-3">
              <button
                onClick={startNewChat}
                className="rounded-lg bg-signal px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
              >
                + New Chat
              </button>
              <button
                onClick={loadSessions}
                className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink-dim hover:border-signal hover:text-ink"
              >
                ↻ Refresh
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 md:px-6">
        {messages.length === 0 ? (
          <div className="mt-16">
            <EmptyState
              title="Start a conversation with Chatty"
              description="Press Enter to send · Shift+Enter for new line"
            />
          </div>
        ) : (
          <div className="flex flex-col gap-3.5">
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                msg={msg}
                isLastUserMessage={lastUserMessage?.id === msg.id}
                isTrailing={trailingMessage?.id === msg.id}
                canEdit={canInteract}
                canRegenerate={canInteract}
                isEditingThis={isEditingLast && lastUserMessage?.id === msg.id}
                editDraft={editDraft}
                onEditDraftChange={changeEditDraft}
                onStartEdit={startEdit}
                onCancelEdit={cancelEdit}
                onSubmitEdit={submitEdit}
                onCopy={copyMessage}
                onRetry={retryLast}
                onRegenerate={regenerateLast}
              />
            ))}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-line bg-surface px-4 py-3 md:px-6">
        {stagedAttachment && (
          <div className="mb-2 flex items-center gap-2 rounded-lg border border-line bg-bg px-2 py-2">
            <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-md bg-surface-dim">
              {stagedAttachment.previewKind === 'video' ? (
                <video src={stagedAttachment.previewUrl} className="h-full w-full object-cover" muted />
              ) : (
                <img src={stagedAttachment.previewUrl} alt="Attachment preview" className="h-full w-full object-cover" />
              )}
              {stagedAttachment.uploading && (
                <div className="absolute inset-0 flex items-center justify-center bg-ink/40">
                  <Spinner size="sm" />
                </div>
              )}
            </div>
            <span className="flex-1 truncate text-xs text-ink-dim">
              {stagedAttachment.uploading
                ? 'Uploading…'
                : stagedAttachment.id
                ? `${stagedAttachment.previewKind === 'video' ? 'Video' : 'Image'} attached`
                : 'Upload failed'}
            </span>
            <button
              onClick={clearStagedAttachment}
              aria-label="Remove attachment"
              title="Remove attachment"
              className="rounded p-1 text-muted hover:bg-surface-dim hover:text-ink"
            >
              ✕
            </button>
          </div>
        )}
        <div className="flex items-end gap-2.5">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,video/*"
            onChange={onFileInputChange}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={!connected}
            title="Attach an image or video"
            aria-label="Attach an image or video"
            className="flex h-[46px] w-[46px] shrink-0 items-center justify-center rounded-lg border border-line text-ink-dim hover:border-signal hover:text-ink disabled:opacity-60"
          >
            📎
          </button>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={handleInputFocus}
            placeholder={activeSessionId !== null ? 'Continue the conversation…' : 'Message Chatty…'}
            disabled={!connected}
            rows={1}
            className="min-h-[46px] max-h-40 flex-1 resize-none rounded-lg border border-line bg-bg px-4 py-2.5 text-[14.5px] text-ink outline-none focus:border-signal disabled:opacity-60"
          />
          {isGenerating ? (
            <button
              onClick={stopGeneration}
              className="h-[46px] shrink-0 whitespace-nowrap rounded-lg bg-alert-red px-5 text-sm font-semibold text-white hover:opacity-90"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={sendMessage}
              disabled={!connected || (!input.trim() && !stagedAttachment?.id)}
              className={`h-[46px] shrink-0 whitespace-nowrap rounded-lg px-5 text-sm font-semibold ${
                connected && (input.trim() || stagedAttachment?.id)
                  ? 'bg-signal text-white hover:opacity-90'
                  : 'bg-surface-dim text-muted'
              }`}
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

interface MessageBubbleProps {
  msg: Message;
  isLastUserMessage: boolean;
  isTrailing: boolean;
  canEdit: boolean;
  canRegenerate: boolean;
  isEditingThis: boolean;
  editDraft: string;
  onEditDraftChange: (v: string) => void;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onSubmitEdit: () => void;
  onCopy: (content: string) => void;
  onRetry: () => void;
  onRegenerate: () => void;
}

const MessageBubble: React.FC<MessageBubbleProps> = React.memo(function MessageBubble({
  msg,
  isLastUserMessage,
  isTrailing,
  canEdit,
  canRegenerate,
  isEditingThis,
  editDraft,
  onEditDraftChange,
  onStartEdit,
  onCancelEdit,
  onSubmitEdit,
  onCopy,
  onRetry,
  onRegenerate,
}) {
  if (msg.role === 'system') {
    return (
      <div className="flex justify-center">
        <div className="rounded-md border border-line bg-surface-dim px-3 py-1 text-center font-mono text-[11px] text-signal">
          {msg.content}
        </div>
      </div>
    );
  }

  const showEdit = msg.role === 'user' && isLastUserMessage && canEdit;
  const showRetry = msg.role === 'error' && isTrailing;
  const showRegenerate = msg.role === 'assistant' && isTrailing && !msg.streaming && canRegenerate;

  const handleEditKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmitEdit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onCancelEdit();
    }
  };

  return (
    <div className={`group flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
      {isEditingThis ? (
        <div className="flex w-full max-w-[78%] flex-col gap-1.5">
          <textarea
            autoFocus
            value={editDraft}
            onChange={(e) => onEditDraftChange(e.target.value)}
            onKeyDown={handleEditKeyDown}
            rows={2}
            className="w-full resize-none rounded-[10px] border border-signal bg-bg px-4 py-2.5 text-[14.5px] text-ink outline-none"
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={onCancelEdit}
              className="rounded-md border border-line px-2.5 py-1 text-xs font-medium text-ink-dim hover:border-signal hover:text-ink"
            >
              Cancel
            </button>
            <button
              onClick={onSubmitEdit}
              disabled={!editDraft.trim()}
              className="rounded-md bg-signal px-2.5 py-1 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              Resend
            </button>
          </div>
        </div>
      ) : (
        <div
          className={`max-w-[78%] break-words rounded-[10px] px-4 py-2.5 text-[14.5px] leading-relaxed ${
            msg.role === 'user'
              ? 'bg-signal text-white'
              : msg.role === 'error'
              ? 'border-l-[3px] border-alert-red bg-surface-dim text-alert-red'
              : 'border-l-[3px] border-signal bg-surface-dim text-ink'
          }`}
        >
          {msg.attachment && (
            <div className="mb-2 max-w-full overflow-hidden rounded-lg">
              {msg.attachment.kind === 'video' ? (
                <video src={chatMediaUrl(msg.attachment.url)} controls className="max-h-72 max-w-full rounded-lg" />
              ) : (
                <img
                  src={chatMediaUrl(msg.attachment.url)}
                  alt="Attachment"
                  className="max-h-72 max-w-full rounded-lg object-contain"
                />
              )}
            </div>
          )}
          {msg.role === 'assistant' ? (
            <>
              {msg.content ? (
                <MarkdownContent content={msg.content} streaming={!!msg.streaming} />
              ) : (
                msg.streaming && <BlinkingCursor />
              )}
              {msg.streaming && msg.content && <BlinkingCursor />}
            </>
          ) : (
            msg.content && <span className="whitespace-pre-wrap">{msg.content}</span>
          )}
        </div>
      )}

      {!isEditingThis && (
        <div className="mt-1 flex items-center gap-3 px-1 text-[11px] text-muted opacity-0 transition-opacity group-hover:opacity-100">
          {msg.content && (
            <button onClick={() => onCopy(msg.content)} className="hover:text-ink" title="Copy">
              ⧉ Copy
            </button>
          )}
          {showEdit && (
            <button onClick={onStartEdit} className="hover:text-ink" title="Edit and resend">
              ✎ Edit
            </button>
          )}
          {showRetry && (
            <button onClick={onRetry} className="hover:text-ink" title="Retry">
              ↻ Retry
            </button>
          )}
          {showRegenerate && (
            <button onClick={onRegenerate} className="hover:text-ink" title="Regenerate response">
              ↻ Regenerate
            </button>
          )}
        </div>
      )}
    </div>
  );
});

const BlinkingCursor: React.FC = () => (
  <span className="ml-0.5 inline-block h-[1em] w-0.5 animate-pulse bg-signal align-text-bottom" />
);

export default Chat;

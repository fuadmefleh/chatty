import React, { useState, useEffect, useRef, useCallback } from 'react';
import { WS_CHAT_URL, getStoredApiKey, fetchChatSessions, fetchSessionMessages, type ChatSession } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Badge from '../components/ui/Badge';
import PulseDot from '../components/ui/PulseDot';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import { useToast } from '../hooks/useToast';

interface Message {
  id: number;
  role: 'user' | 'assistant' | 'error' | 'system';
  content: string;
  streaming?: boolean;
}

let msgId = 0;

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
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pendingIdRef = useRef<number | null>(null);
  const { showToast } = useToast();

  const connect = useCallback((sessionId?: number, summary?: string) => {
    // Clear any previous state
    setMessages([]);
    setActiveSessionId(sessionId ?? null);
    setActiveSessionSummary(summary ?? null);

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
    };

    ws.onclose = () => {
      setConnected(false);
      setConnecting(false);
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
        } else if (data.type === 'done') {
          setMessages((prev) => {
            if (pendingIdRef.current === null) return prev;
            return prev.map((m) =>
              m.id === pendingIdRef.current ? { ...m, streaming: false } : m
            );
          });
          pendingIdRef.current = null;
        } else if (data.type === 'error') {
          const errorId = ++msgId;
          setMessages((prev) => [
            ...prev,
            { id: errorId, role: 'error', content: data.text, streaming: false },
          ]);
          pendingIdRef.current = null;
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
      ws = sessions.length > 0 ? connect(sessions[0].id, sessions[0].summary) : connect();
    })();

    return () => {
      cancelled = true;
      ws?.close();
    };
  }, [connect]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, showSessions]);

  const sendMessage = () => {
    const text = input.trim();
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    // Add user message
    const userId = ++msgId;
    setMessages((prev) => [...prev, { id: userId, role: 'user', content: text }]);

    // Add placeholder assistant message
    const assistantId = ++msgId;
    pendingIdRef.current = assistantId;
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', streaming: true },
    ]);

    wsRef.current.send(JSON.stringify({ message: text }));
    setInput('');
  };

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
    wsRef.current?.close();
    connect(sessionId, summary);
  };

  const startNewChat = () => {
    setShowSessions(false);
    wsRef.current?.close();
    connect();
  };

  const openSessionPicker = async () => {
    setShowSessions(true);
    await loadSessions();
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
                  onClick={() => connect()}
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
                  <button
                    key={sess.id}
                    onClick={() => joinSession(sess.id, sess.summary)}
                    className="block w-full border-b border-line px-5 py-3 text-left hover:bg-surface-dim"
                  >
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="font-mono text-[13px] font-semibold text-signal">#{sess.id}</span>
                      <span className="whitespace-nowrap font-mono text-[11px] text-muted">
                        {formatSessionTime(sess.last_ts)} · {sess.message_count} msgs
                      </span>
                    </div>
                    <div className="overflow-hidden text-ellipsis whitespace-nowrap text-[13px] text-ink-dim">
                      {sess.summary || '(empty session)'}
                    </div>
                  </button>
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
              <div
                key={msg.id}
                className={`flex ${
                  msg.role === 'user' ? 'justify-end' : msg.role === 'system' ? 'justify-center' : 'justify-start'
                }`}
              >
                {msg.role === 'system' ? (
                  <div className="rounded-md border border-line bg-surface-dim px-3 py-1 text-center font-mono text-[11px] text-signal">
                    {msg.content}
                  </div>
                ) : (
                  <div
                    className={`max-w-[78%] whitespace-pre-wrap break-words rounded-[10px] px-4 py-2.5 text-[14.5px] leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-signal text-white'
                        : msg.role === 'error'
                        ? 'border-l-[3px] border-alert-red bg-surface-dim text-alert-red'
                        : 'border-l-[3px] border-signal bg-surface-dim text-ink'
                    }`}
                  >
                    {msg.content || (msg.streaming ? <BlinkingCursor /> : null)}
                    {msg.streaming && msg.content && <BlinkingCursor />}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex shrink-0 items-end gap-2.5 border-t border-line bg-surface px-4 py-3 md:px-6">
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
        <button
          onClick={sendMessage}
          disabled={!connected || !input.trim()}
          className={`h-[46px] shrink-0 whitespace-nowrap rounded-lg px-5 text-sm font-semibold ${
            connected && input.trim() ? 'bg-signal text-white hover:opacity-90' : 'bg-surface-dim text-muted'
          }`}
        >
          Send
        </button>
      </div>
    </div>
  );
};

const BlinkingCursor: React.FC = () => (
  <span className="ml-0.5 inline-block h-[1em] w-0.5 animate-pulse bg-signal align-text-bottom" />
);

export default Chat;

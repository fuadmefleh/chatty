import React, { useState, useEffect, useRef, useCallback } from 'react';
import { WS_CHAT_URL, getStoredApiKey, fetchChatSessions, fetchSessionMessages, type ChatSession } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';

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

  const statusColor = connected ? 'var(--success)' : connecting ? 'var(--stamp-gold)' : 'var(--danger)';
  const statusLabel = connected ? 'Connected' : connecting ? 'Connecting…' : 'Disconnected';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', maxWidth: 880, margin: '0 auto', padding: '0 24px', position: 'relative' }}>
      <div style={{ paddingTop: 24 }}>
        <PageHeader
          eyebrow="Assistant / Chat"
          eyebrowColor="var(--stamp-teal)"
          title={activeSessionSummary ? `Chat — ${activeSessionSummary}` : 'Chat'}
          actions={
            <>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontFamily: 'var(--font-mono)', fontSize: 12, color: statusColor }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: statusColor, boxShadow: connected ? `0 0 6px ${statusColor}` : 'none' }} />
                {statusLabel}
              </span>
              {!connected && !connecting && (
                <button onClick={() => connect()} style={{ fontSize: 12, padding: '4px 12px' }}>
                  Reconnect
                </button>
              )}
              <button
                onClick={openSessionPicker}
                style={{
                  fontSize: 12,
                  padding: '4px 12px',
                  background: 'var(--ink-800)',
                  border: '1px solid var(--ink-600)',
                  borderRadius: 6,
                  color: 'var(--paper)',
                  cursor: 'pointer',
                }}
              >
                📋 History
              </button>
              {activeSessionId !== null && (
                <button
                  onClick={startNewChat}
                  style={{
                    fontSize: 12,
                    padding: '4px 12px',
                    background: 'var(--stamp-teal)',
                    border: 'none',
                    borderRadius: 6,
                    color: 'var(--ink-900)',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
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
        <div style={{
          position: 'absolute',
          top: 60,
          left: 0,
          right: 0,
          bottom: 0,
          zIndex: 50,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          paddingTop: 40,
        }} onClick={() => setShowSessions(false)}>
          <div
            style={{
              width: '100%',
              maxWidth: 600,
              maxHeight: '70vh',
              background: 'var(--ink-900)',
              border: '1px solid var(--ink-700)',
              borderRadius: 12,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Panel header */}
            <div style={{
              padding: '16px 20px',
              borderBottom: '1px solid var(--ink-700)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}>
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, letterSpacing: '0.08em', color: 'var(--stamp-teal)', textTransform: 'uppercase' }}>
                  Chat History
                </div>
                <div style={{ fontSize: 14, color: 'var(--paper)', marginTop: 4 }}>
                  {sessionsLoading ? 'Loading…' : `${sessions.length} session${sessions.length !== 1 ? 's' : ''}`}
                </div>
              </div>
              <button
                onClick={() => setShowSessions(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--muted)',
                  fontSize: 20,
                  cursor: 'pointer',
                  padding: '0 4px',
                }}
              >
                ✕
              </button>
            </div>

            {/* Session list */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
              {sessionsLoading && sessions.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)' }}>Loading sessions…</div>
              ) : sessions.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)', fontSize: 14 }}>
                  No chat history yet. Start a conversation!
                </div>
              ) : (
                sessions.map((sess) => (
                  <button
                    key={sess.id}
                    onClick={() => joinSession(sess.id, sess.summary)}
                    style={{
                      display: 'block',
                      width: '100%',
                      padding: '12px 20px',
                      background: 'transparent',
                      border: 'none',
                      borderBottom: '1px solid var(--ink-800)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      color: 'var(--paper)',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--ink-800)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: 'var(--stamp-teal)',
                        fontFamily: 'var(--font-mono)',
                      }}>
                        #{sess.id}
                      </span>
                      <span style={{
                        fontSize: 11,
                        color: 'var(--muted)',
                        fontFamily: 'var(--font-mono)',
                      }}>
                        {formatSessionTime(sess.last_ts)} · {sess.message_count} msgs
                      </span>
                    </div>
                    <div style={{
                      fontSize: 13,
                      color: 'var(--paper-dim)',
                      lineHeight: 1.4,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {sess.summary || '(empty session)'}
                    </div>
                  </button>
                ))
              )}
            </div>

            {/* Panel footer */}
            <div style={{
              padding: '12px 20px',
              borderTop: '1px solid var(--ink-700)',
              display: 'flex',
              justifyContent: 'space-between',
            }}>
              <button
                onClick={startNewChat}
                style={{
                  fontSize: 13,
                  padding: '8px 16px',
                  background: 'var(--stamp-teal)',
                  border: 'none',
                  borderRadius: 6,
                  color: 'var(--ink-900)',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                + New Chat
              </button>
              <button
                onClick={loadSessions}
                style={{
                  fontSize: 12,
                  padding: '6px 12px',
                  background: 'var(--ink-800)',
                  border: '1px solid var(--ink-600)',
                  borderRadius: 6,
                  color: 'var(--paper)',
                  cursor: 'pointer',
                }}
              >
                ↻ Refresh
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        padding: '4px 2px 16px',
      }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: 'var(--muted)', marginTop: 80, fontSize: 14 }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 10, color: 'var(--stamp-teal)' }}>
              — awaiting input —
            </div>
            Start a conversation with Chatty.<br />
            <span style={{ fontSize: 12 }}>Press Enter to send · Shift+Enter for new line</span>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : msg.role === 'system' ? 'center' : 'flex-start',
            }}
          >
            {msg.role === 'system' ? (
              <div style={{
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                color: 'var(--stamp-teal)',
                background: 'var(--ink-800)',
                border: '1px solid var(--ink-700)',
                borderRadius: 6,
                padding: '4px 12px',
                textAlign: 'center',
              }}>
                {msg.content}
              </div>
            ) : (
              <div style={{
                maxWidth: '78%',
                padding: '11px 16px',
                borderRadius: 10,
                background: msg.role === 'user' ? 'var(--ink-700)' : 'var(--ink-800)',
                borderLeft: msg.role === 'assistant' ? '3px solid var(--stamp-teal)' : msg.role === 'error' ? '3px solid var(--danger)' : 'none',
                color: msg.role === 'error' ? 'var(--danger)' : 'var(--paper)',
                fontSize: 14.5,
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}>
                {msg.content || (msg.streaming ? <BlinkingCursor /> : null)}
                {msg.streaming && msg.content && <BlinkingCursor />}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '10px 0 20px', display: 'flex', gap: 10, alignItems: 'flex-end' }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={activeSessionId !== null ? 'Continue the conversation…' : 'Message Chatty…'}
          disabled={!connected}
          rows={1}
          style={{
            flex: 1,
            padding: '11px 16px',
            borderRadius: 8,
            border: '1px solid var(--ink-600)',
            fontSize: 14.5,
            resize: 'none',
            outline: 'none',
            fontFamily: 'inherit',
            background: connected ? 'var(--ink-800)' : 'var(--ink-900)',
            color: 'var(--paper)',
            boxSizing: 'border-box',
            minHeight: 46,
            maxHeight: 160,
            overflowY: 'auto',
          }}
        />
        <button
          onClick={sendMessage}
          disabled={!connected || !input.trim()}
          style={{
            padding: '11px 22px',
            borderRadius: 8,
            border: 'none',
            background: connected && input.trim() ? 'var(--stamp-teal)' : 'var(--ink-700)',
            color: connected && input.trim() ? 'var(--ink-900)' : 'var(--muted)',
            fontWeight: 700,
            fontSize: 14,
            height: 46,
            whiteSpace: 'nowrap',
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
};

const BlinkingCursor: React.FC = () => (
  <span style={{
    display: 'inline-block',
    width: 2,
    height: '1em',
    background: 'var(--stamp-teal)',
    marginLeft: 2,
    verticalAlign: 'text-bottom',
    animation: 'blink 1s step-end infinite',
  }} />
);

// Inject blink keyframe once
if (typeof document !== 'undefined' && !document.getElementById('chatty-blink-style')) {
  const style = document.createElement('style');
  style.id = 'chatty-blink-style';
  style.textContent = '@keyframes blink { 50% { opacity: 0 } }';
  document.head.appendChild(style);
}

export default Chat;

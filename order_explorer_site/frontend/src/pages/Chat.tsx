import React, { useState, useEffect, useRef, useCallback } from 'react';
import { WS_CHAT_URL, getStoredApiKey } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';

interface Message {
  id: number;
  role: 'user' | 'assistant' | 'error';
  content: string;
  streaming?: boolean;
}

let msgId = 0;

const Chat: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pendingIdRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    const apiKey = getStoredApiKey();
    const ws = new WebSocket(`${WS_CHAT_URL}?api_key=${encodeURIComponent(apiKey)}`);
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

        if (data.type === 'chunk') {
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

  useEffect(() => {
    const ws = connect();
    return () => ws.close();
  }, [connect]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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

  const statusColor = connected ? 'var(--success)' : connecting ? 'var(--stamp-gold)' : 'var(--danger)';
  const statusLabel = connected ? 'Connected' : connecting ? 'Connecting…' : 'Disconnected';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', maxWidth: 880, margin: '0 auto', padding: '0 24px' }}>
      <div style={{ paddingTop: 24 }}>
        <PageHeader
          eyebrow="Assistant / Chat"
          eyebrowColor="var(--stamp-teal)"
          title="Chat"
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
            </>
          }
        />
      </div>

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
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
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
          placeholder="Message Chatty…"
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

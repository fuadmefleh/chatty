import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  fetchFeatureRequests,
  createFeatureRequest,
  deleteFeatureRequest,
} from '../chattyApi';
import type { FeatureRequest, FeatureRequestStatus } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

const POLL_MS = 3000;

const statusColor: Record<FeatureRequestStatus, string> = {
  queued: 'var(--muted)',
  running: 'var(--stamp-teal)',
  completed: 'var(--success)',
  error: 'var(--danger)',
};

const StatusBadge: React.FC<{ status: FeatureRequestStatus }> = ({ status }) => {
  const color = statusColor[status];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
      textTransform: 'uppercase', letterSpacing: '0.05em', color,
      padding: '3px 10px', borderRadius: 20,
      background: status === 'queued' ? 'var(--ink-700)' : `${color}26`,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%', background: color,
        boxShadow: status === 'running' ? `0 0 6px ${color}` : 'none',
      }} />
      {status}
    </span>
  );
};

const Requests: React.FC = () => {
  const [requests, setRequests] = useState<FeatureRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [prompt, setPrompt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchFeatureRequests();
      setRequests(data);
      setError('');
    } catch {
      setError('Failed to load requests');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Poll while anything is queued/running; stop once everything has settled.
  useEffect(() => {
    const pending = requests.some((r) => r.status === 'queued' || r.status === 'running');

    if (pending && !pollRef.current) {
      pollRef.current = setInterval(load, POLL_MS);
    } else if (!pending && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [requests, load]);

  const handleSubmit = async () => {
    const text = prompt.trim();
    if (!text) return;
    setSubmitting(true);
    try {
      const created = await createFeatureRequest(text);
      setRequests((prev) => [created, ...prev]);
      setPrompt('');
    } catch {
      setError('Failed to submit request');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetry = async (r: FeatureRequest) => {
    setRetryingId(r.id);
    try {
      const created = await createFeatureRequest(r.prompt);
      setRequests((prev) => [created, ...prev]);
    } catch {
      setError('Failed to retry request');
    } finally {
      setRetryingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this request?')) return;
    try {
      await deleteFeatureRequest(id);
      setRequests((prev) => prev.filter((r) => r.id !== id));
    } catch {
      setError('Failed to delete request');
    }
  };

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 24px 48px' }}>
      <PageHeader
        eyebrow="Assistant / Requests"
        eyebrowColor="var(--stamp-teal)"
        title="Feature requests"
      />
      <p style={{ fontSize: 13, color: 'var(--muted)', marginTop: -18, marginBottom: 24 }}>
        Describe a feature or fix. It's routed to the local Pi coding agent (qwen3.6-27b),
        which edits the Chatty codebase directly. Restart the affected pm2 service yourself
        once a request completes.
      </p>

      {/* Submit */}
      <Card style={{ marginBottom: 28 }}>
        <textarea
          placeholder="e.g. Add a /weather command that shows tomorrow's forecast too…"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          style={{
            width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid var(--ink-600)',
            fontSize: 14.5, resize: 'vertical', fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box',
            background: 'var(--ink-900)', color: 'var(--paper)',
          }}
          onKeyDown={(e) => { if (e.key === 'Enter' && e.metaKey) handleSubmit(); }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
          <button
            onClick={handleSubmit}
            disabled={submitting || !prompt.trim()}
            style={{
              padding: '9px 20px', borderRadius: 8, border: 'none',
              background: submitting || !prompt.trim() ? 'var(--ink-700)' : 'var(--stamp-teal)',
              color: submitting || !prompt.trim() ? 'var(--muted)' : 'var(--ink-900)',
              fontWeight: 700, fontSize: 13,
            }}
          >
            {submitting ? 'Submitting…' : 'Submit request'}
          </button>
        </div>
      </Card>

      {error && <p style={{ color: 'var(--danger)', marginBottom: 16 }}>{error}</p>}

      {loading ? (
        <p style={{ color: 'var(--muted)' }}>Loading requests…</p>
      ) : requests.length === 0 ? (
        <p style={{ color: 'var(--muted)', textAlign: 'center', marginTop: 40 }}>
          No requests yet. Describe a feature above to get started.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {requests.map((r) => (
            <Card key={r.id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 10 }}>
                <p style={{ margin: 0, fontSize: 14.5, color: 'var(--paper)', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                  {r.prompt}
                </p>
                <StatusBadge status={r.status} />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
                  {new Date(r.created_at).toLocaleString()}
                </span>
                <div style={{ display: 'flex', gap: 8 }}>
                  {r.log.length > 0 && (
                    <button onClick={() => toggleExpanded(r.id)} style={{ padding: '4px 12px', fontSize: 12 }}>
                      {expanded.has(r.id) ? 'Hide log' : 'Show log'}
                    </button>
                  )}
                  {r.status === 'error' && (
                    <button
                      onClick={() => handleRetry(r)}
                      disabled={retryingId === r.id}
                      style={{
                        padding: '4px 12px', fontSize: 12,
                        background: 'var(--stamp-teal)', color: 'var(--ink-900)', fontWeight: 700,
                        opacity: retryingId === r.id ? 0.6 : 1,
                      }}
                    >
                      {retryingId === r.id ? 'Retrying…' : 'Try again'}
                    </button>
                  )}
                  {r.status !== 'running' && (
                    <button onClick={() => handleDelete(r.id)} style={{ padding: '4px 12px', fontSize: 12, background: 'transparent', color: 'var(--danger)', border: '1px solid var(--ink-600)' }}>
                      Delete
                    </button>
                  )}
                </div>
              </div>

              {r.summary && (
                <p style={{ margin: '10px 0 0', fontSize: 13, color: r.status === 'error' ? 'var(--danger)' : 'var(--paper-dim)' }}>
                  {r.summary}
                </p>
              )}

              {r.files_changed.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                  {r.files_changed.map((f) => (
                    <span key={f} style={{
                      fontSize: 11, padding: '2px 8px', borderRadius: 6,
                      background: 'var(--ink-900)', color: 'var(--stamp-gold)', fontFamily: 'var(--font-mono)',
                    }}>
                      {f}
                    </span>
                  ))}
                </div>
              )}

              {expanded.has(r.id) && r.log.length > 0 && (
                <pre style={{
                  margin: '12px 0 0', padding: '14px', fontSize: 12, lineHeight: 1.6,
                  background: 'var(--ink-900)', color: 'var(--paper-dim)', overflowX: 'auto',
                  whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  border: '1px solid var(--ink-700)', borderRadius: 8, fontFamily: 'var(--font-mono)',
                  maxHeight: 320, overflowY: 'auto',
                }}>
                  {r.log.join('\n')}
                </pre>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default Requests;

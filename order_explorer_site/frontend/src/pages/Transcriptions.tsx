import React, { useEffect, useState } from 'react';
import { fetchTranscriptions, deleteTranscription, fetchTranscriptionAudioUrl } from '../chattyApi';
import type { ChattyTranscription } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

// Lazily fetches the audio blob (via the authenticated API client) only once
// the user asks to play it, then hands the <audio> element an object URL.
const TranscriptionAudio: React.FC<{ id: string }> = ({ id }) => {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [url]);

  if (url) {
    return <audio controls src={url} style={{ height: 32, maxWidth: 220 }} />;
  }

  const handleLoad = async () => {
    setLoading(true);
    setError(false);
    try {
      setUrl(await fetchTranscriptionAudioUrl(id));
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button onClick={handleLoad} disabled={loading} style={btnSmall('transparent', 'var(--stamp-teal)')}>
      {error ? 'Failed to load — retry' : loading ? 'Loading…' : '▶ Play audio'}
    </button>
  );
};

const Transcriptions: React.FC = () => {
  const [transcriptions, setTranscriptions] = useState<ChattyTranscription[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async (includeArchived: boolean) => {
    setLoading(true);
    try {
      const data = await fetchTranscriptions(includeArchived);
      data.sort((a, b) => b.created_at.localeCompare(a.created_at));
      setTranscriptions(data);
      setError('');
    } catch {
      setError('Failed to load transcriptions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(showArchived); }, [showArchived]);

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this transcription?')) return;
    try {
      await deleteTranscription(id);
      setTranscriptions((prev) => prev.filter((t) => t.id !== id));
    } catch {
      setError('Failed to delete transcription');
    }
  };

  return (
    <div style={{ maxWidth: 760, margin: '0 auto', padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Assistant / Transcriptions" eyebrowColor="var(--stamp-teal)" title="Transcriptions" />

      <p style={{ color: 'var(--muted)', fontSize: 13.5, marginTop: -8, marginBottom: 20, lineHeight: 1.5 }}>
        Raw transcriptions submitted from the iOS app. Chatty automatically mines each one into
        long-term memory during its heartbeat, then archives it — nothing here is manually edited.
      </p>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20, fontSize: 13.5, color: 'var(--paper)', cursor: 'pointer' }}>
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
        Show already-mined (archived) transcriptions
      </label>

      {error && <p style={{ color: 'var(--danger)', marginBottom: 16 }}>{error}</p>}
      {loading ? (
        <p style={{ color: 'var(--muted)' }}>Loading transcriptions…</p>
      ) : transcriptions.length === 0 ? (
        <p style={{ color: 'var(--muted)', textAlign: 'center', marginTop: 40 }}>
          No {showArchived ? '' : 'pending '}transcriptions yet.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {transcriptions.map((t) => (
            <Card key={t.id}>
              <p style={{ margin: '0 0 12px', fontSize: 14.5, whiteSpace: 'pre-wrap', color: 'var(--paper)', lineHeight: 1.6 }}>
                {t.content}
              </p>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
                  {new Date(t.created_at).toLocaleString()} · {t.source}
                </span>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  {t.has_audio && <TranscriptionAudio id={t.id} />}
                  <span
                    style={{
                      fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 6,
                      color: t.mined ? 'var(--stamp-teal)' : 'var(--muted)',
                      border: `1px solid ${t.mined ? 'var(--stamp-teal)' : 'var(--ink-600)'}`,
                    }}
                  >
                    {t.mined ? 'Mined' : 'Pending'}
                  </span>
                  {!t.mined && (
                    <button onClick={() => handleDelete(t.id)} style={btnSmall('transparent', 'var(--danger)')}>Delete</button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

const btnSmall = (bg: string, fg: string): React.CSSProperties => ({
  padding: '4px 12px', borderRadius: 6, border: bg === 'transparent' ? '1px solid var(--ink-600)' : 'none',
  background: bg, color: fg, fontWeight: 600,
  fontSize: 12,
});

export default Transcriptions;

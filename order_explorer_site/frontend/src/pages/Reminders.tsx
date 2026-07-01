import React, { useEffect, useState } from 'react';
import { fetchChattyReminders, deleteChattyReminder } from '../chattyApi';
import type { ChattyReminder } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

const Reminders: React.FC = () => {
  const [reminders, setReminders] = useState<ChattyReminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      setReminders(await fetchChattyReminders());
    } catch {
      setError('Failed to load reminders');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (filename: string) => {
    if (!confirm('Delete this reminder?')) return;
    try {
      await deleteChattyReminder(filename);
      setReminders((prev) => prev.filter((r) => r._file !== filename));
    } catch {
      setError('Failed to delete reminder');
    }
  };

  // Render a single field value nicely
  const renderValue = (val: unknown): string => {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'object') return JSON.stringify(val);
    return String(val);
  };

  return (
    <div style={{ maxWidth: 760, margin: '0 auto', padding: '24px 24px 48px' }}>
      <PageHeader
        eyebrow="Assistant / Reminders"
        eyebrowColor="var(--stamp-teal)"
        title="Reminders"
        actions={
          <button onClick={load} style={{ fontSize: 12, padding: '4px 12px' }}>
            Refresh
          </button>
        }
      />
      <p style={{ fontSize: 13, color: 'var(--muted)', marginTop: -18, marginBottom: 24 }}>
        Set reminders by asking Chatty in the chat.
      </p>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {loading ? (
        <p style={{ color: 'var(--muted)' }}>Loading reminders…</p>
      ) : reminders.length === 0 ? (
        <div style={{ textAlign: 'center', marginTop: 60, color: 'var(--muted)' }}>
          <p>No active reminders.</p>
          <p style={{ fontSize: 13 }}>Say "Remind me to…" in the Chat to create one.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {reminders.map((r) => {
            const { _file, ...fields } = r;
            return (
              <Card key={_file}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1 }}>
                    {Object.entries(fields).map(([k, v]) => (
                      <div key={k} style={{ marginBottom: 6 }}>
                        <span style={{ fontWeight: 600, fontSize: 12, color: 'var(--stamp-teal)', textTransform: 'capitalize', fontFamily: 'var(--font-mono)' }}>
                          {k.replace(/_/g, ' ')}:{' '}
                        </span>
                        <span style={{ fontSize: 14, color: 'var(--paper)' }}>{renderValue(v)}</span>
                      </div>
                    ))}
                    <div style={{ marginTop: 8 }}>
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>{_file}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(_file)}
                    style={{ marginLeft: 16, padding: '5px 12px', border: '1px solid var(--ink-600)', background: 'transparent', color: 'var(--danger)', fontWeight: 600, fontSize: 12, whiteSpace: 'nowrap' }}
                  >
                    Delete
                  </button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Reminders;

import React, { useEffect, useState } from 'react';
import { fetchChattyReminders, deleteChattyReminder } from '../chattyApi';
import type { ChattyReminder } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import Modal from '../components/ui/Modal';
import { useToast } from '../hooks/useToast';

const Reminders: React.FC = () => {
  const { showToast } = useToast();
  const [reminders, setReminders] = useState<ChattyReminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

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

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await deleteChattyReminder(pendingDelete);
      setReminders((prev) => prev.filter((r) => r._file !== pendingDelete));
      showToast('Reminder deleted', 'signal');
      setPendingDelete(null);
    } catch {
      setError('Failed to delete reminder');
      showToast('Failed to delete reminder', 'red');
    } finally {
      setDeleting(false);
    }
  };

  // Render a single field value nicely
  const renderValue = (val: unknown): string => {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'object') return JSON.stringify(val);
    return String(val);
  };

  return (
    <div className="mx-auto max-w-[720px] px-4 py-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / Reminders"
        eyebrowColor="var(--signal)"
        title="Reminders"
        actions={
          <button onClick={load} className="h-9 rounded-lg border border-line px-3 text-xs font-medium text-ink-dim">
            Refresh
          </button>
        }
      />
      <p className="-mt-4 mb-6 text-sm text-muted">
        Set reminders by asking Atlas in the chat.
      </p>

      {error && <p className="mb-4 text-sm text-alert-red">{error}</p>}

      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner label="Loading reminders…" />
        </div>
      ) : reminders.length === 0 ? (
        <EmptyState
          title="No active reminders"
          description={'Say "Remind me to…" in the Chat to create one.'}
        />
      ) : (
        <div className="flex flex-col gap-3">
          {reminders.map((r) => {
            const { _file, ...fields } = r;
            return (
              <Card key={_file}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    {Object.entries(fields).map(([k, v]) => (
                      <div key={k} className="mb-1.5">
                        <span className="font-mono text-xs font-semibold capitalize text-signal">
                          {k.replace(/_/g, ' ')}:{' '}
                        </span>
                        <span className="text-sm text-ink">{renderValue(v)}</span>
                      </div>
                    ))}
                    <div className="mt-2">
                      <span className="font-mono text-[11px] text-muted">{_file}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => setPendingDelete(_file)}
                    className="shrink-0 whitespace-nowrap rounded-lg border border-line px-3 py-1.5 text-xs font-semibold text-alert-red"
                  >
                    Delete
                  </button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Modal open={pendingDelete !== null} onClose={() => setPendingDelete(null)} title="Delete reminder?">
        <p className="mb-4 text-sm text-ink-dim">This will permanently remove the reminder.</p>
        <div className="flex justify-end gap-2">
          <button
            onClick={() => setPendingDelete(null)}
            disabled={deleting}
            className="h-9 rounded-lg border border-line px-4 text-sm font-medium text-ink-dim"
          >
            Cancel
          </button>
          <button
            onClick={confirmDelete}
            disabled={deleting}
            className="h-9 rounded-lg bg-alert-red px-4 text-sm font-semibold text-white disabled:opacity-60"
          >
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default Reminders;

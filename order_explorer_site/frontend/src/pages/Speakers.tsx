import React, { useEffect, useState } from 'react';
import { fetchSpeakers, renameSpeaker, deleteSpeaker } from '../chattyApi';
import type { ChattySpeaker } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import Modal from '../components/ui/Modal';
import Input from '../components/ui/form/Input';
import { useToast } from '../components/ui/ToastProvider';

const Speakers: React.FC = () => {
  const { showToast } = useToast();
  const [speakers, setSpeakers] = useState<ChattySpeaker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [saving, setSaving] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setSpeakers(await fetchSpeakers());
      setError('');
    } catch {
      setError('Failed to load speakers');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const startEdit = (speaker: ChattySpeaker) => {
    setEditingId(speaker.id);
    setEditName(speaker.name);
  };

  const handleRename = async (id: string) => {
    const name = editName.trim();
    if (!name) return;
    setSaving(true);
    try {
      const updated = await renameSpeaker(id, name);
      setSpeakers((prev) => prev.map((s) => (s.id === id ? updated : s)));
      setEditingId(null);
      showToast('Speaker renamed', 'signal');
    } catch {
      setError('Failed to rename speaker');
      showToast('Failed to rename speaker', 'red');
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await deleteSpeaker(pendingDelete);
      setSpeakers((prev) => prev.filter((s) => s.id !== pendingDelete));
      showToast('Speaker removed', 'signal');
      setPendingDelete(null);
    } catch {
      setError('Failed to delete speaker');
      showToast('Failed to delete speaker', 'red');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Assistant / Speakers" eyebrowColor="var(--signal)" title="Speakers" />

      <p className="-mt-2 mb-5 text-sm leading-relaxed text-muted">
        Named voices Chatty recognizes across recordings — like tagging faces in photos. New people are
        added from the Transcriptions page by labeling a speaker in a recording; once added, their voice
        is recognized automatically in future recordings.
      </p>

      {error && <p className="mb-4 text-sm text-alert-red">{error}</p>}
      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner label="Loading speakers…" />
        </div>
      ) : speakers.length === 0 ? (
        <EmptyState
          title="No known speakers yet"
          description="Label a speaker on the Transcriptions page to add one."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {speakers.map((s) => (
            <Card key={s.id}>
              <div className="flex items-center justify-between gap-3">
                {editingId === s.id ? (
                  <Input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    autoFocus
                    className="flex-1"
                    onKeyDown={(e) => { if (e.key === 'Enter') handleRename(s.id); }}
                  />
                ) : (
                  <div className="flex items-center gap-2.5">
                    <span className="text-base font-semibold text-ink">{s.name}</span>
                    <Badge tone="teal">{s.num_samples} sample{s.num_samples === 1 ? '' : 's'}</Badge>
                  </div>
                )}
                <div className="flex shrink-0 gap-2">
                  {editingId === s.id ? (
                    <>
                      <button onClick={() => setEditingId(null)} disabled={saving} className="rounded-md px-3 py-1 text-xs font-semibold text-muted">Cancel</button>
                      <button onClick={() => handleRename(s.id)} disabled={saving} className="rounded-md bg-signal px-3 py-1 text-xs font-semibold text-white disabled:opacity-60">
                        {saving ? 'Saving…' : 'Save'}
                      </button>
                    </>
                  ) : (
                    <>
                      <button onClick={() => startEdit(s)} className="rounded-md border border-line px-3 py-1 text-xs font-semibold text-ink-dim">Rename</button>
                      <button onClick={() => setPendingDelete(s.id)} className="rounded-md px-3 py-1 text-xs font-semibold text-alert-red">Delete</button>
                    </>
                  )}
                </div>
              </div>
              <div className="mt-2 font-mono text-xs text-muted">
                Added {new Date(s.created_at).toLocaleDateString()} · updated {new Date(s.updated_at).toLocaleDateString()}
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={pendingDelete !== null} onClose={() => setPendingDelete(null)} title="Remove speaker?">
        <p className="mb-4 text-sm text-ink-dim">
          Remove this speaker from the roster? Labels already applied to past transcripts are kept — this
          only stops future matching.
        </p>
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
            {deleting ? 'Removing…' : 'Remove'}
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default Speakers;

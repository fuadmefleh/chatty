import React, { useEffect, useState, useRef } from 'react';
import {
  fetchChattyNotes,
  createChattyNote,
  updateChattyNote,
  deleteChattyNote,
} from '../chattyApi';
import type { ChattyNote } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import Modal from '../components/ui/Modal';
import { useToast } from '../hooks/useToast';

const textareaClass = 'w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-signal resize-vertical';

const Notes: React.FC = () => {
  const { showToast } = useToast();
  const [notes, setNotes] = useState<ChattyNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [newContent, setNewContent] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const load = async () => {
    setLoading(true);
    try {
      setNotes(await fetchChattyNotes());
    } catch {
      setError('Failed to load notes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    const content = newContent.trim();
    if (!content) return;
    setSaving(true);
    try {
      const note = await createChattyNote(content);
      setNotes((prev) => [note, ...prev]);
      setNewContent('');
      showToast('Note added', 'signal');
    } catch {
      setError('Failed to create note');
      showToast('Failed to create note', 'red');
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (note: ChattyNote) => {
    setEditingId(note.id);
    setEditContent(note.content);
  };

  const handleUpdate = async (id: string) => {
    const content = editContent.trim();
    if (!content) return;
    setSaving(true);
    try {
      const updated = await updateChattyNote(id, content);
      setNotes((prev) => prev.map((n) => (n.id === id ? updated : n)));
      setEditingId(null);
      showToast('Note saved', 'signal');
    } catch {
      setError('Failed to update note');
      showToast('Failed to update note', 'red');
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await deleteChattyNote(pendingDelete);
      setNotes((prev) => prev.filter((n) => n.id !== pendingDelete));
      showToast('Note deleted', 'signal');
      setPendingDelete(null);
    } catch {
      setError('Failed to delete note');
      showToast('Failed to delete note', 'red');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Assistant / Notes" eyebrowColor="var(--signal)" title="Notes" />

      {/* Create */}
      <Card className="mb-6">
        <textarea
          ref={inputRef}
          placeholder="Write a new note…"
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          rows={3}
          className={textareaClass}
          onKeyDown={(e) => { if (e.key === 'Enter' && e.metaKey) handleCreate(); }}
        />
        <div className="mt-2.5 flex justify-end">
          <button
            onClick={handleCreate}
            disabled={saving || !newContent.trim()}
            className="h-10 w-full rounded-lg bg-signal px-5 text-sm font-bold text-white disabled:bg-surface-dim disabled:text-muted sm:w-auto"
          >
            {saving ? 'Saving…' : '+ Add note'}
          </button>
        </div>
      </Card>

      {error && <p className="mb-4 text-sm text-alert-red">{error}</p>}
      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner label="Loading notes…" />
        </div>
      ) : notes.length === 0 ? (
        <EmptyState title="No notes yet" description="Create your first note above." />
      ) : (
        <div className="flex flex-col gap-3">
          {notes.map((note) => (
            <Card key={note.id}>
              {editingId === note.id ? (
                <>
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={4}
                    className={textareaClass}
                    autoFocus
                  />
                  <div className="mt-2.5 flex justify-end gap-2">
                    <button onClick={() => setEditingId(null)} className="h-9 rounded-lg border border-line px-4 text-sm font-medium text-ink-dim">Cancel</button>
                    <button onClick={() => handleUpdate(note.id)} disabled={saving} className="h-9 rounded-lg bg-signal px-4 text-sm font-bold text-white disabled:opacity-60">Save</button>
                  </div>
                </>
              ) : (
                <>
                  <p className="mb-3 whitespace-pre-wrap text-sm leading-relaxed text-ink">
                    {note.content}
                  </p>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-muted">
                      {new Date(note.created_at).toLocaleString()}
                    </span>
                    <div className="flex gap-2">
                      <button onClick={() => startEdit(note)} className="rounded-md border border-line px-3 py-1 text-xs font-semibold text-ink-dim">Edit</button>
                      <button onClick={() => setPendingDelete(note.id)} className="rounded-md border border-line px-3 py-1 text-xs font-semibold text-alert-red">Delete</button>
                    </div>
                  </div>
                </>
              )}
            </Card>
          ))}
        </div>
      )}

      <Modal open={pendingDelete !== null} onClose={() => setPendingDelete(null)} title="Delete note?">
        <p className="mb-4 text-sm text-ink-dim">This will permanently remove the note.</p>
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

export default Notes;

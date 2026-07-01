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

const Notes: React.FC = () => {
  const [notes, setNotes] = useState<ChattyNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [newContent, setNewContent] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');
  const [saving, setSaving] = useState(false);
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
    } catch {
      setError('Failed to create note');
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
    } catch {
      setError('Failed to update note');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this note?')) return;
    try {
      await deleteChattyNote(id);
      setNotes((prev) => prev.filter((n) => n.id !== id));
    } catch {
      setError('Failed to delete note');
    }
  };

  return (
    <div style={{ maxWidth: 760, margin: '0 auto', padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Assistant / Notes" eyebrowColor="var(--stamp-teal)" title="Notes" />

      {/* Create */}
      <Card style={{ marginBottom: 28 }}>
        <textarea
          ref={inputRef}
          placeholder="Write a new note…"
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          rows={3}
          style={{
            width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid var(--ink-600)',
            fontSize: 14.5, resize: 'vertical', fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box',
            background: 'var(--ink-900)', color: 'var(--paper)',
          }}
          onKeyDown={(e) => { if (e.key === 'Enter' && e.metaKey) handleCreate(); }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
          <button
            onClick={handleCreate}
            disabled={saving || !newContent.trim()}
            style={btnStyle('var(--stamp-teal)', saving || !newContent.trim())}
          >
            {saving ? 'Saving…' : '+ Add note'}
          </button>
        </div>
      </Card>

      {error && <p style={{ color: 'var(--danger)', marginBottom: 16 }}>{error}</p>}
      {loading ? (
        <p style={{ color: 'var(--muted)' }}>Loading notes…</p>
      ) : notes.length === 0 ? (
        <p style={{ color: 'var(--muted)', textAlign: 'center', marginTop: 40 }}>No notes yet. Create your first note above.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {notes.map((note) => (
            <Card key={note.id}>
              {editingId === note.id ? (
                <>
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={4}
                    style={{
                      width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid var(--ink-600)',
                      fontSize: 14.5, resize: 'vertical', fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box',
                      background: 'var(--ink-900)', color: 'var(--paper)',
                    }}
                    autoFocus
                  />
                  <div style={{ display: 'flex', gap: 8, marginTop: 10, justifyContent: 'flex-end' }}>
                    <button onClick={() => setEditingId(null)} style={btnStyle('var(--ink-700)', false)}>Cancel</button>
                    <button onClick={() => handleUpdate(note.id)} disabled={saving} style={btnStyle('var(--stamp-teal)', saving)}>Save</button>
                  </div>
                </>
              ) : (
                <>
                  <p style={{ margin: '0 0 12px', fontSize: 14.5, whiteSpace: 'pre-wrap', color: 'var(--paper)', lineHeight: 1.6 }}>
                    {note.content}
                  </p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--muted)' }}>
                      {new Date(note.created_at).toLocaleString()}
                    </span>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button onClick={() => startEdit(note)} style={btnSmall('var(--ink-700)', 'var(--paper)')}>Edit</button>
                      <button onClick={() => handleDelete(note.id)} style={btnSmall('transparent', 'var(--danger)')}>Delete</button>
                    </div>
                  </div>
                </>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

const btnStyle = (color: string, disabled: boolean): React.CSSProperties => ({
  padding: '8px 18px', borderRadius: 8, border: 'none',
  background: disabled ? 'var(--ink-700)' : color,
  color: disabled ? 'var(--muted)' : color === 'var(--ink-700)' ? 'var(--paper)' : 'var(--ink-900)',
  fontWeight: 700, fontSize: 13,
});

const btnSmall = (bg: string, fg: string): React.CSSProperties => ({
  padding: '4px 12px', borderRadius: 6, border: bg === 'transparent' ? '1px solid var(--ink-600)' : 'none',
  background: bg, color: fg, fontWeight: 600,
  fontSize: 12,
});

export default Notes;

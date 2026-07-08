import React, { useState } from 'react';
import { slugifyHeading } from '../../lib/slugifyHeading';

export interface WikiPageEditorValue {
  type: 'entity' | 'concept';
  slug: string;
  title: string;
  summary: string;
  tags: string[];
  body: string;
}

interface WikiPageEditorProps {
  mode: 'create' | 'edit';
  initial: WikiPageEditorValue;
  onSave: (value: WikiPageEditorValue) => Promise<void>;
  onCancel: () => void;
  saving?: boolean;
}

const fieldClass = 'w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-signal';
const labelClass = 'mb-1.5 block font-mono text-[11px] font-semibold uppercase tracking-wider text-muted';

/** Create/edit form for a single wiki page, reused by WikiArticle (edit an
 * existing page) and MemoryViewer (create a new one). In edit mode, type
 * and slug are fixed (the API has no rename/retype - only title/summary/
 * tags/body are mutable), so those two fields render read-only. */
const WikiPageEditor: React.FC<WikiPageEditorProps> = ({ mode, initial, onSave, onCancel, saving = false }) => {
  const [type, setType] = useState<WikiPageEditorValue['type']>(initial.type);
  const [slug, setSlug] = useState(initial.slug);
  const [slugTouched, setSlugTouched] = useState(mode === 'edit');
  const [title, setTitle] = useState(initial.title);
  const [summary, setSummary] = useState(initial.summary);
  const [tagsText, setTagsText] = useState(initial.tags.join(', '));
  const [body, setBody] = useState(initial.body);
  const [error, setError] = useState('');

  const handleTitleChange = (value: string) => {
    setTitle(value);
    if (!slugTouched) setSlug(slugifyHeading(value));
  };

  const handleSubmit = async () => {
    if (!title.trim()) {
      setError('Title is required.');
      return;
    }
    if (mode === 'create' && !slug.trim()) {
      setError('Slug is required.');
      return;
    }
    setError('');
    const tags = tagsText.split(',').map((t) => t.trim()).filter(Boolean);
    try {
      await onSave({ type, slug: slug.trim(), title: title.trim(), summary: summary.trim(), tags, body });
    } catch {
      setError(`Failed to ${mode === 'create' ? 'create' : 'save'} page.`);
    }
  };

  return (
    <div className="flex flex-col gap-3.5">
      {mode === 'create' && (
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
          <div>
            <label className={labelClass} htmlFor="wiki-editor-type">Type</label>
            <select
              id="wiki-editor-type"
              value={type}
              onChange={(e) => setType(e.target.value as WikiPageEditorValue['type'])}
              className={fieldClass}
            >
              <option value="concept">Concept</option>
              <option value="entity">Entity</option>
            </select>
          </div>
          <div>
            <label className={labelClass} htmlFor="wiki-editor-slug">Slug</label>
            <input
              id="wiki-editor-slug"
              type="text"
              value={slug}
              onChange={(e) => { setSlug(e.target.value); setSlugTouched(true); }}
              placeholder="auto-generated-from-title"
              className={`${fieldClass} font-mono`}
            />
          </div>
        </div>
      )}

      <div>
        <label className={labelClass} htmlFor="wiki-editor-title">Title</label>
        <input
          id="wiki-editor-title"
          type="text"
          value={title}
          onChange={(e) => handleTitleChange(e.target.value)}
          className={fieldClass}
          autoFocus
        />
      </div>

      <div>
        <label className={labelClass} htmlFor="wiki-editor-summary">Summary</label>
        <input
          id="wiki-editor-summary"
          type="text"
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          placeholder="One-line summary shown in the page index"
          className={fieldClass}
        />
      </div>

      <div>
        <label className={labelClass} htmlFor="wiki-editor-tags">Tags</label>
        <input
          id="wiki-editor-tags"
          type="text"
          value={tagsText}
          onChange={(e) => setTagsText(e.target.value)}
          placeholder="comma, separated, tags"
          className={fieldClass}
        />
      </div>

      <div>
        <label className={labelClass} htmlFor="wiki-editor-body">Body (Markdown)</label>
        <textarea
          id="wiki-editor-body"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={12}
          className={`${fieldClass} resize-vertical font-mono text-[13px] leading-relaxed`}
        />
      </div>

      {error && <p className="text-sm text-alert-red">{error}</p>}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="h-9 rounded-lg border border-line px-4 text-sm font-medium text-ink-dim"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={saving}
          className="h-9 rounded-lg bg-signal px-4 text-sm font-bold text-white disabled:opacity-60"
        >
          {saving ? 'Saving…' : mode === 'create' ? 'Create page' : 'Save changes'}
        </button>
      </div>
    </div>
  );
};

export default WikiPageEditor;

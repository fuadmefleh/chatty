import React, { useState } from 'react';
import { mergeWikiPages } from '../../chattyApi';
import type { WikiPage } from '../../chattyApi';

interface MergePageRef {
  type: WikiPage['type'];
  slug: string;
  title: string;
}

interface MergeConfirmPanelProps {
  pageA: MergePageRef;
  pageB: MergePageRef;
  defaultKeep: 'a' | 'b';
  onCancel: () => void;
  onMerged: (kept: WikiPage, removed: MergePageRef) => void;
}

/** Confirms and executes a merge of two wiki pages, with a toggle to flip
 * which one survives. Shared by the "Merge…" picker on WikiArticle and the
 * "Possible duplicates" panel on WikiHealth, so the direction-toggle +
 * confirm + error-handling logic only lives in one place. */
const MergeConfirmPanel: React.FC<MergeConfirmPanelProps> = ({ pageA, pageB, defaultKeep, onCancel, onMerged }) => {
  const [keepSide, setKeepSide] = useState<'a' | 'b'>(defaultKeep);
  const [merging, setMerging] = useState(false);
  const [error, setError] = useState('');

  const keep = keepSide === 'a' ? pageA : pageB;
  const remove = keepSide === 'a' ? pageB : pageA;

  const handleMerge = async () => {
    setMerging(true);
    setError('');
    try {
      const kept = await mergeWikiPages(
        { type: keep.type, slug: keep.slug },
        { type: remove.type, slug: remove.slug },
      );
      onMerged(kept, remove);
    } catch {
      setError('Failed to merge pages.');
      setMerging(false);
    }
  };

  return (
    <div className="flex flex-col gap-3.5">
      <p className="text-sm text-ink-dim">
        "{remove.title}" will be deleted; its content will be appended to "{keep.title}" under a
        "Merged from {remove.title}" heading. Links elsewhere in the wiki will be updated to point at "{keep.title}".
        This can't be undone.
      </p>
      <button
        type="button"
        onClick={() => setKeepSide(keepSide === 'a' ? 'b' : 'a')}
        disabled={merging}
        className="self-start text-xs font-semibold text-signal hover:underline disabled:opacity-60"
      >
        Merge the other way instead
      </button>

      {error && <p className="text-sm text-alert-red">{error}</p>}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={merging}
          className="h-9 rounded-lg border border-line px-4 text-sm font-medium text-ink-dim"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleMerge}
          disabled={merging}
          className="h-9 rounded-lg bg-signal px-4 text-sm font-bold text-white disabled:opacity-60"
        >
          {merging ? 'Merging…' : 'Merge'}
        </button>
      </div>
    </div>
  );
};

export default MergeConfirmPanel;

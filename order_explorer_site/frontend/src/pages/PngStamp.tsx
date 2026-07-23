import React, { useCallback, useRef, useState } from 'react';
import { stampPngOwner } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import EmptyState from '../components/ui/EmptyState';
import { useToast } from '../hooks/useToast';

type ItemStatus = 'ready' | 'working' | 'done' | 'error';

interface StampItem {
  id: string;
  file: File;
  status: ItemStatus;
  url?: string;
  downloadName?: string;
  error?: string;
}

const MAX_BYTES = 50 * 1024 * 1024;

const formatBytes = (n: number): string => {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
};

const statusStyles: Record<ItemStatus, string> = {
  ready: 'text-muted',
  working: 'text-signal',
  done: 'text-alert-amber',
  error: 'text-alert-red',
};

const PngStamp: React.FC = () => {
  const { showToast } = useToast();
  const [items, setItems] = useState<StampItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const [processing, setProcessing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((fileList: FileList | null) => {
    if (!fileList) return;
    const next: StampItem[] = [];
    for (const file of Array.from(fileList)) {
      const isPng = file.type === 'image/png' || file.name.toLowerCase().endsWith('.png');
      if (!isPng) {
        showToast(`Skipped ${file.name} — not a PNG`, 'red');
        continue;
      }
      if (file.size > MAX_BYTES) {
        showToast(`Skipped ${file.name} — over 50 MB`, 'red');
        continue;
      }
      next.push({ id: `${file.name}-${file.size}-${crypto.randomUUID()}`, file, status: 'ready' });
    }
    if (next.length) setItems((prev) => [...prev, ...next]);
  }, [showToast]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    addFiles(e.dataTransfer.files);
  };

  const removeItem = (id: string) => {
    setItems((prev) => {
      const target = prev.find((i) => i.id === id);
      if (target?.url) URL.revokeObjectURL(target.url);
      return prev.filter((i) => i.id !== id);
    });
  };

  const clearAll = () => {
    items.forEach((i) => i.url && URL.revokeObjectURL(i.url));
    setItems([]);
  };

  const stampAll = async () => {
    const pending = items.filter((i) => i.status === 'ready' || i.status === 'error');
    if (!pending.length) return;
    setProcessing(true);
    let ok = 0;
    for (const item of pending) {
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, status: 'working', error: undefined } : i)));
      try {
        const { blob, filename } = await stampPngOwner(item.file);
        const url = URL.createObjectURL(blob);
        ok += 1;
        setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, status: 'done', url, downloadName: filename } : i)));
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to stamp';
        setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, status: 'error', error: message } : i)));
      }
    }
    setProcessing(false);
    if (ok) showToast(`Stamped ${ok} image${ok === 1 ? '' : 's'}`, 'signal');
  };

  const readyCount = items.filter((i) => i.status === 'ready' || i.status === 'error').length;

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / Ownership"
        eyebrowColor="var(--signal)"
        title="PNG Owner Stamp"
        actions={items.length > 0 ? (
          <button onClick={clearAll} className="h-9 rounded-lg border border-line px-4 text-sm font-medium text-ink-dim">
            Clear all
          </button>
        ) : undefined}
      />

      <Card className="mb-6">
        <p className="text-sm leading-relaxed text-ink-dim">
          Re-encodes each PNG and writes <span className="font-semibold text-ink">Infineray LLC</span> ownership into
          its metadata:
        </p>
        <ul className="mt-2 list-inside list-disc text-sm text-ink-dim">
          <li><span className="font-mono text-xs text-ink">Copyright</span> — Copyright © {new Date().getFullYear()} Infineray LLC. All rights reserved.</li>
          <li><span className="font-mono text-xs text-ink">Author</span> — Infineray LLC</li>
        </ul>
        <p className="mt-2 text-xs text-muted">
          Pixels are unchanged. Any pre-existing metadata chunks are dropped. Original files are not modified — you download a new <span className="font-mono">_owned.png</span>.
        </p>
      </Card>

      {/* Dropzone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`mb-6 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${dragging ? 'border-signal bg-signal/5' : 'border-line hover:border-signal/60'}`}
      >
        <p className="text-sm font-semibold text-ink">Drop PNGs here or click to choose</p>
        <p className="mt-1 text-xs text-muted">Multiple files supported · up to 50 MB each</p>
        <input
          ref={inputRef}
          type="file"
          accept="image/png,.png"
          multiple
          className="hidden"
          onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }}
        />
      </div>

      {items.length === 0 ? (
        <EmptyState title="No files queued" description="Add one or more PNGs to stamp with Infineray LLC ownership." />
      ) : (
        <>
          <div className="mb-4 flex justify-end">
            <button
              onClick={stampAll}
              disabled={processing || readyCount === 0}
              className="h-10 w-full rounded-lg bg-signal px-5 text-sm font-bold text-white disabled:bg-surface-dim disabled:text-muted sm:w-auto"
            >
              {processing ? 'Stamping…' : `Stamp ${readyCount} file${readyCount === 1 ? '' : 's'}`}
            </button>
          </div>

          <div className="flex flex-col gap-3">
            {items.map((item) => (
              <Card key={item.id}>
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink">{item.file.name}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      {formatBytes(item.file.size)}
                      <span className={`ml-2 font-medium ${statusStyles[item.status]}`}>
                        {item.status === 'ready' && 'Ready'}
                        {item.status === 'working' && 'Stamping…'}
                        {item.status === 'done' && 'Stamped'}
                        {item.status === 'error' && (item.error || 'Failed')}
                      </span>
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {item.status === 'done' && item.url && (
                      <a
                        href={item.url}
                        download={item.downloadName}
                        className="rounded-md bg-alert-amber px-3 py-1.5 text-xs font-bold text-white"
                      >
                        Download
                      </a>
                    )}
                    <button
                      onClick={() => removeItem(item.id)}
                      className="rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-ink-dim"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default PngStamp;

import React, { useEffect, useState, useCallback } from 'react';
import {
  fetchWebcamSources,
  createWebcamSource,
  updateWebcamSource,
  deleteWebcamSource,
  fetchWebcamSuggestions,
  scanWebcamSuggestions,
  approveWebcamSuggestion,
  dismissWebcamSuggestion,
  deleteWebcamSuggestion,
} from '../chattyApi';
import type { WebcamSource, WebcamSuggestion, WebcamSuggestionStatus, WebcamKind } from '../chattyApi';
import { useToast } from '../hooks/useToast';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import FormField from '../components/ui/form/FormField';
import Input from '../components/ui/form/Input';
import Select from '../components/ui/form/Select';

const KINDS: WebcamKind[] = ['snapshot', 'mjpeg', 'hls', 'youtube', 'webpage'];

type SuggestionFilter = WebcamSuggestionStatus | 'all';
const FILTERS: SuggestionFilter[] = ['pending', 'approved', 'dismissed', 'all'];
const statusTone: Record<WebcamSuggestionStatus, 'gold' | 'teal' | 'neutral'> = {
  pending: 'gold',
  approved: 'teal',
  dismissed: 'neutral',
};

const emptyForm = { name: '', url: '', kind: 'webpage' as WebcamKind, location: '' };

const Webcams: React.FC = () => {
  const { showToast } = useToast();

  const [sources, setSources] = useState<WebcamSource[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [addForm, setAddForm] = useState(emptyForm);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState(emptyForm);
  const [savingId, setSavingId] = useState<string | null>(null);

  const [suggestions, setSuggestions] = useState<WebcamSuggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [filter, setFilter] = useState<SuggestionFilter>('pending');
  const [actingId, setActingId] = useState<string | null>(null);

  const loadSources = useCallback(async () => {
    try {
      setSources(await fetchWebcamSources());
    } catch {
      showToast('Failed to load webcam sources.', 'red');
    } finally {
      setSourcesLoading(false);
    }
  }, [showToast]);

  const loadSuggestions = useCallback(async () => {
    try {
      setSuggestions(await fetchWebcamSuggestions());
    } catch {
      showToast('Failed to load webcam suggestions.', 'red');
    } finally {
      setSuggestionsLoading(false);
    }
  }, [showToast]);

  useEffect(() => { loadSources(); loadSuggestions(); }, [loadSources, loadSuggestions]);

  const handleAdd = async () => {
    const name = addForm.name.trim();
    const url = addForm.url.trim();
    if (!name || !url) return;
    setAdding(true);
    try {
      const source = await createWebcamSource({ ...addForm, name, url });
      setSources((prev) => [source, ...prev]);
      setAddForm(emptyForm);
      showToast('Webcam added.', 'signal');
    } catch {
      showToast('Failed to add webcam.', 'red');
    } finally {
      setAdding(false);
    }
  };

  const startEdit = (s: WebcamSource) => {
    setEditingId(s.id);
    setEditForm({ name: s.name, url: s.url, kind: s.kind, location: s.location });
  };

  const handleSaveEdit = async (id: string) => {
    const name = editForm.name.trim();
    const url = editForm.url.trim();
    if (!name || !url) return;
    setSavingId(id);
    try {
      const updated = await updateWebcamSource(id, { ...editForm, name, url });
      setSources((prev) => prev.map((s) => (s.id === id ? updated : s)));
      setEditingId(null);
      showToast('Webcam updated.', 'signal');
    } catch {
      showToast('Failed to update webcam.', 'red');
    } finally {
      setSavingId(null);
    }
  };

  const handleToggleEnabled = async (s: WebcamSource) => {
    setSavingId(s.id);
    try {
      const updated = await updateWebcamSource(s.id, { enabled: !s.enabled });
      setSources((prev) => prev.map((x) => (x.id === s.id ? updated : x)));
    } catch {
      showToast('Failed to update webcam.', 'red');
    } finally {
      setSavingId(null);
    }
  };

  const handleDeleteSource = async (id: string) => {
    if (!confirm('Remove this webcam source?')) return;
    try {
      await deleteWebcamSource(id);
      setSources((prev) => prev.filter((s) => s.id !== id));
    } catch {
      showToast('Failed to remove webcam.', 'red');
    }
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      const data = await scanWebcamSuggestions();
      setSuggestions(data);
      showToast('Scan complete.', 'signal');
    } catch {
      showToast('Scan failed.', 'red');
    } finally {
      setScanning(false);
    }
  };

  const handleApprove = async (s: WebcamSuggestion) => {
    setActingId(s.id);
    try {
      const updated = await approveWebcamSuggestion(s.id);
      setSuggestions((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
      await loadSources();
      showToast('Added to your webcam sources.', 'green');
    } catch {
      showToast('Failed to approve suggestion.', 'red');
    } finally {
      setActingId(null);
    }
  };

  const handleDismiss = async (s: WebcamSuggestion) => {
    setActingId(s.id);
    try {
      const updated = await dismissWebcamSuggestion(s.id);
      setSuggestions((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch {
      showToast('Failed to dismiss suggestion.', 'red');
    } finally {
      setActingId(null);
    }
  };

  const handleDeleteSuggestion = async (id: string) => {
    if (!confirm('Remove this suggestion?')) return;
    try {
      await deleteWebcamSuggestion(id);
      setSuggestions((prev) => prev.filter((s) => s.id !== id));
    } catch {
      showToast('Failed to remove suggestion.', 'red');
    }
  };

  const visibleSuggestions = suggestions.filter((s) => filter === 'all' || s.status === filter);
  const pendingCount = suggestions.filter((s) => s.status === 'pending').length;

  return (
    <div className="mx-auto max-w-[860px] px-4 py-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / Webcams"
        eyebrowColor="var(--signal)"
        title="Webcam Sources"
        actions={
          <button
            type="button"
            onClick={handleScan}
            disabled={scanning}
            className={`rounded-lg px-4 py-2 text-sm font-bold ${
              scanning ? 'bg-surface-dim text-muted' : 'bg-signal text-white'
            }`}
          >
            {scanning ? <Spinner size="sm" label="Scanning…" /> : 'Scan now'}
          </button>
        }
      />
      <p className="-mt-4 mb-6 text-sm text-muted">
        Add live webcam sources yourself, or let Chatty search Reddit, forums, and the web (via
        SearXNG) for promising ones every few hours - nothing is added automatically, review and{' '}
        <strong>Approve</strong> suggestions below. Chatty can list these sources in conversation,
        but does not yet view or analyze what's showing on them.
      </p>

      <h2 className="mb-3 font-display text-lg">My Sources</h2>
      <Card className="mb-6">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FormField label="Name">
            <Input
              value={addForm.name}
              onChange={(e) => setAddForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Times Square DOT Cam"
            />
          </FormField>
          <FormField label="URL">
            <Input
              value={addForm.url}
              onChange={(e) => setAddForm((f) => ({ ...f, url: e.target.value }))}
              placeholder="https://..."
            />
          </FormField>
          <FormField label="Kind">
            <Select
              value={addForm.kind}
              onChange={(e) => setAddForm((f) => ({ ...f, kind: e.target.value as WebcamKind }))}
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Location">
            <Input
              value={addForm.location}
              onChange={(e) => setAddForm((f) => ({ ...f, location: e.target.value }))}
              placeholder="New York, NY"
            />
          </FormField>
        </div>
        <div className="mt-3 flex justify-end">
          <button
            type="button"
            onClick={handleAdd}
            disabled={adding || !addForm.name.trim() || !addForm.url.trim()}
            className="h-10 rounded-lg bg-signal px-5 text-sm font-bold text-white disabled:bg-surface-dim disabled:text-muted"
          >
            {adding ? 'Adding…' : '+ Add webcam'}
          </button>
        </div>
      </Card>

      {sourcesLoading ? (
        <Spinner label="Loading sources…" />
      ) : sources.length === 0 ? (
        <EmptyState title="No webcam sources yet" description="Add one above, or approve a suggestion below." />
      ) : (
        <div className="mb-8 flex flex-col gap-3">
          {sources.map((s) => (
            <Card key={s.id}>
              {editingId === s.id ? (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <FormField label="Name">
                    <Input value={editForm.name} onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))} />
                  </FormField>
                  <FormField label="URL">
                    <Input value={editForm.url} onChange={(e) => setEditForm((f) => ({ ...f, url: e.target.value }))} />
                  </FormField>
                  <FormField label="Kind">
                    <Select value={editForm.kind} onChange={(e) => setEditForm((f) => ({ ...f, kind: e.target.value as WebcamKind }))}>
                      {KINDS.map((k) => (
                        <option key={k} value={k}>{k}</option>
                      ))}
                    </Select>
                  </FormField>
                  <FormField label="Location">
                    <Input value={editForm.location} onChange={(e) => setEditForm((f) => ({ ...f, location: e.target.value }))} />
                  </FormField>
                  <div className="col-span-full flex justify-end gap-2">
                    <button onClick={() => setEditingId(null)} className="h-9 rounded-lg border border-line px-4 text-sm font-medium text-ink-dim">Cancel</button>
                    <button
                      onClick={() => handleSaveEdit(s.id)}
                      disabled={savingId === s.id}
                      className="h-9 rounded-lg bg-signal px-4 text-sm font-bold text-white disabled:opacity-60"
                    >
                      Save
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-4">
                  <div className="flex flex-1 gap-3">
                    {s.kind === 'snapshot' ? (
                      <img
                        src={s.url}
                        alt={s.name}
                        className="h-16 w-24 flex-shrink-0 rounded-md border border-line object-cover"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                      />
                    ) : null}
                    <div>
                      <a href={s.url} target="_blank" rel="noreferrer" className="font-semibold text-ink hover:underline">
                        {s.name}
                      </a>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5">
                        <Badge tone="teal">{s.kind}</Badge>
                        {s.location && <span className="text-xs text-muted">{s.location}</span>}
                        {s.source === 'suggestion' && <Badge tone="gold">discovered</Badge>}
                        {!s.enabled && <Badge tone="neutral">disabled</Badge>}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleToggleEnabled(s)}
                      disabled={savingId === s.id}
                      className="rounded-md border border-line px-3 py-1 text-xs font-semibold text-ink-dim disabled:opacity-60"
                    >
                      {s.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button
                      type="button"
                      onClick={() => startEdit(s)}
                      className="rounded-md border border-line px-3 py-1 text-xs font-semibold text-ink-dim"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteSource(s.id)}
                      className="rounded-md border border-line px-3 py-1 text-xs font-semibold text-alert-red"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      <h2 className="mb-3 font-display text-lg">Suggestions</h2>
      <div className="mb-5 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`rounded-md px-3 py-1 text-xs font-semibold capitalize ${
              filter === f ? 'bg-signal text-white' : 'bg-surface-dim text-ink-dim'
            }`}
          >
            {f}
            {f === 'pending' && pendingCount > 0 ? ` (${pendingCount})` : ''}
          </button>
        ))}
      </div>

      {suggestionsLoading ? (
        <Spinner label="Loading suggestions…" />
      ) : visibleSuggestions.length === 0 ? (
        <EmptyState
          title={filter === 'pending' ? 'No pending suggestions' : `No ${filter} suggestions`}
          description={
            filter === 'pending'
              ? 'Click "Scan now" to search right away, or wait for the next heartbeat cycle.'
              : undefined
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          {visibleSuggestions.map((s) => (
            <Card key={s.id}>
              <div className="mb-2.5 flex items-start justify-between gap-3">
                <div>
                  <span className="font-semibold text-ink">{s.name}</span>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <Badge tone="teal">{s.kind}</Badge>
                    {s.location && <span className="text-xs text-muted">{s.location}</span>}
                  </div>
                </div>
                <Badge tone={statusTone[s.status]}>{s.status}</Badge>
              </div>

              {s.rationale && (
                <p className="m-0 mb-2 text-sm italic leading-relaxed text-ink-dim">{s.rationale}</p>
              )}
              <a
                href={s.discovered_url}
                target="_blank"
                rel="noreferrer"
                className="mb-2 block truncate font-mono text-xs text-muted hover:underline"
              >
                found via {s.discovered_url} ↗
              </a>

              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs text-muted">
                  {new Date(s.created_at).toLocaleString()}
                </span>
                <div className="flex gap-2">
                  {s.status === 'pending' && (
                    <>
                      <button
                        type="button"
                        onClick={() => handleDismiss(s)}
                        disabled={actingId === s.id}
                        className="rounded-md border border-line bg-transparent px-3 py-1 text-xs font-semibold text-ink-dim disabled:opacity-60"
                      >
                        Dismiss
                      </button>
                      <button
                        type="button"
                        onClick={() => handleApprove(s)}
                        disabled={actingId === s.id}
                        className="rounded-md bg-signal px-3 py-1 text-xs font-bold text-white disabled:opacity-60"
                      >
                        {actingId === s.id ? 'Approving…' : 'Approve'}
                      </button>
                    </>
                  )}
                  {s.status === 'dismissed' && (
                    <button
                      type="button"
                      onClick={() => handleDeleteSuggestion(s.id)}
                      className="rounded-md border border-line bg-transparent px-3 py-1 text-xs font-semibold text-alert-red"
                    >
                      Delete
                    </button>
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

export default Webcams;

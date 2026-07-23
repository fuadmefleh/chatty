import React, { useEffect, useState } from 'react';
import {
  fetchTranscriptions, deleteTranscription, fetchTranscriptionAudioUrl,
  fetchTranscriptionSegments, fetchSpeakers, labelSpeaker, rescanSpeakers,
} from '../chattyApi';
import type { ChattyTranscription, TranscriptSegment, ChattySpeaker } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import Modal from '../components/ui/Modal';
import Checkbox from '../components/ui/form/Checkbox';
import { useToast } from '../hooks/useToast';

const btnSmallClass = (border: boolean) =>
  `whitespace-nowrap rounded-md px-3 py-1 text-xs font-semibold text-signal ${border ? 'border border-line' : ''}`;

const selectClass = 'rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink outline-none focus:border-signal';
const inputClass = 'w-[120px] rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink outline-none focus:border-signal';

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
    return <audio controls src={url} className="h-8 max-w-[220px]" />;
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
    <button onClick={handleLoad} disabled={loading} className={btnSmallClass(false)}>
      {error ? 'Failed to load — retry' : loading ? 'Loading…' : '▶ Play audio'}
    </button>
  );
};

const formatTime = (seconds: number | null): string => {
  if (seconds === null || Number.isNaN(seconds)) return '--:--';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

// Inline control for resolving one segment's generic speaker id (e.g.
// "SPEAKER_00") to a real name - either an existing roster entry or a brand
// new one, mirroring Notes.tsx's inline-edit-in-place pattern.
const SpeakerLabelControl: React.FC<{
  speakers: ChattySpeaker[];
  onSave: (opts: { name?: string; speakerId?: string }) => Promise<void>;
  onCancel: () => void;
}> = ({ speakers, onSave, onCancel }) => {
  const [speakerId, setSpeakerId] = useState('');
  const [newName, setNewName] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    const opts = speakerId ? { speakerId } : { name: newName.trim() };
    if (!opts.speakerId && !opts.name) return;
    setSaving(true);
    try {
      await onSave(opts);
    } finally {
      setSaving(false);
    }
  };

  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      {speakers.length > 0 && (
        <select
          value={speakerId}
          onChange={(e) => { setSpeakerId(e.target.value); if (e.target.value) setNewName(''); }}
          className={selectClass}
        >
          <option value="">+ New person…</option>
          {speakers.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      )}
      {!speakerId && (
        <input
          type="text"
          placeholder="Name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          autoFocus
          className={inputClass}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); }}
        />
      )}
      <button onClick={handleSave} disabled={saving || (!speakerId && !newName.trim())} className="whitespace-nowrap rounded-md bg-signal px-3 py-1 text-xs font-semibold text-white disabled:opacity-60">
        {saving ? 'Saving…' : 'Save'}
      </button>
      <button onClick={onCancel} disabled={saving} className="whitespace-nowrap rounded-md px-3 py-1 text-xs font-semibold text-muted">Cancel</button>
    </span>
  );
};

const TranscriptSegments: React.FC<{
  transcriptionId: string;
  speakers: ChattySpeaker[];
  onSpeakerLabeled: () => void;
}> = ({ transcriptionId, speakers, onSpeakerLabeled }) => {
  const [segments, setSegments] = useState<TranscriptSegment[] | null>(null);
  const [error, setError] = useState('');
  const [labelingSpeaker, setLabelingSpeaker] = useState<string | null>(null);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    fetchTranscriptionSegments(transcriptionId)
      .then(setSegments)
      .catch(() => setError('Failed to load segments'));
  }, [transcriptionId]);

  const handleSave = async (localSpeaker: string, opts: { name?: string; speakerId?: string }) => {
    const result = await labelSpeaker(transcriptionId, localSpeaker, opts);
    setSegments((prev) =>
      prev
        ? prev.map((seg) =>
            seg.local_speaker === localSpeaker ? { ...seg, speaker_name: result.speaker.name } : seg,
          )
        : prev,
    );
    setLabelingSpeaker(null);
    setNotice(
      result.also_updated_count > 0
        ? `Labeled as "${result.speaker.name}" — also updated ${result.also_updated_count} other recording(s).`
        : `Labeled as "${result.speaker.name}".`,
    );
    onSpeakerLabeled();
  };

  if (error) return <p className="text-sm text-alert-red">{error}</p>;
  if (!segments) return <p className="text-sm text-muted">Loading segments…</p>;
  if (segments.length === 0) return <p className="text-sm text-muted">No segments available.</p>;

  return (
    <div className="mt-1 flex flex-col gap-2">
      {notice && <p className="mb-1 text-xs text-signal">{notice}</p>}
      {segments.map((seg, i) => {
        const key = `${transcriptionId}-${i}`;
        const isLabeling = labelingSpeaker === seg.local_speaker;
        return (
          <div key={key} className="flex items-start gap-2.5 text-sm">
            <span className="min-w-[42px] pt-0.5 font-mono text-[11.5px] text-muted">
              {formatTime(seg.start)}
            </span>
            <div className="flex flex-1 flex-col gap-1">
              {isLabeling && seg.local_speaker ? (
                <SpeakerLabelControl
                  speakers={speakers}
                  onSave={(opts) => handleSave(seg.local_speaker!, opts)}
                  onCancel={() => setLabelingSpeaker(null)}
                />
              ) : seg.local_speaker ? (
                <button
                  onClick={() => setLabelingSpeaker(seg.local_speaker)}
                  className="self-start"
                  title={seg.speaker_name ? 'Click to relabel' : 'Click to label this speaker'}
                >
                  <Badge tone={seg.speaker_name ? 'teal' : 'neutral'}>{seg.speaker_name ?? seg.local_speaker}</Badge>
                </button>
              ) : null}
              <span className="leading-relaxed text-ink">{seg.text}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

const Transcriptions: React.FC = () => {
  const { showToast } = useToast();
  const [transcriptions, setTranscriptions] = useState<ChattyTranscription[]>([]);
  const [speakers, setSpeakers] = useState<ChattySpeaker[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [rescanning, setRescanning] = useState(false);

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

  const loadSpeakers = async () => {
    try {
      setSpeakers(await fetchSpeakers());
    } catch {
      // Roster is a nice-to-have here (drives the "existing person" dropdown) -
      // labeling still works (as "+ New person") if this fails, so don't
      // surface a blocking error for it.
    }
  };

  useEffect(() => { load(showArchived); }, [showArchived]);
  useEffect(() => { loadSpeakers(); }, []);

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await deleteTranscription(pendingDelete);
      setTranscriptions((prev) => prev.filter((t) => t.id !== pendingDelete));
      showToast('Transcription deleted', 'signal');
      setPendingDelete(null);
    } catch {
      setError('Failed to delete transcription');
      showToast('Failed to delete transcription', 'red');
    } finally {
      setDeleting(false);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // After a label action, re-sync the flat list (content strings and any
  // newly-created/updated roster entries) rather than trying to patch every
  // possibly-affected transcription's cached content by hand.
  const handleSpeakerLabeled = () => {
    load(showArchived);
    loadSpeakers();
  };

  // Labeling a speaker already re-checks every other transcript against the
  // roster automatically - this is for forcing that same sweep on demand,
  // e.g. right after loosening SPEAKER_MATCH_THRESHOLD, without needing to
  // make a throwaway label first.
  const handleRescan = async () => {
    setRescanning(true);
    try {
      const { updated_count } = await rescanSpeakers();
      showToast(
        updated_count > 0
          ? `Rescanned — matched ${updated_count} more recording(s) to known speakers.`
          : 'Rescanned — no new matches found.',
        'signal',
      );
      load(showArchived);
    } catch {
      showToast('Rescan failed', 'red');
    } finally {
      setRescanning(false);
    }
  };

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / Transcriptions"
        eyebrowColor="var(--signal)"
        title="Transcriptions"
        actions={
          <button
            onClick={handleRescan}
            disabled={rescanning}
            className="whitespace-nowrap rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-signal disabled:opacity-60"
            title="Re-check every recording's unmatched speakers against the known roster"
          >
            {rescanning ? 'Rescanning…' : '↻ Rescan unmatched'}
          </button>
        }
      />

      <p className="-mt-2 mb-5 text-sm leading-relaxed text-muted">
        Raw transcriptions submitted from the iOS app. Atlas automatically mines each one into
        long-term memory during its heartbeat, then archives it. Recordings with diarized speakers
        can be expanded to label who's who — labels apply immediately and carry over to future recordings
        of the same voice.
      </p>

      <div className="mb-5">
        <Checkbox
          id="show-archived"
          label="Show already-mined (archived) transcriptions"
          checked={showArchived}
          onChange={(e) => setShowArchived(e.target.checked)}
        />
      </div>

      {error && <p className="mb-4 text-sm text-alert-red">{error}</p>}
      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner label="Loading transcriptions…" />
        </div>
      ) : transcriptions.length === 0 ? (
        <p className="mt-10 text-center text-sm text-muted">
          No {showArchived ? '' : 'pending '}transcriptions yet.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {transcriptions.map((t) => {
            const expanded = expandedIds.has(t.id);
            return (
              <Card key={t.id}>
                <p className="mb-3 whitespace-pre-wrap text-sm leading-relaxed text-ink">
                  {t.content}
                </p>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-xs text-muted">
                    {new Date(t.created_at).toLocaleString()} · {t.source}
                  </span>
                  <div className="flex flex-wrap items-center gap-2">
                    {t.has_audio && <TranscriptionAudio id={t.id} />}
                    {t.has_segments && (
                      <button onClick={() => toggleExpand(t.id)} className={btnSmallClass(false)}>
                        {expanded ? '▲ Hide speakers' : '▼ Label speakers'}
                      </button>
                    )}
                    <Badge tone={t.mined ? 'teal' : 'neutral'}>
                      {t.mined ? 'Mined' : 'Pending'}
                    </Badge>
                    {!t.mined && (
                      <button onClick={() => setPendingDelete(t.id)} className="whitespace-nowrap rounded-md px-3 py-1 text-xs font-semibold text-alert-red">Delete</button>
                    )}
                  </div>
                </div>
                {expanded && (
                  <div className="mt-3.5 border-t border-line pt-3.5">
                    <TranscriptSegments
                      transcriptionId={t.id}
                      speakers={speakers}
                      onSpeakerLabeled={handleSpeakerLabeled}
                    />
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      <Modal open={pendingDelete !== null} onClose={() => setPendingDelete(null)} title="Delete transcription?">
        <p className="mb-4 text-sm text-ink-dim">This will permanently remove the transcription.</p>
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

export default Transcriptions;

import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  fetchVideoJobs,
  createVideoJob,
  deleteVideoJob,
  chatMediaUrl,
} from '../chattyApi';
import type { VideoJob, VideoJobStatus, VideoResolution } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import { useToast } from '../hooks/useToast';

const POLL_MS = 3000;
const VALID_DURATIONS = [2, 4, 6, 8, 10, 15];
const VALID_RESOLUTIONS: VideoResolution[] = ['480p', '720p', '1080p', 'auto'];

const statusTone: Record<VideoJobStatus, 'neutral' | 'teal' | 'gold' | 'ember'> = {
  submitted: 'neutral',
  generating: 'teal',
  completed: 'teal',
  failed: 'ember',
};

const statusLabel: Record<VideoJobStatus, string> = {
  submitted: 'Queued',
  generating: 'Generating',
  completed: 'Ready',
  failed: 'Failed',
};

const VideoProduction: React.FC = () => {
  const { showToast } = useToast();
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [prompt, setPrompt] = useState('');
  const [duration, setDuration] = useState(4);
  const [resolution, setResolution] = useState<VideoResolution>('auto');
  const [submitting, setSubmitting] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchVideoJobs();
      setJobs(data);
      setError('');
    } catch {
      setError('Failed to load video jobs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while anything is active
  const hasActive = jobs.some((j) => j.status === 'submitted' || j.status === 'generating');

  useEffect(() => {
    if (hasActive && !pollRef.current) {
      pollRef.current = setInterval(load, POLL_MS);
    } else if (!hasActive && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [hasActive, load]);

  const handleSubmit = async () => {
    const text = prompt.trim();
    if (!text) return;
    setSubmitting(true);
    try {
      const job = await createVideoJob(text, duration, resolution);
      setJobs((prev) => [job, ...prev]);
      setPrompt('');
      showToast('Video generation started', 'signal');
    } catch {
      setError('Failed to submit video job');
      showToast('Failed to submit job', 'red');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this video job?')) return;
    try {
      await deleteVideoJob(id);
      setJobs((prev) => prev.filter((j) => j.id !== id));
      showToast('Job deleted', 'signal');
    } catch {
      showToast('Failed to delete job', 'red');
    }
  };

  const formatTime = (ts: string): string => {
    try {
      const d = new Date(ts);
      const now = new Date();
      const diffMs = now.getTime() - d.getTime();
      const diffMin = Math.floor(diffMs / 60000);
      const diffHr = Math.floor(diffMs / 3600000);
      const diffDay = Math.floor(diffMs / 86400000);

      if (diffMin < 1) return 'just now';
      if (diffMin < 60) return `${diffMin}m ago`;
      if (diffHr < 24) return `${diffHr}h ago`;
      if (diffDay < 7) return `${diffDay}d ago`;
      return d.toLocaleDateString();
    } catch {
      return ts;
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="shrink-0 border-b border-line px-4 pt-4 md:px-6 md:pt-5">
        <PageHeader
          eyebrow="Assistant / Video Production"
          title="Video Production"
        />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-4 md:px-6">
        {/* Error banner */}
        {error && (
          <div className="mb-4 rounded-lg border border-alert-red bg-alert-red/10 px-4 py-2.5 text-sm text-alert-red">
            {error}
            <button onClick={() => setError('')} className="ml-2 font-bold">×</button>
          </div>
        )}

        {/* Create form */}
        <Card className="mb-6">
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-ink-dim">
                Prompt
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Describe the video you want to create…"
                rows={3}
                className="w-full resize-none rounded-lg border border-line bg-bg px-3.5 py-2.5 text-sm text-ink outline-none focus:border-signal"
              />
            </div>

            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-ink-dim">
                  Duration (seconds)
                </label>
                <select
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                  className="rounded-lg border border-line bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                >
                  {VALID_DURATIONS.map((d) => (
                    <option key={d} value={d}>
                      {d}s
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-medium text-ink-dim">
                  Resolution
                </label>
                <select
                  value={resolution}
                  onChange={(e) => setResolution(e.target.value as VideoResolution)}
                  className="rounded-lg border border-line bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-signal"
                >
                  {VALID_RESOLUTIONS.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={handleSubmit}
                disabled={submitting || !prompt.trim()}
                className="shrink-0 rounded-lg bg-signal px-5 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
              >
                {submitting ? 'Submitting…' : 'Generate Video'}
              </button>
            </div>
          </div>
        </Card>

        {/* Jobs list */}
        {loading ? (
          <div className="flex justify-center py-10">
            <Spinner label="Loading jobs…" />
          </div>
        ) : jobs.length === 0 ? (
          <EmptyState
            title="No videos yet"
            description="Use the form above to generate your first video."
          />
        ) : (
          <div className="flex flex-col gap-3">
            {jobs.map((job) => (
              <Card key={job.id} className="overflow-hidden">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge tone={statusTone[job.status]}>
                        {statusLabel[job.status]}
                      </Badge>
                      {job.status === 'generating' && <Spinner size="sm" />}
                      <span className="font-mono text-[11px] text-muted">
                        {formatTime(job.created_at)}
                      </span>
                    </div>
                    <p className="text-sm text-ink truncate">{job.prompt}</p>
                    <div className="mt-1 flex items-center gap-2 text-[11px] text-muted">
                      <span>{job.duration_seconds}s</span>
                      <span>·</span>
                      <span>{job.resolution}</span>
                    </div>
                    {job.error && (
                      <p className="mt-1.5 text-xs text-alert-red">Error: {job.error}</p>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      onClick={() => setExpandedId(expandedId === job.id ? null : job.id)}
                      className="rounded-lg p-1.5 text-muted hover:bg-surface-dim hover:text-ink"
                      title="Toggle details"
                    >
                      {expandedId === job.id ? '▲' : '▼'}
                    </button>
                    <button
                      onClick={() => handleDelete(job.id)}
                      className="rounded-lg p-1.5 text-muted hover:bg-surface-dim hover:text-alert-red"
                      title="Delete"
                    >
                      🗑
                    </button>
                  </div>
                </div>

                {/* Expanded details / video playback */}
                {expandedId === job.id && (
                  <div className="mt-3 border-t border-line pt-3 space-y-3">
                    {job.status === 'completed' && job.url && (
                      <div className="overflow-hidden rounded-lg bg-bg">
                        <video
                          src={chatMediaUrl(job.url)}
                          controls
                          className="w-full max-h-96"
                        />
                      </div>
                    )}
                    <div className="flex flex-wrap gap-x-6 gap-y-1 text-[11px] text-muted font-mono">
                      <span>ID: {job.id}</span>
                      <span>Created: {job.created_at}</span>
                      <span>Updated: {job.updated_at}</span>
                    </div>
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default VideoProduction;

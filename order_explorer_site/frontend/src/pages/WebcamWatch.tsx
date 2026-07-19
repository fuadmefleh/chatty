import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchWebcamSource } from '../chattyApi';
import type { WebcamSource } from '../chattyApi';
import PageHeader from '../components/ui/PageHeader';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import WebcamPlayer from '../components/webcams/WebcamPlayer';

const verifyTone: Record<WebcamSource['verify_status'], 'teal' | 'danger' | 'neutral'> = {
  ok: 'teal',
  broken: 'danger',
  unchecked: 'neutral',
};

const WebcamWatch: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [source, setSource] = useState<WebcamSource | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(false);
    fetchWebcamSource(id)
      .then(setSource)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="mx-auto max-w-[860px] px-4 py-6 md:px-6">
        <Spinner label="Loading stream…" />
      </div>
    );
  }

  if (error || !source) {
    return (
      <div className="mx-auto max-w-[860px] px-4 py-6 md:px-6">
        <EmptyState
          title="Source not found"
          description="This webcam may have been removed."
          action={<Link to="/webcams" className="text-sm font-semibold text-signal hover:underline">← Back to Webcams</Link>}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[860px] px-4 py-6 md:px-6">
      <PageHeader
        eyebrow="Assistant / Webcams / Watch"
        eyebrowColor="var(--signal)"
        title={source.name}
      />
      <WebcamPlayer source={source} />
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Badge tone="teal">{source.kind}</Badge>
        <Badge tone={verifyTone[source.verify_status]}>{source.verify_status}</Badge>
        {source.location && <span className="text-sm text-muted">{source.location}</span>}
      </div>
      {source.last_verified_at && (
        <p className="mt-2 text-xs text-muted">
          Last checked {new Date(source.last_verified_at).toLocaleString()}
          {source.verify_detail ? ` — ${source.verify_detail}` : ''}
        </p>
      )}
      <a href={source.url} target="_blank" rel="noreferrer" className="mt-3 inline-block text-sm font-semibold text-signal hover:underline">
        Open original URL ↗
      </a>
    </div>
  );
};

export default WebcamWatch;

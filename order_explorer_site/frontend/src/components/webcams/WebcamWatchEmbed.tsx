import { useEffect, useState } from 'react';
import { fetchWebcamSource } from '../../chattyApi';
import type { WebcamSource } from '../../chattyApi';
import WebcamPlayer from './WebcamPlayer';

// Small module-level cache so a message re-rendering during chat streaming
// doesn't refetch the same source on every token.
const sourceCache = new Map<string, Promise<WebcamSource>>();

const getSource = (id: string): Promise<WebcamSource> => {
  let promise = sourceCache.get(id);
  if (!promise) {
    promise = fetchWebcamSource(id);
    sourceCache.set(id, promise);
    promise.catch(() => sourceCache.delete(id));
  }
  return promise;
};

/** Renders a live inline player for a chat-embedded `/webcams/watch/{id}`
 * link, falling back to a plain link if the source can't be resolved. */
const WebcamWatchEmbed: React.FC<{ id: string; href: string; children?: React.ReactNode }> = ({
  id,
  href,
  children,
}) => {
  const [source, setSource] = useState<WebcamSource | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getSource(id)
      .then((s) => { if (!cancelled) setSource(s); })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [id]);

  if (failed) {
    return (
      <a href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  }

  if (!source) {
    return <div className="my-2 h-40 w-full max-w-md animate-pulse rounded-md bg-surface-dim" />;
  }

  return (
    <span className="my-2 block max-w-md">
      <WebcamPlayer source={source} />
      <span className="mt-1 flex items-center justify-between text-xs text-muted">
        <span>{source.name}</span>
        <a href={href} className="text-signal hover:underline">Open watch page ↗</a>
      </span>
    </span>
  );
};

export default WebcamWatchEmbed;

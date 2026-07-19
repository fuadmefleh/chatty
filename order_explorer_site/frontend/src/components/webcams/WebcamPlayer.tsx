import { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';
import type { WebcamSource } from '../../chattyApi';

// youtube.com/watch?v=ID, youtu.be/ID, youtube.com/live/ID, /shorts/ID, /embed/ID
const YOUTUBE_ID_RE = /(?:youtube\.com\/(?:watch\?(?:.*&)?v=|live\/|shorts\/|embed\/)|youtu\.be\/)([A-Za-z0-9_-]{6,})/;

const extractYoutubeId = (url: string): string | null => {
  const match = YOUTUBE_ID_RE.exec(url);
  return match ? match[1] : null;
};

const PlayerError: React.FC<{ message: string; url: string }> = ({ message, url }) => (
  <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-md border border-line bg-surface-dim p-4 text-center">
    <p className="m-0 text-sm text-muted">{message}</p>
    <a href={url} target="_blank" rel="noreferrer" className="text-sm font-semibold text-signal hover:underline">
      Open externally ↗
    </a>
  </div>
);

const SnapshotPlayer: React.FC<{ url: string; name: string }> = ({ url, name }) => {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 5000);
    return () => clearInterval(interval);
  }, [url]);

  const separator = url.includes('?') ? '&' : '?';
  return (
    <img
      src={`${url}${separator}_ts=${tick}`}
      alt={name}
      className="w-full rounded-md border border-line object-cover"
    />
  );
};

const HlsPlayer: React.FC<{ url: string }> = ({ url }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    setError(false);

    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = url;
      return;
    }

    if (Hls.isSupported()) {
      const hls = new Hls();
      hls.loadSource(url);
      hls.attachMedia(video);
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) setError(true);
      });
      return () => hls.destroy();
    }

    setError(true);
  }, [url]);

  if (error) {
    return <PlayerError message="This browser can't play this HLS stream." url={url} />;
  }

  return (
    <video
      ref={videoRef}
      autoPlay
      muted
      playsInline
      controls
      className="aspect-video w-full rounded-md border border-line bg-black"
    />
  );
};

const YoutubePlayer: React.FC<{ url: string }> = ({ url }) => {
  const videoId = extractYoutubeId(url);
  if (!videoId) {
    return <PlayerError message="Couldn't determine the YouTube video for this source." url={url} />;
  }
  return (
    <iframe
      src={`https://www.youtube.com/embed/${videoId}`}
      title="YouTube live stream"
      allow="autoplay; encrypted-media; picture-in-picture"
      allowFullScreen
      className="aspect-video w-full rounded-md border border-line"
    />
  );
};

const WebcamPlayer: React.FC<{ source: WebcamSource }> = ({ source }) => {
  switch (source.kind) {
    case 'snapshot':
      return <SnapshotPlayer url={source.url} name={source.name} />;
    case 'mjpeg':
      return <img src={source.url} alt={source.name} className="w-full rounded-md border border-line object-cover" />;
    case 'hls':
      return <HlsPlayer url={source.url} />;
    case 'youtube':
      return <YoutubePlayer url={source.url} />;
    case 'webpage':
    default:
      return (
        <PlayerError message="This source is a webpage, not a media feed - it can't be shown inline." url={source.url} />
      );
  }
};

export default WebcamPlayer;

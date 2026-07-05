type PulseTone = 'signal' | 'amber' | 'red' | 'green';

const toneClasses: Record<PulseTone, string> = {
  signal: 'bg-signal',
  amber: 'bg-alert-amber',
  red: 'bg-alert-red',
  green: 'bg-alert-green',
};

/** Small live-indicator dot for pages with polling/streaming data. */
const PulseDot: React.FC<{ tone?: PulseTone; label?: string }> = ({ tone = 'signal', label }) => (
  <span className="inline-flex items-center gap-1.5" role="status" aria-label={label ?? 'Live'}>
    <span className="relative flex h-2 w-2">
      <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${toneClasses[tone]} motion-reduce:animate-none`} />
      <span className={`relative inline-flex h-2 w-2 rounded-full ${toneClasses[tone]}`} />
    </span>
    {label && <span className="text-xs text-muted">{label}</span>}
  </span>
);

export default PulseDot;

import type { PropsWithChildren } from 'react';

type BadgeTone = 'gold' | 'ember' | 'teal' | 'neutral' | 'danger';

const toneClasses: Record<BadgeTone, string> = {
  gold: 'bg-alert-amber/15 text-alert-amber',
  ember: 'bg-alert-red/15 text-alert-red',
  teal: 'bg-signal/15 text-signal',
  neutral: 'bg-surface-dim text-muted',
  danger: 'bg-alert-red/15 text-alert-red',
};

const Badge: React.FC<PropsWithChildren<{ tone?: BadgeTone }>> = ({ children, tone = 'neutral' }) => (
  <span
    className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 font-mono text-[11px] font-semibold ${toneClasses[tone]}`}
  >
    {children}
  </span>
);

export default Badge;

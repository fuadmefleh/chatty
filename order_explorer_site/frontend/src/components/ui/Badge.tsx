import type { PropsWithChildren } from 'react';

type BadgeTone = 'gold' | 'ember' | 'teal' | 'neutral' | 'danger';

const toneColors: Record<BadgeTone, { bg: string; fg: string }> = {
  gold: { bg: 'rgba(200,155,60,0.15)', fg: 'var(--stamp-gold)' },
  ember: { bg: 'rgba(216,96,63,0.15)', fg: 'var(--stamp-ember)' },
  teal: { bg: 'rgba(79,168,160,0.15)', fg: 'var(--stamp-teal)' },
  neutral: { bg: 'var(--ink-700)', fg: 'var(--muted)' },
  danger: { bg: 'rgba(216,96,63,0.15)', fg: 'var(--danger)' },
};

const Badge: React.FC<PropsWithChildren<{ tone?: BadgeTone }>> = ({ children, tone = 'neutral' }) => {
  const c = toneColors[tone];
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 9px',
        borderRadius: 20,
        fontSize: 11,
        fontWeight: 600,
        fontFamily: 'var(--font-mono)',
        background: c.bg,
        color: c.fg,
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
};

export default Badge;

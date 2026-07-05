import type { ReactNode } from 'react';
import Card from './Card';

interface StatCardProps {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  tone?: 'signal' | 'amber' | 'red' | 'green' | 'neutral';
}

const toneClasses: Record<NonNullable<StatCardProps['tone']>, string> = {
  signal: 'text-signal',
  amber: 'text-alert-amber',
  red: 'text-alert-red',
  green: 'text-alert-green',
  neutral: 'text-ink',
};

const StatCard: React.FC<StatCardProps> = ({ label, value, detail, tone = 'neutral' }) => (
  <Card padding="16px 18px">
    <div className="mb-1.5 font-mono text-[11px] uppercase tracking-wider text-muted">{label}</div>
    <div className={`font-display text-2xl font-semibold ${toneClasses[tone]}`}>{value}</div>
    {detail && <div className="mt-1 text-xs text-muted">{detail}</div>}
  </Card>
);

export default StatCard;

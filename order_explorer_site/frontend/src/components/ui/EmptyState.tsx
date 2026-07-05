import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

const EmptyState: React.FC<EmptyStateProps> = ({ title, description, action }) => (
  <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-line px-6 py-12 text-center">
    <h3 className="font-display text-base font-semibold text-ink">{title}</h3>
    {description && <p className="max-w-sm text-sm text-muted">{description}</p>}
    {action && <div className="mt-1">{action}</div>}
  </div>
);

export default EmptyState;

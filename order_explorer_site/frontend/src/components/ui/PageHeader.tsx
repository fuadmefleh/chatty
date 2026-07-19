import type { ReactNode } from 'react';

interface PageHeaderProps {
  eyebrow: string;
  eyebrowColor?: string;
  title: string;
  titleClassName?: string;
  actions?: ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({ eyebrow, eyebrowColor, title, titleClassName, actions }) => (
  <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
    <div>
      <div
        className="mb-1.5 font-mono text-[11px] uppercase tracking-wider"
// TODO: replace inline style with Tailwind class
        style={eyebrowColor ? { color: eyebrowColor } : undefined}
      >
        <span className={eyebrowColor ? '' : 'text-alert-amber'}>{eyebrow}</span>
      </div>
      <h1 className={titleClassName || 'font-display text-2xl'}>{title}</h1>
    </div>
    {actions && <div className="flex items-center gap-2.5">{actions}</div>}
  </div>
);

export default PageHeader;

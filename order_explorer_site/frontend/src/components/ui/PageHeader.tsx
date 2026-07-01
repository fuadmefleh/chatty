import type { ReactNode } from 'react';

interface PageHeaderProps {
  eyebrow: string;
  eyebrowColor?: string;
  title: string;
  actions?: ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({
  eyebrow,
  eyebrowColor = 'var(--stamp-gold)',
  title,
  actions,
}) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      gap: 16,
      marginBottom: 28,
      flexWrap: 'wrap',
    }}
  >
    <div>
      <div
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: eyebrowColor,
          marginBottom: 6,
        }}
      >
        {eyebrow}
      </div>
      <h1 style={{ fontSize: 26 }}>{title}</h1>
    </div>
    {actions && <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>{actions}</div>}
  </div>
);

export default PageHeader;

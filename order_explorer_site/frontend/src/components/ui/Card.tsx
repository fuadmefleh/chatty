import type { PropsWithChildren, CSSProperties } from 'react';

interface CardProps {
  style?: CSSProperties;
  padding?: number | string;
}

const Card: React.FC<PropsWithChildren<CardProps>> = ({ children, style, padding = 20 }) => (
  <div
    style={{
      background: 'var(--ink-800)',
      border: '1px solid var(--ink-700)',
      borderRadius: 10,
      padding,
      ...style,
    }}
  >
    {children}
  </div>
);

export default Card;

import type { PropsWithChildren, CSSProperties } from 'react';

interface CardProps {
  style?: CSSProperties;
  className?: string;
  padding?: number | string;
}

const Card: React.FC<PropsWithChildren<CardProps>> = ({ children, style, className = '', padding = 20 }) => (
  <div
    className={`rounded-xl border border-line bg-surface ${className}`}
    style={{ padding, ...style }}
  >
    {children}
  </div>
);

export default Card;

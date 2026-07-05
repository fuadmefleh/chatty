import type { FC, SVGProps } from 'react';

const iconProps = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

export const LedgerIcon: FC<SVGProps<SVGSVGElement>> = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z" />
    <path d="M9 8h6M9 12h6M9 16h3" />
  </svg>
);

export const TrainingIcon: FC<SVGProps<SVGSVGElement>> = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M6.5 8v8M17.5 8v8" />
    <path d="M3.5 10v4M20.5 10v4" />
    <path d="M6.5 12h11" />
  </svg>
);

export const AssistantIcon: FC<SVGProps<SVGSVGElement>> = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M4 5h16v10H9l-4 4V5Z" />
    <path d="M9 9h6M9 12h3" />
  </svg>
);

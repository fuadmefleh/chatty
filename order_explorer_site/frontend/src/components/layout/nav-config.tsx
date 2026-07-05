import type { FC, SVGProps } from 'react';
import { LedgerIcon, TrainingIcon, AssistantIcon } from './nav-icons';

export interface NavEntry {
  to: string;
  label: string;
}

export type NavColor = 'amber' | 'red' | 'signal';

export interface NavGroup {
  id: string;
  caption: string;
  color: NavColor;
  icon: FC<SVGProps<SVGSVGElement>>;
  entries: NavEntry[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'ledger',
    caption: 'Ledger',
    color: 'amber',
    icon: LedgerIcon,
    entries: [
      { to: '/', label: 'Dashboard' },
      { to: '/orders', label: 'Orders' },
      { to: '/items', label: 'Items' },
      { to: '/months', label: 'Months' },
      { to: '/years', label: 'Years' },
      { to: '/categories', label: 'Categories' },
      { to: '/vendors', label: 'Vendors' },
      { to: '/search', label: 'Search' },
      { to: '/budget', label: 'Budget' },
      { to: '/recurring', label: 'Recurring' },
      { to: '/export', label: 'Export' },
    ],
  },
  {
    id: 'training',
    caption: 'Training',
    color: 'red',
    icon: TrainingIcon,
    entries: [{ to: '/exercise', label: 'Exercise' }],
  },
  {
    id: 'assistant',
    caption: 'Assistant',
    color: 'signal',
    icon: AssistantIcon,
    entries: [
      { to: '/chat', label: 'Chat' },
      { to: '/notes', label: 'Notes' },
      { to: '/transcriptions', label: 'Transcriptions' },
      { to: '/speakers', label: 'Speakers' },
      { to: '/insights', label: 'Insights' },
      { to: '/reminders', label: 'Reminders' },
      { to: '/memory', label: 'Memory' },
      { to: '/requests', label: 'Requests' },
      { to: '/suggestions', label: 'Suggestions' },
      { to: '/system', label: 'System' },
      { to: '/server-health', label: 'Server Health' },
      { to: '/token-usage', label: 'Token Usage' },
      { to: '/code', label: 'Code' },
    ],
  },
];

export const isNavActive = (pathname: string, to: string): boolean => {
  if (to === '/') return pathname === '/';
  return pathname === to || pathname.startsWith(`${to}/`);
};

export const navColorTextClass: Record<NavColor, string> = {
  amber: 'text-alert-amber',
  red: 'text-alert-red',
  signal: 'text-signal',
};

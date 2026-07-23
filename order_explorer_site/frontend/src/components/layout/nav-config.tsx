import type { FC, SVGProps } from 'react';
import { LedgerIcon, TrainingIcon, AssistantIcon } from './nav-icons';

export interface NavEntry {
  to: string;
  label: string;
}

export type NavColor = 'amber' | 'red' | 'signal';

export interface NavSection {
  id: string;
  caption: string;
  entries: NavEntry[];
}

export interface NavGroup {
  id: string;
  caption: string;
  color: NavColor;
  icon: FC<SVGProps<SVGSVGElement>>;
  sections: NavSection[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'ledger',
    caption: 'Ledger',
    color: 'amber',
    icon: LedgerIcon,
    sections: [
      {
        id: 'overview',
        caption: 'Overview',
        entries: [
          { to: '/', label: 'Dashboard' },
          { to: '/search', label: 'Search' },
        ],
      },
      {
        id: 'records',
        caption: 'Records',
        entries: [
          { to: '/orders', label: 'Orders' },
          { to: '/items', label: 'Items' },
          { to: '/months', label: 'Months' },
          { to: '/years', label: 'Years' },
          { to: '/categories', label: 'Categories' },
          { to: '/vendors', label: 'Vendors' },
        ],
      },
      {
        id: 'planning',
        caption: 'Planning',
        entries: [
          { to: '/budget', label: 'Budget' },
          { to: '/recurring', label: 'Recurring' },
        ],
      },
      {
        id: 'export',
        caption: 'Export',
        entries: [{ to: '/export', label: 'Export' }],
      },
    ],
  },
  {
    id: 'training',
    caption: 'Training',
    color: 'red',
    icon: TrainingIcon,
    sections: [
      {
        id: 'exercise',
        caption: 'Exercise',
        entries: [{ to: '/exercise', label: 'Exercise' }],
      },
    ],
  },
  {
    id: 'assistant',
    caption: 'Assistant',
    color: 'signal',
    icon: AssistantIcon,
    sections: [
      {
        id: 'conversation',
        caption: 'Conversation',
        entries: [
          { to: '/chat', label: 'Chat' },
          { to: '/notes', label: 'Notes' },
          { to: '/transcriptions', label: 'Transcriptions' },
          { to: '/speakers', label: 'Speakers' },
          { to: '/insights', label: 'Insights' },
          { to: '/reminders', label: 'Reminders' },
        ],
      },
      {
        id: 'writing',
        caption: 'Writing',
        entries: [{ to: '/chatty-blog', label: 'Notes by Atlas' }],
      },
      {
        id: 'channels',
        caption: 'Channels',
        entries: [
          { to: '/whatsapp', label: 'WhatsApp' },
          { to: '/linkedin', label: 'LinkedIn' },
        ],
      },
      {
        id: 'memory',
        caption: 'Memory',
        entries: [
          { to: '/memory', label: 'Memory' },
          { to: '/requests', label: 'Requests' },
          { to: '/suggestions', label: 'Suggestions' },
        ],
      },
      {
        id: 'media',
        caption: 'Media',
        entries: [
          { to: '/video-production', label: 'Video Production' },
          { to: '/webcams', label: 'Webcams' },
          { to: '/png-stamp', label: 'PNG Owner Stamp' },
        ],
      },
      {
        id: 'admin',
        caption: 'Admin',
        entries: [
          { to: '/system', label: 'System' },
          { to: '/settings', label: 'Settings' },
          { to: '/server-health', label: 'Server Health' },
          { to: '/token-usage', label: 'Token Usage' },
          { to: '/code', label: 'Code' },
          { to: '/taste-audit', label: 'Taste Audit' },
        ],
      },
    ],
  },
];

export const groupEntries = (group: NavGroup): NavEntry[] => group.sections.flatMap((section) => section.entries);

export const isNavActive = (pathname: string, to: string): boolean => {
  if (to === '/') return pathname === '/';
  return pathname === to || pathname.startsWith(`${to}/`);
};

export const navColorTextClass: Record<NavColor, string> = {
  amber: 'text-alert-amber',
  red: 'text-alert-red',
  signal: 'text-signal',
};

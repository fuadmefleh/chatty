import React from 'react';
import { Link, useLocation } from 'react-router-dom';

interface NavEntry {
  to: string;
  label: string;
}

interface NavGroup {
  caption: string;
  color: string;
  entries: NavEntry[];
}

const GROUPS: NavGroup[] = [
  {
    caption: 'Ledger',
    color: 'var(--stamp-gold)',
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
    caption: 'Training',
    color: 'var(--stamp-ember)',
    entries: [{ to: '/exercise', label: 'Exercise' }],
  },
  {
    caption: 'Assistant',
    color: 'var(--stamp-teal)',
    entries: [
      { to: '/chat', label: 'Chat' },
      { to: '/notes', label: 'Notes' },
      { to: '/insights', label: 'Insights' },
      { to: '/reminders', label: 'Reminders' },
      { to: '/memory', label: 'Memory' },
      { to: '/requests', label: 'Requests' },
      { to: '/system', label: 'System' },
    ],
  },
];

const isActive = (pathname: string, to: string): boolean => {
  if (to === '/') return pathname === '/';
  return pathname === to || pathname.startsWith(`${to}/`);
};

const Sidebar: React.FC = () => {
  const { pathname } = useLocation();

  return (
    <aside className="ledger-sidebar">
      <div
        className="ledger-brand"
        style={{
          padding: '0 20px 18px',
          fontFamily: 'var(--font-mono)',
          fontSize: 13,
          letterSpacing: '0.08em',
          color: 'var(--paper-dim)',
          borderBottom: '1px solid var(--ink-700)',
          marginBottom: 4,
        }}
      >
        CHATTY&nbsp;<span style={{ color: 'var(--muted)' }}>/ ledger</span>
      </div>
      <div className="ledger-sidebar-groups">
        {GROUPS.map((group) => (
          <div className="ledger-nav-group" key={group.caption}>
            <div className="ledger-nav-caption">{group.caption}</div>
            {group.entries.map((entry) => {
              const active = isActive(pathname, entry.to);
              return (
                <Link
                  key={entry.to}
                  to={entry.to}
                  className={`ledger-nav-item${active ? ' active' : ''}`}
                  style={{ '--tab': group.color } as React.CSSProperties}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: group.color,
                      opacity: active ? 1 : 0.45,
                      flexShrink: 0,
                    }}
                  />
                  {entry.label}
                </Link>
              );
            })}
          </div>
        ))}
      </div>
    </aside>
  );
};

export default Sidebar;

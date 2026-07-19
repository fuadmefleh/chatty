import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { NAV_GROUPS, isNavActive, navColorTextClass } from './nav-config';
import ThemeToggle from '../ui/ThemeToggle';
import LogoutButton from '../ui/LogoutButton';

const COLLAPSE_KEY = 'chatty-rail-collapsed';
const SECTIONS_KEY = 'chatty-sidebar-sections-collapsed';

const readCollapsedSections = (): Record<string, boolean> => {
  try {
    return JSON.parse(localStorage.getItem(SECTIONS_KEY) ?? '{}');
  } catch {
    return {};
  }
};

const Sidebar: React.FC = () => {
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === '1');
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>(readCollapsedSections);

  useEffect(() => {
    localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0');
  }, [collapsed]);

  useEffect(() => {
    localStorage.setItem(SECTIONS_KEY, JSON.stringify(collapsedSections));
  }, [collapsedSections]);

  const toggleSection = (key: string) => {
    setCollapsedSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <aside
      className={`sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-line bg-surface transition-[width] duration-150 md:flex ${
        collapsed ? 'w-[68px]' : 'w-60'
      }`}
    >
      <div
        className={`flex items-center border-b border-line px-4 py-4 font-mono text-sm tracking-wide text-ink-dim ${
          collapsed ? 'justify-center px-0' : ''
        }`}
      >
        {collapsed ? (
          <span className="font-semibold text-signal">C</span>
        ) : (
          <>
            CHATTY <span className="ml-1 text-muted">/ ops</span>
          </>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto py-2" aria-label="Primary">
        {NAV_GROUPS.map((group) => (
          <div key={group.id} className="mb-1">
            {group.sections.map((section) => {
              const sectionKey = `${group.id}:${section.id}`;
              const hasActiveEntry = section.entries.some((entry) => isNavActive(pathname, entry.to));
              const sectionCollapsed = !collapsed && collapsedSections[sectionKey] && !hasActiveEntry;
              return (
                <div key={sectionKey}>
                  {!collapsed && (
                    <button
                      type="button"
                      onClick={() => toggleSection(sectionKey)}
                      aria-expanded={!sectionCollapsed}
                      className="flex w-full items-center justify-between px-4 pb-1 pt-4 font-mono text-[11px] uppercase tracking-wider text-muted hover:text-ink-dim"
                    >
                      {section.caption}
                      <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={2}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className={`h-3 w-3 shrink-0 transition-transform ${sectionCollapsed ? '-rotate-90' : ''}`}
                      >
                        <path d="M6 9l6 6 6-6" />
                      </svg>
                    </button>
                  )}
                  {!sectionCollapsed &&
                    section.entries.map((entry) => {
                      const active = isNavActive(pathname, entry.to);
                      return (
                        <Link
                          key={entry.to}
                          to={entry.to}
                          aria-current={active ? 'page' : undefined}
                          title={collapsed ? entry.label : undefined}
                          className={`mx-2 my-0.5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                            active ? 'bg-bg text-ink' : 'text-muted hover:bg-bg hover:text-ink'
                          } ${collapsed ? 'justify-center px-0' : ''}`}
                        >
                          <span
                            className={`h-1.5 w-1.5 shrink-0 rounded-full bg-current ${
                              active ? navColorTextClass[group.color] : 'text-line'
                            }`}
                            aria-hidden="true"
                          />
                          {!collapsed && entry.label}
                        </Link>
                      );
                    })}
                </div>
              );
            })}
          </div>
        ))}
      </nav>

      <div className={`flex items-center gap-2 border-t border-line p-3 ${collapsed ? 'flex-col' : 'justify-between'}`}>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <LogoutButton />
        </div>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line p-0 text-ink-dim transition-colors hover:border-signal hover:text-ink"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`h-4 w-4 transition-transform ${collapsed ? 'rotate-180' : ''}`}
          >
            <path d="M15 5 9 12l6 7" />
          </svg>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;

import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { NAV_GROUPS, groupEntries, isNavActive, navColorTextClass } from './nav-config';
import Drawer from '../ui/Drawer';

const MobileNav: React.FC = () => {
  const { pathname } = useLocation();
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const activeGroup = NAV_GROUPS.find((group) => groupEntries(group).some((entry) => isNavActive(pathname, entry.to)));

  return (
    <>
      <nav
        className="fixed inset-x-0 bottom-0 z-40 flex border-t border-line bg-surface md:hidden"
// TODO: replace inline style with Tailwind class
// TODO: replace inline style with Tailwind class
// TODO: replace inline style with Tailwind class
// TODO: replace inline style with Tailwind class
// TODO: replace inline style with Tailwind class
// TODO: replace inline style with Tailwind class
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
        aria-label="Primary"
      >
        {NAV_GROUPS.map((group) => {
          const Icon = group.icon;
          const active = activeGroup?.id === group.id;
          return (
            <button
              key={group.id}
              type="button"
              onClick={() => setOpenGroup(group.id)}
              aria-haspopup="dialog"
              aria-expanded={openGroup === group.id}
              className={`flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition-colors ${
                active ? navColorTextClass[group.color] : 'text-muted'
              }`}
            >
              <Icon className="h-5 w-5" />
              {group.caption}
            </button>
          );
        })}
      </nav>

      {NAV_GROUPS.map((group) => (
        <Drawer key={group.id} open={openGroup === group.id} onClose={() => setOpenGroup(null)} title={group.caption}>
          <div className="flex flex-col gap-3">
            {group.sections.map((section) => (
              <div key={section.id} className="flex flex-col gap-1">
                {group.sections.length > 1 && (
                  <div className="px-3 font-mono text-[11px] uppercase tracking-wider text-muted">
                    {section.caption}
                  </div>
                )}
                {section.entries.map((entry) => {
                  const active = isNavActive(pathname, entry.to);
                  return (
                    <Link
                      key={entry.to}
                      to={entry.to}
                      onClick={() => setOpenGroup(null)}
                      aria-current={active ? 'page' : undefined}
                      className={`rounded-lg px-3 py-2.5 text-sm font-medium ${
                        active ? 'bg-bg text-ink' : 'text-ink-dim hover:bg-bg hover:text-ink'
                      }`}
                    >
                      {entry.label}
                    </Link>
                  );
                })}
              </div>
            ))}
          </div>
        </Drawer>
      ))}
    </>
  );
};

export default MobileNav;

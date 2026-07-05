import { useEffect, useRef } from 'react';
import type { PropsWithChildren, ReactNode } from 'react';

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
}

/** Bottom-sheet drawer used for mobile navigation and small pickers. */
const Drawer: React.FC<PropsWithChildren<DrawerProps>> = ({ open, onClose, title, children }) => {
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<Element | null>(null);

  useEffect(() => {
    if (open) {
      triggerRef.current = document.activeElement;
      panelRef.current?.focus();
    } else if (triggerRef.current instanceof HTMLElement) {
      triggerRef.current.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <div
      className={`fixed inset-0 z-50 flex items-end justify-center transition-opacity duration-200 ${
        open ? 'opacity-100' : 'pointer-events-none opacity-0'
      }`}
      aria-hidden={!open}
    >
      <div className="absolute inset-0 bg-ink/40" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === 'string' ? title : undefined}
        tabIndex={-1}
        style={{ paddingBottom: 'calc(1rem + env(safe-area-inset-bottom))' }}
        className={`relative z-10 max-h-[75vh] w-full max-w-md overflow-y-auto rounded-t-2xl border-t border-line bg-surface p-4 shadow-xl outline-none transition-transform duration-200 ${
          open ? 'translate-y-0' : 'translate-y-full'
        }`}
      >
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-line" aria-hidden="true" />
        {title && <h2 className="mb-3 font-display text-base font-semibold text-ink">{title}</h2>}
        {children}
      </div>
    </div>
  );
};

export default Drawer;

import { useEffect, useRef } from 'react';
import type { PropsWithChildren, ReactNode } from 'react';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
}

/** Centered dialog for confirmations and small forms. */
const Modal: React.FC<PropsWithChildren<ModalProps>> = ({ open, onClose, title, children }) => {
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
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 transition-opacity duration-150 ${
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
        className={`relative z-10 w-full max-w-md rounded-2xl border border-line bg-surface p-5 shadow-xl outline-none transition-transform duration-150 ${
          open ? 'scale-100' : 'scale-95'
        }`}
      >
        {title && <h2 className="mb-3 font-display text-base font-semibold text-ink">{title}</h2>}
        {children}
      </div>
    </div>
  );
};

export default Modal;

import { useCallback, useMemo, useRef, useState } from 'react';
import type { PropsWithChildren } from 'react';
import { ToastContext, type ToastTone } from '../../hooks/useToast';

interface Toast {
  id: number;
  message: string;
  tone: ToastTone;
}

const toneClasses: Record<ToastTone, string> = {
  signal: 'border-signal/40 bg-signal-dim text-ink',
  amber: 'border-alert-amber/40 bg-alert-amber/10 text-ink',
  red: 'border-alert-red/40 bg-alert-red/10 text-ink',
  green: 'border-alert-green/40 bg-alert-green/10 text-ink',
};

export const ToastProvider: React.FC<PropsWithChildren> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);

  const showToast = useCallback((message: string, tone: ToastTone = 'signal') => {
    const id = nextId.current++;
    setToasts((current) => [...current, { id, message, tone }]);
    setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="fixed inset-x-0 top-[calc(4rem+env(safe-area-inset-top))] z-[60] flex flex-col items-center gap-2 px-4 md:inset-x-auto md:top-auto md:right-6 md:bottom-6 md:items-end"
        aria-live="polite"
        aria-atomic="true"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className={`w-full max-w-sm rounded-lg border px-4 py-2.5 text-sm shadow-lg ${toneClasses[toast.tone]}`}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

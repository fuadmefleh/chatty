import { clearStoredApiKey } from '../../chattyApi';

const LogoutButton: React.FC = () => (
  <button
    type="button"
    onClick={() => {
      clearStoredApiKey();
      window.location.reload();
    }}
    aria-label="Lock session"
    title="Lock session"
    className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line p-0 text-ink-dim transition-colors hover:border-alert-red hover:text-alert-red"
  >
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  </button>
);

export default LogoutButton;

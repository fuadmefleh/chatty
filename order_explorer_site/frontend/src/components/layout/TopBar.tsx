import ThemeToggle from '../ui/ThemeToggle';
import LogoutButton from '../ui/LogoutButton';

const TopBar: React.FC = () => (
  <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-surface/95 px-4 py-3 backdrop-blur md:hidden">
    <span className="font-mono text-sm tracking-wide text-ink-dim">
      CHATTY <span className="text-muted">/ ops</span>
    </span>
    <div className="flex items-center gap-2">
      <ThemeToggle />
      <LogoutButton />
    </div>
  </header>
);

export default TopBar;

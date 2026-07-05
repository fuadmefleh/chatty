import type { PropsWithChildren } from 'react';
import Sidebar from './Sidebar';
import MobileNav from './MobileNav';
import TopBar from './TopBar';

const AppShell: React.FC<PropsWithChildren> = ({ children }) => (
  <div className="flex min-h-dvh bg-bg text-ink">
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-signal focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
    >
      Skip to content
    </a>
    <Sidebar />
    <div className="flex min-w-0 flex-1 flex-col">
      <TopBar />
      <main id="main-content" className="min-w-0 flex-1 overflow-y-auto pb-16 md:pb-0">
        {children}
      </main>
    </div>
    <MobileNav />
  </div>
);

export default AppShell;

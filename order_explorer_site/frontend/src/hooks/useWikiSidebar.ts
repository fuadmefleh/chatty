import { createContext, useContext } from 'react';
import type { WikiPage } from '../chattyApi';

export interface WikiSidebarContextValue {
  refreshPages: () => void;
  pages: WikiPage[];
}

export const WikiSidebarContext = createContext<WikiSidebarContextValue>({ refreshPages: () => {}, pages: [] });

export const useWikiSidebar = (): WikiSidebarContextValue => useContext(WikiSidebarContext);

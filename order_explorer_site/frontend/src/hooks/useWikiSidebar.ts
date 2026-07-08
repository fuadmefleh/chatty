import { createContext, useContext } from 'react';

export interface WikiSidebarContextValue {
  refreshPages: () => void;
}

export const WikiSidebarContext = createContext<WikiSidebarContextValue>({ refreshPages: () => {} });

export const useWikiSidebar = (): WikiSidebarContextValue => useContext(WikiSidebarContext);

import { createContext, useContext } from 'react';
import type { WhatsAppChat } from '../chattyApi';

export interface WhatsAppChatsContextValue {
  chats: WhatsAppChat[];
  refreshChats: () => void;
}

export const WhatsAppChatsContext = createContext<WhatsAppChatsContextValue>({
  chats: [],
  refreshChats: () => {},
});

export const useWhatsAppChats = (): WhatsAppChatsContextValue => useContext(WhatsAppChatsContext);

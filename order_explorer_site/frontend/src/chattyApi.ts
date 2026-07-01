/**
 * chattyApi.ts
 * Axios instance for the Chatty Web API (port 8016).
 * Automatically attaches the X-API-Key header from localStorage.
 */
import axios from 'axios';

// Relative to the current origin — nginx (prod) or the Vite dev-server proxy (dev)
// forwards /api/chatty/* to the chatty-web-server. Routes below already include
// the /api/chatty prefix, so this stays empty rather than duplicating it.
export const CHATTY_API_BASE = '';
export const WS_CHAT_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/chatty/chat`;
export const API_KEY_STORAGE = 'chatty_api_key';

export function getStoredApiKey(): string {
  return localStorage.getItem(API_KEY_STORAGE) ?? '';
}

export function setStoredApiKey(key: string): void {
  localStorage.setItem(API_KEY_STORAGE, key);
}

export function clearStoredApiKey(): void {
  localStorage.removeItem(API_KEY_STORAGE);
}

const chattyApi = axios.create({
  baseURL: CHATTY_API_BASE,
});

chattyApi.interceptors.request.use((config) => {
  const key = getStoredApiKey();
  if (key) {
    config.headers['X-API-Key'] = key;
  }
  return config;
});

// ── Notes ────────────────────────────────────────────────────────────────────
export interface ChattyNote {
  id: string;
  content: string;
  created_at: string;
  user_id: string;
}

export const fetchChattyNotes = async (): Promise<ChattyNote[]> => {
  const res = await chattyApi.get<ChattyNote[]>('/api/chatty/notes');
  return res.data;
};

export const createChattyNote = async (content: string): Promise<ChattyNote> => {
  const res = await chattyApi.post<ChattyNote>('/api/chatty/notes', { content });
  return res.data;
};

export const updateChattyNote = async (id: string, content: string): Promise<ChattyNote> => {
  const res = await chattyApi.put<ChattyNote>(`/api/chatty/notes/${id}`, { content });
  return res.data;
};

export const deleteChattyNote = async (id: string): Promise<void> => {
  await chattyApi.delete(`/api/chatty/notes/${id}`);
};

// ── Reminders ─────────────────────────────────────────────────────────────────
export interface ChattyReminder {
  _file: string;
  [key: string]: unknown;
}

export const fetchChattyReminders = async (): Promise<ChattyReminder[]> => {
  const res = await chattyApi.get<ChattyReminder[]>('/api/chatty/reminders');
  return res.data;
};

export const deleteChattyReminder = async (filename: string): Promise<void> => {
  await chattyApi.delete(`/api/chatty/reminders/${encodeURIComponent(filename)}`);
};

// ── Memory ────────────────────────────────────────────────────────────────────
export interface MemoryEntry {
  date: string;
  content: string;
  filename: string;
}

export interface MemoryData {
  short_term: MemoryEntry[];
  long_term: MemoryEntry[];
}

export const fetchChattyMemory = async (days = 7): Promise<MemoryData> => {
  const res = await chattyApi.get<MemoryData>('/api/chatty/memory', { params: { days } });
  return res.data;
};

// ── System ────────────────────────────────────────────────────────────────────
export interface SkillInfo {
  name: string;
  description: string;
  tool_count: number;
  tools: string[];
}

export interface Pm2Process {
  name?: string;
  status?: string;
  pid?: number;
  uptime?: number;
  restarts?: number;
  error?: string;
}

export interface SystemStatus {
  skills: SkillInfo[];
  pm2: Pm2Process[];
  web_user_id: string;
  timestamp: string;
}

export const fetchChattySystem = async (): Promise<SystemStatus> => {
  const res = await chattyApi.get<SystemStatus>('/api/chatty/system');
  return res.data;
};

// ── Feature Requests (Pi agent) ────────────────────────────────────────────────
export type FeatureRequestStatus = 'queued' | 'running' | 'completed' | 'error';

export interface FeatureRequest {
  id: string;
  prompt: string;
  status: FeatureRequestStatus;
  created_at: string;
  updated_at: string;
  files_changed: string[];
  log: string[];
  summary: string;
}

export const fetchFeatureRequests = async (): Promise<FeatureRequest[]> => {
  const res = await chattyApi.get<FeatureRequest[]>('/api/chatty/requests');
  return res.data;
};

export const createFeatureRequest = async (prompt: string): Promise<FeatureRequest> => {
  const res = await chattyApi.post<FeatureRequest>('/api/chatty/requests', { prompt });
  return res.data;
};

export const deleteFeatureRequest = async (id: string): Promise<void> => {
  await chattyApi.delete(`/api/chatty/requests/${id}`);
};

export default chattyApi;

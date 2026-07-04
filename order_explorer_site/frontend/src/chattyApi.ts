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

// ── Transcriptions ─────────────────────────────────────────────────────────────
// Raw transcriptions (e.g. iOS voice memos) awaiting/after automatic mining
// into long-term memory by the heartbeat. Separate from Notes — write-once,
// no update endpoint.
export interface ChattyTranscription {
  id: string;
  content: string;
  created_at: string;
  user_id: string;
  source: string;
  mined: boolean;
  has_audio: boolean;
}

export const fetchTranscriptions = async (includeArchived = false): Promise<ChattyTranscription[]> => {
  const res = await chattyApi.get<ChattyTranscription[]>('/api/chatty/transcriptions', {
    params: { include_archived: includeArchived },
  });
  return res.data;
};

export const deleteTranscription = async (id: string): Promise<void> => {
  await chattyApi.delete(`/api/chatty/transcriptions/${id}`);
};

// Fetches the audio as a blob (via the authenticated axios instance, since a
// plain <audio src> can't attach the X-API-Key header) and hands back an
// object URL the caller must revoke when done with it.
export const fetchTranscriptionAudioUrl = async (id: string): Promise<string> => {
  const res = await chattyApi.get(`/api/chatty/transcriptions/${id}/audio`, {
    responseType: 'blob',
  });
  return URL.createObjectURL(res.data);
};

// ── Watchlist ────────────────────────────────────────────────────────────────
export type WatchTopicKind = 'news' | 'stock' | 'github';

export interface ChattyWatchTopic {
  id: string;
  topic: string;
  kind: WatchTopicKind;
  user_id: string;
  created_at: string;
  last_run_at: string | null;
  seen_urls: string[];
}

export const fetchWatchlist = async (): Promise<ChattyWatchTopic[]> => {
  const res = await chattyApi.get<ChattyWatchTopic[]>('/api/chatty/watchlist');
  return res.data;
};

export const createWatchTopic = async (topic: string, kind: WatchTopicKind = 'news'): Promise<ChattyWatchTopic> => {
  const res = await chattyApi.post<ChattyWatchTopic>('/api/chatty/watchlist', { topic, kind });
  return res.data;
};

export const deleteWatchTopic = async (id: string): Promise<void> => {
  await chattyApi.delete(`/api/chatty/watchlist/${id}`);
};

// ── Insights ─────────────────────────────────────────────────────────────────
export interface ChattyInsightSource {
  title: string;
  url: string;
}

export interface ChattyInsight {
  id: string;
  topic: string;
  summary: string;
  sources: ChattyInsightSource[];
  created_at: string;
  user_id: string;
}

export const fetchInsights = async (limit = 50): Promise<ChattyInsight[]> => {
  const res = await chattyApi.get<ChattyInsight[]>('/api/chatty/insights', { params: { limit } });
  return res.data;
};

export const deleteInsight = async (id: string): Promise<void> => {
  await chattyApi.delete(`/api/chatty/insights/${id}`);
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

// ── Code Browser ─────────────────────────────────────────────────────────────
export interface CodeTreeEntry {
  name: string;
  path: string;
  type: 'dir' | 'file';
  size: number | null;
}

export interface CodeTreeResponse {
  path: string;
  entries: CodeTreeEntry[];
}

export interface CodeFile {
  path: string;
  name: string;
  size: number;
  language: string;
  content: string;
}

export const fetchCodeTree = async (path = ''): Promise<CodeTreeResponse> => {
  const res = await chattyApi.get<CodeTreeResponse>('/api/chatty/code/tree', { params: { path } });
  return res.data;
};

export const fetchCodeFile = async (path: string): Promise<CodeFile> => {
  const res = await chattyApi.get<CodeFile>('/api/chatty/code/file', { params: { path } });
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

// ── Chat Sessions ──────────────────────────────────────────────────────────────
export interface ChatSession {
  id: number;
  first_ts: string;
  last_ts: string;
  message_count: number;
  summary: string;
}

export const fetchChatSessions = async (): Promise<ChatSession[]> => {
  const res = await chattyApi.get<ChatSession[]>('/api/chatty/sessions');
  return res.data;
};

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export const fetchSessionMessages = async (sessionId: number): Promise<ChatMessage[]> => {
  const res = await chattyApi.get<ChatMessage[]>(`/api/chatty/sessions/${sessionId}`);
  return res.data;
};

// ── Feature Requests (Pi agent) ────────────────────────────────────────────────
export type FeatureRequestStatus = 'queued' | 'running' | 'testing' | 'completed' | 'error';
export type FeatureRequestSource = 'user' | 'self_upgrade';

export interface FeatureRequest {
  id: string;
  prompt: string;
  status: FeatureRequestStatus;
  created_at: string;
  updated_at: string;
  files_changed: string[];
  log: string[];
  summary: string;
  source: FeatureRequestSource;
  branch: string | null;
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

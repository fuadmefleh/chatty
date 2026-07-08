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
  has_segments: boolean;
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

// ── Speakers (named voice roster + per-transcript labeling) ─────────────────
// Speaker identification/labeling - like tagging faces in photos, but for
// voices. A transcript's diarized segments start out tagged with generic
// ids (e.g. "SPEAKER_00"); labeling one resolves it to a real name here and
// going forward, and retroactively relabels other transcripts with the same
// voice (see also_updated_count on labelSpeaker's response).
export interface ChattySpeaker {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  num_samples: number;
  sample_transcription_id: string | null;
  sample_start: number | null;
  sample_end: number | null;
}

export interface TranscriptSegment {
  start: number | null;
  end: number | null;
  local_speaker: string | null;
  speaker_name: string | null;
  text: string;
}

export const fetchSpeakers = async (): Promise<ChattySpeaker[]> => {
  const res = await chattyApi.get<ChattySpeaker[]>('/api/chatty/speakers');
  return res.data;
};

export const renameSpeaker = async (id: string, name: string): Promise<ChattySpeaker> => {
  const res = await chattyApi.put<ChattySpeaker>(`/api/chatty/speakers/${id}`, { name });
  return res.data;
};

export const deleteSpeaker = async (id: string): Promise<void> => {
  await chattyApi.delete(`/api/chatty/speakers/${id}`);
};

export const fetchTranscriptionSegments = async (id: string): Promise<TranscriptSegment[]> => {
  const res = await chattyApi.get<{ segments: TranscriptSegment[] }>(`/api/chatty/transcriptions/${id}/segments`);
  return res.data.segments;
};

export const labelSpeaker = async (
  transcriptionId: string,
  localSpeaker: string,
  opts: { name?: string; speakerId?: string },
): Promise<{ speaker: ChattySpeaker; also_updated_count: number }> => {
  const res = await chattyApi.post(`/api/chatty/transcriptions/${transcriptionId}/label`, {
    local_speaker: localSpeaker,
    name: opts.name,
    speaker_id: opts.speakerId,
  });
  return res.data;
};

// Manually sweeps every transcript's unmatched speaker embeddings against
// the full roster right now, rather than waiting for the next label action
// to trigger it as a side effect - e.g. after loosening SPEAKER_MATCH_THRESHOLD.
export const rescanSpeakers = async (): Promise<{ updated_count: number }> => {
  const res = await chattyApi.post('/api/chatty/speakers/rescan');
  return res.data;
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
export interface ShortTermEntry {
  date: string;
  content: string;
  filename: string;
}

export interface WikiPage {
  title: string;
  type: 'entity' | 'concept';
  slug: string;
  summary: string;
  tags: string[];
  body: string;
  updated: string;
}

export interface MemoryData {
  short_term: ShortTermEntry[];
  long_term: WikiPage[];
  wiki_index: string;
  wiki_log: string;
}

export const fetchChattyMemory = async (days = 7): Promise<MemoryData> => {
  const res = await chattyApi.get<MemoryData>('/api/chatty/memory', { params: { days } });
  return res.data;
};

export const fetchWikiPage = async (type: string, slug: string): Promise<WikiPage | null> => {
  try {
    const res = await chattyApi.get<WikiPage>(
      `/api/chatty/memory/page/${encodeURIComponent(type)}/${encodeURIComponent(slug)}`,
    );
    return res.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) return null;
    throw error;
  }
};

export const searchChattyMemory = async (q: string): Promise<string> => {
  const res = await chattyApi.get<{ results: string }>('/api/chatty/memory/search', { params: { q } });
  return res.data.results;
};

export const triggerMemoryConsolidation = async (): Promise<string> => {
  const res = await chattyApi.post<{ result: string }>('/api/chatty/memory/consolidate');
  return res.data.result;
};

export interface WikiPageInput {
  title: string;
  summary: string;
  body: string;
  tags: string[];
}

export interface WikiPageCreateInput extends WikiPageInput {
  type: 'entity' | 'concept';
  slug: string;
}

export interface WikiBacklink {
  title: string;
  type: 'entity' | 'concept';
  slug: string;
  summary: string;
}

export interface WikiHealthRef {
  type: 'entity' | 'concept';
  slug: string;
  title: string;
}

export interface WikiHealthContradiction {
  page_a: WikiHealthRef;
  page_b: WikiHealthRef;
  description: string;
}

export interface WikiHealthCoverageGap {
  suggested_title: string;
  suggested_type: 'entity' | 'concept';
  description: string;
}

export interface WikiHealth {
  generated_at: string | null;
  total_pages: number;
  auto_fixed: { cross_references_added?: number; duplicates_merged?: number };
  orphans: WikiHealthRef[];
  contradictions: WikiHealthContradiction[];
  coverage_gaps: WikiHealthCoverageGap[];
}

export const createWikiPage = async (input: WikiPageCreateInput): Promise<WikiPage> => {
  const res = await chattyApi.post<WikiPage>('/api/chatty/memory/page', input);
  return res.data;
};

export const updateWikiPage = async (type: string, slug: string, input: WikiPageInput): Promise<WikiPage> => {
  const res = await chattyApi.put<WikiPage>(
    `/api/chatty/memory/page/${encodeURIComponent(type)}/${encodeURIComponent(slug)}`,
    input,
  );
  return res.data;
};

export const deleteWikiPage = async (type: string, slug: string): Promise<void> => {
  await chattyApi.delete(`/api/chatty/memory/page/${encodeURIComponent(type)}/${encodeURIComponent(slug)}`);
};

export const fetchWikiBacklinks = async (type: string, slug: string): Promise<WikiBacklink[]> => {
  const res = await chattyApi.get<WikiBacklink[]>(
    `/api/chatty/memory/page/${encodeURIComponent(type)}/${encodeURIComponent(slug)}/backlinks`,
  );
  return res.data;
};

export const fetchWikiHealth = async (): Promise<WikiHealth> => {
  const res = await chattyApi.get<WikiHealth>('/api/chatty/memory/health');
  return res.data;
};

export const triggerWikiLint = async (): Promise<string> => {
  const res = await chattyApi.post<{ result: string }>('/api/chatty/memory/lint');
  return res.data.result;
};

// Runs the full agent tool loop server-side (not a scripted fix) - expect
// this to take a couple of minutes, not seconds. No axios timeout is set
// on this client, so a slow response just waits rather than erroring out.
export const resolveWikiContradiction = async (
  contradiction: WikiHealthContradiction,
  guidance: string,
): Promise<string> => {
  const res = await chattyApi.post<{ result: string }>('/api/chatty/memory/health/resolve-contradiction', {
    page_a: contradiction.page_a,
    page_b: contradiction.page_b,
    description: contradiction.description,
    guidance,
  });
  return res.data.result;
};

export interface ReorganizeTargetPage {
  type: 'entity' | 'concept';
  slug: string;
  title: string;
  summary: string;
  source_pages: string[];
  already_exists: boolean;
}

export interface ReorganizeProposal {
  target_pages: ReorganizeTargetPage[];
  error?: string;
}

// One LLM call over the whole wiki - read-only, writes nothing. Expect
// tens of seconds, not instant.
export const proposeWikiReorganization = async (): Promise<ReorganizeProposal> => {
  const res = await chattyApi.post<ReorganizeProposal>('/api/chatty/memory/reorganize/propose');
  return res.data;
};

// Executes a (possibly user-trimmed) plan from proposeWikiReorganization().
// Only ever creates/overwrites the listed target pages - never deletes
// their source pages.
export const applyWikiReorganization = async (targetPages: ReorganizeTargetPage[]): Promise<string> => {
  const res = await chattyApi.post<{ result: string }>('/api/chatty/memory/reorganize/apply', {
    target_pages: targetPages,
  });
  return res.data.result;
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

// ── Integrations (Gmail) ─────────────────────────────────────────────────────
export interface GmailStatus {
  status: 'connected' | 'expired' | 'disconnected' | 'not_configured';
  reconnect_available: boolean;
}

export const fetchGmailStatus = async (): Promise<GmailStatus> => {
  const res = await chattyApi.get<GmailStatus>('/api/chatty/gmail/status');
  return res.data;
};

// Returns Google's consent-screen URL; the caller does a full-page navigation
// to it (window.location.href), not a fetch - Google's own redirect back to
// our /api/chatty/gmail/callback can't carry our X-API-Key header either, so
// that leg of the flow is a plain browser round trip, not an API call.
export const fetchGmailConnectUrl = async (): Promise<string> => {
  const res = await chattyApi.get<{ url: string }>('/api/chatty/gmail/connect-url');
  return res.data.url;
};

export const disconnectGmail = async (): Promise<GmailStatus> => {
  const res = await chattyApi.post<GmailStatus>('/api/chatty/gmail/disconnect');
  return res.data;
};

// ── Chat Sessions ──────────────────────────────────────────────────────────────
export interface ChatSession {
  id: number;
  first_ts: string;
  last_ts: string;
  message_count: number;
  summary: string;
  title: string | null;
}

export const fetchChatSessions = async (): Promise<ChatSession[]> => {
  const res = await chattyApi.get<ChatSession[]>('/api/chatty/sessions');
  return res.data;
};

export interface ChatAttachment {
  kind: 'image' | 'video';
  url: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  attachment?: ChatAttachment;
}

export const fetchSessionMessages = async (sessionId: number): Promise<ChatMessage[]> => {
  const res = await chattyApi.get<ChatMessage[]>(`/api/chatty/sessions/${sessionId}`);
  return res.data;
};

export const deleteSession = async (sessionId: number): Promise<void> => {
  await chattyApi.delete(`/api/chatty/sessions/${sessionId}`);
};

export const renameSession = async (sessionId: number, title: string): Promise<void> => {
  await chattyApi.put(`/api/chatty/sessions/${sessionId}`, { title });
};

// ── Chat attachments (images/videos sent in a chat message) ─────────────────
// `chat-media` URLs are authenticated via an `api_key` query param rather than
// the usual X-API-Key header, since they're used directly as <img>/<video> src
// (which can't set custom headers) - mirrors WS_CHAT_URL's own `?api_key=` auth.
// Both the upload response and session-history reload return the bare path
// (e.g. "/api/chatty/chat-media/<id>"); this appends the key for display.
export const chatMediaUrl = (relativeUrl: string): string =>
  `${relativeUrl}?api_key=${encodeURIComponent(getStoredApiKey())}`;

export const uploadChatAttachment = async (file: File): Promise<ChatAttachment & { id: string }> => {
  const form = new FormData();
  form.append('file', file);
  const res = await chattyApi.post<{ id: string; kind: 'image' | 'video'; url: string }>(
    '/api/chatty/chat/attachments',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return res.data;
};

// ── Feature Requests (Pi agent) ────────────────────────────────────────────────
// `merge_pending` = tests passed but main was dirty/on another branch at merge
// time - retried automatically every heartbeat tick (see retryPendingMerges
// below for the on-demand version), never a dead end requiring manual `git merge`.
export type FeatureRequestStatus = 'queued' | 'running' | 'testing' | 'merge_pending' | 'completed' | 'error';
export type FeatureRequestSource = 'user' | 'self_upgrade' | 'github_trending';

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

// Manually retries any merge_pending requests right now, instead of waiting
// for the heartbeat's own tick (see self_upgrade_manager.retry_pending_merges).
export const retryPendingMerges = async (): Promise<{ summaries: string[] }> => {
  const res = await chattyApi.post<{ summaries: string[] }>('/api/chatty/requests/retry-merges');
  return res.data;
};

// ── Trending Suggestions (GitHub trending scan, curated every few hours) ──────
export type TrendingSuggestionStatus = 'pending' | 'implemented' | 'dismissed';

export interface TrendingSuggestion {
  id: string;
  repo: string;
  repo_url: string;
  description: string;
  language: string;
  stars: string;
  rationale: string;
  integration_prompt: string;
  status: TrendingSuggestionStatus;
  created_at: string;
  updated_at: string;
  request_id: string | null;
}

export const fetchTrendingSuggestions = async (): Promise<TrendingSuggestion[]> => {
  const res = await chattyApi.get<TrendingSuggestion[]>('/api/chatty/trending-suggestions');
  return res.data;
};

export const scanTrendingSuggestions = async (): Promise<TrendingSuggestion[]> => {
  const res = await chattyApi.post<TrendingSuggestion[]>('/api/chatty/trending-suggestions/scan');
  return res.data;
};

export const implementTrendingSuggestion = async (id: string): Promise<TrendingSuggestion> => {
  const res = await chattyApi.post<TrendingSuggestion>(`/api/chatty/trending-suggestions/${id}/implement`);
  return res.data;
};

export const dismissTrendingSuggestion = async (id: string): Promise<TrendingSuggestion> => {
  const res = await chattyApi.post<TrendingSuggestion>(`/api/chatty/trending-suggestions/${id}/dismiss`);
  return res.data;
};

export const deleteTrendingSuggestion = async (id: string): Promise<void> => {
  await chattyApi.delete(`/api/chatty/trending-suggestions/${id}`);
};

// ── Webcam Sources & Suggestions (SearXNG-curated discovery, reviewed here) ───
export type WebcamKind = 'snapshot' | 'mjpeg' | 'hls' | 'youtube' | 'webpage';

export interface WebcamSource {
  id: string;
  name: string;
  url: string;
  kind: WebcamKind;
  location: string;
  enabled: boolean;
  source: 'manual' | 'suggestion';
  suggestion_id: string | null;
  created_at: string;
  updated_at: string;
}

export type WebcamSuggestionStatus = 'pending' | 'approved' | 'dismissed';

export interface WebcamSuggestion {
  id: string;
  name: string;
  url: string;
  discovered_url: string;
  kind: WebcamKind;
  location: string;
  rationale: string;
  status: WebcamSuggestionStatus;
  source_id: string | null;
  created_at: string;
  updated_at: string;
}

export const fetchWebcamSources = async (): Promise<WebcamSource[]> => {
  const res = await chattyApi.get<WebcamSource[]>('/api/chatty/webcam-sources');
  return res.data;
};

export const createWebcamSource = async (body: {
  name: string;
  url: string;
  kind: WebcamKind;
  location: string;
  enabled?: boolean;
}): Promise<WebcamSource> => {
  const res = await chattyApi.post<WebcamSource>('/api/chatty/webcam-sources', body);
  return res.data;
};

export const updateWebcamSource = async (
  id: string,
  body: Partial<{ name: string; url: string; kind: WebcamKind; location: string; enabled: boolean }>
): Promise<WebcamSource> => {
  const res = await chattyApi.put<WebcamSource>(`/api/chatty/webcam-sources/${id}`, body);
  return res.data;
};

export const deleteWebcamSource = async (id: string): Promise<void> => {
  await chattyApi.delete(`/api/chatty/webcam-sources/${id}`);
};

export const fetchWebcamSuggestions = async (): Promise<WebcamSuggestion[]> => {
  const res = await chattyApi.get<WebcamSuggestion[]>('/api/chatty/webcam-suggestions');
  return res.data;
};

export const scanWebcamSuggestions = async (): Promise<WebcamSuggestion[]> => {
  const res = await chattyApi.post<WebcamSuggestion[]>('/api/chatty/webcam-suggestions/scan');
  return res.data;
};

export const approveWebcamSuggestion = async (id: string): Promise<WebcamSuggestion> => {
  const res = await chattyApi.post<WebcamSuggestion>(`/api/chatty/webcam-suggestions/${id}/approve`);
  return res.data;
};

export const dismissWebcamSuggestion = async (id: string): Promise<WebcamSuggestion> => {
  const res = await chattyApi.post<WebcamSuggestion>(`/api/chatty/webcam-suggestions/${id}/dismiss`);
  return res.data;
};

export const deleteWebcamSuggestion = async (id: string): Promise<void> => {
  await chattyApi.delete(`/api/chatty/webcam-suggestions/${id}`);
};

// ── Server Health ───────────────────────────────────────────────────────────
export interface HealthCPU {
  logical_cores: number;
  physical_cores: number;
  overall_percent: number;
  per_core_percent: number[];
  load_average: { "1m": number; "5m": number; "15m": number };
}

export interface HealthMemory {
  total_bytes: number;
  used_bytes: number;
  available_bytes: number;
  percent: number;
}

export interface HealthDisk {
  device: string;
  mountpoint: string;
  fstype: string;
  total_bytes: number;
  used_bytes: number;
  free_bytes: number;
  percent: number;
}

export interface HealthNetwork {
  bytes_sent: number;
  bytes_recv: number;
  packets_sent: number;
  packets_recv: number;
}

export interface HealthGPU {
  name: string;
  memory_used_miB: number;
  memory_total_miB: number;
  gpu_util_percent: number;
  mem_util_percent: number;
  temperature_c: number;
  power_draw_w: number;
  power_limit_w: number;
  clock_gr_mhz: number;
  clock_mem_mhz: number;
  driver_version: string;
}

export interface ServerHealth {
  cpu: HealthCPU;
  memory: HealthMemory;
  swap: HealthMemory;
  disks: HealthDisk[];
  network: HealthNetwork;
  gpus: HealthGPU[];
  boot_time: string;
  uptime_seconds: number;
  timestamp: string;
}

export const fetchServerHealth = async (): Promise<ServerHealth> => {
  const res = await chattyApi.get<ServerHealth>('/api/chatty/health/server');
  return res.data;
};

// ── Storage Breakdown ───────────────────────────────────────────────────────
export interface StorageEntry {
  path: string;
  path_display: string;
  size_bytes: number;
  depth: number;
  mountpoint: string;
}

export interface StorageBreakdown {
  mountpoints: string[];
  depth: number;
  entries: StorageEntry[];
  timestamp: string;
}

export const fetchStorageBreakdown = async (
  mountpoint?: string,
  depth: number = 1,
): Promise<StorageBreakdown> => {
  const params: Record<string, string | number> = { depth };
  if (mountpoint) params.mountpoint = mountpoint;
  const res = await chattyApi.get<StorageBreakdown>('/api/chatty/health/storage-breakdown', { params });
  return res.data;
};

// ── Token usage ──────────────────────────────────────────────────────────────
export interface TokenUsageByModel {
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  request_count: number;
  estimated_cost_usd: number | null;
}

export interface TokenUsageByDay {
  day: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface TokenUsageSummary {
  range_days: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  request_count: number;
  today_total_tokens: number;
  today_request_count: number;
  total_estimated_cost_usd: number;
  unpriced_model_count: number;
  by_model: TokenUsageByModel[];
  by_day: TokenUsageByDay[];
}

export interface TokenUsageEntry {
  timestamp: string;
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export const fetchTokenUsageSummary = async (days = 30): Promise<TokenUsageSummary> => {
  const res = await chattyApi.get<TokenUsageSummary>('/api/chatty/token-usage/summary', { params: { days } });
  return res.data;
};

export const fetchTokenUsageRecent = async (limit = 50): Promise<TokenUsageEntry[]> => {
  const res = await chattyApi.get<TokenUsageEntry[]>('/api/chatty/token-usage/recent', { params: { limit } });
  return res.data;
};

// ── Video Production ──────────────────────────────────────────────────────
export type VideoJobStatus = 'submitted' | 'generating' | 'completed' | 'failed';
export type VideoResolution = '480p' | '720p' | '1080p' | 'auto';

export interface VideoJob {
  id: string;
  prompt: string;
  duration_seconds: number;
  resolution: string;
  status: VideoJobStatus;
  url: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export const fetchVideoJobs = async (limit = 50): Promise<VideoJob[]> => {
  const res = await chattyApi.get<VideoJob[]>('/api/chatty/video-jobs', { params: { limit } });
  return res.data;
};

export const createVideoJob = async (
  prompt: string,
  durationSeconds = 4,
  resolution: VideoResolution = 'auto',
): Promise<VideoJob> => {
  const res = await chattyApi.post<VideoJob>('/api/chatty/video-jobs', {
    prompt,
    duration_seconds: durationSeconds,
    resolution,
  });
  return res.data;
};

export const getVideoJob = async (jobId: string): Promise<VideoJob> => {
  const res = await chattyApi.get<VideoJob>(`/api/chatty/video-jobs/${jobId}`);
  return res.data;
};

export const deleteVideoJob = async (jobId: string): Promise<void> => {
  await chattyApi.delete(`/api/chatty/video-jobs/${jobId}`);
};

export default chattyApi;

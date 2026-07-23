# Atlas API Reference (for the iOS App)

This document describes the Atlas backend API contract for building a native iOS
client. It covers the REST endpoints, authentication, and the WebSocket chat
protocol, with Swift examples to get an iOS client started quickly.

Source of truth: `chatty_web_server.py` (FastAPI server). The existing web
frontend's client, `order_explorer_site/frontend/src/chattyApi.ts`, implements this
same contract and can be used as a secondary reference.

## 1. Overview

- Framework: FastAPI, served via `uvicorn chatty_web_server:app --host 0.0.0.0 --port 8016`.
- Default port: `8016` (override with the `CHATTY_WEB_PORT` env var on the server).
- CORS: wide open (`*` origins/methods/headers, credentials enabled) — not a
  blocker for a native client, but relevant if you proxy calls through a WKWebView.
- Base URL: there is no `/api` root beyond what's shown below — every route is
  prefixed with `/api/chatty` except the two health checks.

## 2. Authentication

Every route except `/` and `/api/chatty/health` requires an API key.

- REST calls: header `X-API-Key: <key>`.
- WebSocket: query parameter `?api_key=<key>` (headers aren't available for `ws://` handshakes from browsers, so the server accepts it as a query param instead).
- The key is validated against the server's `CHATTY_WEB_API_KEY` env var (default `"changeme"` — make sure a real key is configured before shipping).
- Missing/invalid key → `401`.

Store the key in the iOS Keychain, not `UserDefaults`:

```swift
import Security

enum APIKeyStore {
    private static let service = "com.yourorg.chatty"
    private static let account = "chatty_api_key"

    static func save(_ key: String) {
        let data = Data(key.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
        var attributes = query
        attributes[kSecValueData as String] = data
        SecItemAdd(attributes as CFDictionary, nil)
    }

    static func load() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
}
```

A shared `URLSession` client that attaches the header to every REST request:

```swift
final class ChattyAPIClient {
    static let shared = ChattyAPIClient()
    var baseURL = URL(string: "http://localhost:8016")!

    private func request(_ path: String, method: String = "GET", body: Data? = nil) -> URLRequest {
        var req = URLRequest(url: baseURL.appendingPathComponent(path))
        req.httpMethod = method
        req.httpBody = body
        if body != nil { req.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        if let key = APIKeyStore.load() { req.setValue(key, forHTTPHeaderField: "X-API-Key") }
        return req
    }

    func get<T: Decodable>(_ path: String) async throws -> T {
        let (data, _) = try await URLSession.shared.data(for: request(path))
        return try JSONDecoder().decode(T.self, from: data)
    }

    func send<T: Decodable, B: Encodable>(_ path: String, method: String, body: B) async throws -> T {
        let payload = try JSONEncoder().encode(body)
        let (data, _) = try await URLSession.shared.data(for: request(path, method: method, body: payload))
        return try JSONDecoder().decode(T.self, from: data)
    }

    func delete(_ path: String) async throws {
        _ = try await URLSession.shared.data(for: request(path, method: "DELETE"))
    }
}
```

## 3. REST endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | No | Service info: `{service, status, version}` |
| GET | `/api/chatty/health` | No | `{status, timestamp}` |
| GET | `/api/chatty/notes` | Yes | List notes |
| POST | `/api/chatty/notes` | Yes | Create note |
| PUT | `/api/chatty/notes/{id}` | Yes | Update note |
| DELETE | `/api/chatty/notes/{id}` | Yes | Delete note |
| GET | `/api/chatty/transcriptions?include_archived=` | Yes | List transcriptions (pending only by default) |
| POST | `/api/chatty/transcriptions` | Yes | Submit a new transcription |
| DELETE | `/api/chatty/transcriptions/{id}` | Yes | Delete a pending transcription |
| GET | `/api/chatty/watchlist` | Yes | List watch topics |
| POST | `/api/chatty/watchlist` | Yes | Add watch topic |
| DELETE | `/api/chatty/watchlist/{id}` | Yes | Remove watch topic |
| GET | `/api/chatty/insights?limit=` | Yes | List insights (limit 1–200, default 50) |
| DELETE | `/api/chatty/insights/{id}` | Yes | Delete insight |
| GET | `/api/chatty/reminders` | Yes | List reminders |
| DELETE | `/api/chatty/reminders/{filename}` | Yes | Delete reminder (must be a `.json` filename) |
| GET | `/api/chatty/requests` | Yes | List feature requests |
| POST | `/api/chatty/requests` | Yes | Queue a feature request (processed async) |
| DELETE | `/api/chatty/requests/{id}` | Yes | Delete a request (only if not running) |
| GET | `/api/chatty/memory?days=` | Yes | Memory entries (days 1–90, default 7) |
| GET | `/api/chatty/code/tree?path=` | Yes | Browse code tree (read-only) |
| GET | `/api/chatty/code/file?path=` | Yes | Read a code file's contents |
| GET | `/api/chatty/system` | Yes | Skills/pm2/system status |
| GET | `/api/chatty/sessions` | Yes | List chat sessions |
| GET | `/api/chatty/sessions/{id}` | Yes | Get a session's full message history |
| POST | `/api/chatty/audio` | Yes | Upload a raw audio chunk for transcription (see below) |

There is **no polling**; all real-time behavior goes through the single
WebSocket chat connection described below (chat) or fire-and-forget upload
(audio/transcriptions).

### Transcriptions vs. notes

Transcriptions are a separate resource from notes, purpose-built for the iOS
app: submit raw transcribed text (e.g. from a voice memo, dictated via
`SFSpeechRecognizer`) via `POST /api/chatty/transcriptions`, and atlas's
heartbeat automatically mines every pending transcription on its next cycle,
extracting anything long-term-memory-worthy (preferences, facts, goals,
relationships, recurring topics, insights) into long-term memory. Once mined,
a transcription is archived server-side and drops out of the default
`GET /api/chatty/transcriptions` listing (pass `include_archived=true` to see
it). There's no "update" endpoint for transcriptions — they're a write-once
staging area, not an editable note.

There are two ways a transcription ends up in that queue: the app transcribes
locally (e.g. `SFSpeechRecognizer`) and posts the text directly to
`POST /api/chatty/transcriptions`, or the app uploads raw audio chunks to
`POST /api/chatty/audio` (below) and atlas transcribes them server-side.
Either way, everything downstream (heartbeat mining, archiving) is identical.

### Audio ingestion

For continuous/background recording (e.g. an always-listening mode), upload
short raw audio chunks directly — no local transcription needed. The server
transcribes via a WhisperX STT engine (`STT_ENGINE_URL` in `.env` — see the
[Docker deployment's `whisperx` profile](../README.md#docker-deployment) for
a scaffold, or bring your own), with diarization when speakers are
distinguishable, formats the result, and adds
it to the same pending-transcription queue as above.

**Request:** raw audio bytes as the request body — **not multipart**.

```
POST /api/chatty/audio
Content-Type: audio/mp4          (AAC in an m4a container, 16 kHz mono recommended)
X-API-Key: <key>
X-Device-Id: <uuid>                        — identifies the recording device
X-Chunk-Start: 2026-07-03T21:08:00.000Z    — wall-clock start of the chunk (ISO 8601)
X-Chunk-Duration: 20.00                    — seconds
X-Source: ios_app                          — optional, defaults to "ios_app"

<body = raw m4a bytes>
```

**Response:** `202 Accepted` (`{"accepted": true}`) as soon as the bytes are
received — transcription happens afterward as a background task, so this
returns immediately regardless of how long Whisper takes. A `400` means the
body was empty; a `401` means the API key was wrong. There is currently no
mechanism for the client to learn whether a given chunk's transcription
*succeeded* after the `202` — if the STT engine fails or the audio has no
speech, the chunk is silently dropped rather than appearing as a
transcription. Treat `202` as "durably received," not "successfully mined."

Chunks should arrive in order per device, roughly gapless (~20s each);
`X-Chunk-Start` is what orders/timestamps them server-side (each stored
transcription is prefixed with `[<chunk_start>] (device <id>, <duration>s
audio)`), so the client doesn't need to guarantee strict ordering on the wire.

### Assistant mode (wake-word push)

When the user has assistant mode enabled, send `X-Mode: assistant` on
`POST /api/chatty/audio` chunks:

```
POST /api/chatty/audio
Content-Type: audio/mp4
X-API-Key: <key>
X-Device-Id: <uuid>
X-Chunk-Start: 2026-07-03T21:08:00.000Z
X-Chunk-Duration: 20.00
X-Mode: assistant

<body = raw m4a bytes>
```

The server still runs STT on the chunk as usual, then checks whether the
transcript mentions "atlas" (case-insensitive):

- **No mention:** identical to a non-assistant chunk — transcribed and queued
  for the heartbeat's memory mining, nothing pushed.
- **Mentioned:** the text after the first "atlas" becomes the query (or, if
  nothing follows, the server falls back to recent context/a short
  acknowledgment). Atlas answers it using the same agent/memory context as
  the chat WebSocket, and streams the answer over that device's **open**
  `/api/chatty/chat` connection unprompted — the app never sends a
  `{"message": ...}` frame to trigger it. This chunk is *not* added to the
  transcription/mining queue (the exchange itself is saved to memory the
  same way a normal chat turn is).
- **No open connection for that device** (e.g. app backgrounded): the
  response is dropped silently — no error, nothing retried.

For this to work, the app must identify itself on the **chat WebSocket
handshake** too — add an `X-Device-Id` header (matching the value sent on
`/api/chatty/audio`) when opening the socket, e.g. via a custom `URLRequest`
passed to `URLSession.webSocketTask(with:)` instead of a plain URL. Without
it, the connection still works for interactive chat, it's just unreachable
for proactive pushes.

Pushed frames reuse the `chunk`/`done` types but carry the text under a
`content` key (not `text`, which is reserved for chunks that are replies to
a client-sent message) so the client can tell a push apart from a reply:

```json
{"type": "chunk", "content": "It's "}
{"type": "chunk", "content": "sunny today."}
{"type": "done"}
```

### Swift models

```swift
struct ChattyNote: Codable, Identifiable {
    let id: String
    let content: String
    let created_at: String
    let user_id: String
}

struct ChattyTranscription: Codable, Identifiable {
    let id: String
    let content: String
    let created_at: String
    let user_id: String
    let source: String // e.g. "ios_app"
    let mined: Bool // false until the heartbeat processes it; only present on GET responses
}

enum WatchTopicKind: String, Codable {
    case news, stock, github
}

struct ChattyWatchTopic: Codable, Identifiable {
    let id: String
    let topic: String
    let kind: WatchTopicKind
    let user_id: String
    let created_at: String
    let last_run_at: String?
    let seen_urls: [String]
}

struct ChattyInsightSource: Codable {
    let title: String
    let url: String
}

struct ChattyInsight: Codable, Identifiable {
    let id: String
    let topic: String
    let summary: String
    let sources: [ChattyInsightSource]
    let created_at: String
    let user_id: String
}

// Reminders are free-form JSON blobs; decode as [String: AnyCodable]
// or a dedicated struct once the shape you care about is known.
// `_file` identifies the backing filename (used for delete calls).

enum FeatureRequestStatus: String, Codable {
    case queued, running, testing, completed, error
}

struct FeatureRequest: Codable, Identifiable {
    let id: String
    let prompt: String
    let status: FeatureRequestStatus
    let created_at: String
    let updated_at: String
    let files_changed: [String]
    let log: [String]
    let summary: String
    let source: String // "user" | "self_upgrade"
    let branch: String?
}

struct MemoryEntry: Codable {
    let date: String
    let content: String
    let filename: String
}

struct MemoryData: Codable {
    let short_term: [MemoryEntry]
    let long_term: [MemoryEntry]
}

struct ChatSession: Codable, Identifiable {
    let id: Int
    let first_ts: String
    let last_ts: String
    let message_count: Int
    let summary: String
}

struct ChatMessage: Codable {
    let role: String // "user" | "assistant"
    let content: String
}
```

## 4. WebSocket chat protocol

This is the core interactive feature — sending a message to the agent and
streaming its reply.

**URL:**

```
ws://<host>:8016/api/chatty/chat?api_key=<key>[&session_id=<id>]
```

Use `wss://` if the server is behind TLS. Omit `session_id` to start a new
conversation; pass an existing session's `id` to resume it (the server preloads
history and reports it via `session_loaded`).

Also set an `X-Device-Id` header on the handshake request itself (matching
the value sent on `/api/chatty/audio`) — this is what lets the server find
this connection later for an assistant-mode proactive push (see [Assistant
mode](#assistant-mode-wake-word-push) above). It's optional for plain
interactive chat; without it, the connection just isn't reachable for pushes.

**Client → server:**

```json
{"message": "your question here"}
```

**Server → client**, in order:

1. On connect:
   ```json
   {"type": "session_loaded", "session_id": 123, "message_count": 5}
   ```
2. Zero or more streamed chunks as the agent generates its reply:
   ```json
   {"type": "chunk", "text": "partial response..."}
   ```
3. Terminal event:
   ```json
   {"type": "done"}
   ```
4. Or, at any point, an error instead of/interspersed with the above:
   ```json
   {"type": "error", "text": "error description"}
   ```

Responses are persisted server-side automatically; the full history for a
session is retrievable later via `GET /api/chatty/sessions/{id}`.

**Server → client, unprompted** (assistant mode wake-word push — not a reply
to any client-sent message): the same `chunk`/`done` types, but chunks carry
the text under `content` instead of `text`, so the client can tell a push
apart from a reply to something it sent:

```json
{"type": "chunk", "content": "partial response..."}
{"type": "done"}
```

### Swift example

```swift
import Foundation

enum ChattyWSEvent: Decodable {
    case sessionLoaded(sessionId: Int?, messageCount: Int)
    case chunk(text: String, isPush: Bool) // isPush: true for an unprompted assistant-mode push
    case done
    case error(text: String)

    private enum CodingKeys: String, CodingKey { case type, session_id, message_count, text, content }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        switch try c.decode(String.self, forKey: .type) {
        case "session_loaded":
            self = .sessionLoaded(
                sessionId: try c.decodeIfPresent(Int.self, forKey: .session_id),
                messageCount: try c.decode(Int.self, forKey: .message_count))
        case "chunk":
            // Replies to a client-sent message use "text"; unprompted
            // assistant-mode pushes use "content" instead.
            if let text = try c.decodeIfPresent(String.self, forKey: .text) {
                self = .chunk(text: text, isPush: false)
            } else {
                self = .chunk(text: try c.decode(String.self, forKey: .content), isPush: true)
            }
        case "done":
            self = .done
        case "error":
            self = .error(text: try c.decode(String.self, forKey: .text))
        default:
            throw DecodingError.dataCorruptedError(forKey: .type, in: c, debugDescription: "unknown event type")
        }
    }
}

final class ChattyChatSession {
    private var task: URLSessionWebSocketTask?
    var onEvent: ((ChattyWSEvent) -> Void)?

    func connect(baseURL: URL, apiKey: String, deviceId: String, sessionId: Int? = nil) {
        var components = URLComponents(url: baseURL.appendingPathComponent("api/chatty/chat"),
                                        resolvingAgainstBaseURL: false)!
        components.scheme = baseURL.scheme == "https" ? "wss" : "ws"
        var items = [URLQueryItem(name: "api_key", value: apiKey)]
        if let sessionId { items.append(URLQueryItem(name: "session_id", value: String(sessionId))) }
        components.queryItems = items

        // A plain URL loses the ability to set headers on the handshake, so
        // use a URLRequest instead - this is what lets the server key this
        // connection by device for assistant-mode proactive pushes.
        var request = URLRequest(url: components.url!)
        request.setValue(deviceId, forHTTPHeaderField: "X-Device-Id")

        task = URLSession.shared.webSocketTask(with: request)
        task?.resume()
        listen()
    }

    private func listen() {
        task?.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let message):
                if case .string(let text) = message,
                   let data = text.data(using: .utf8),
                   let event = try? JSONDecoder().decode(ChattyWSEvent.self, from: data) {
                    DispatchQueue.main.async { self.onEvent?(event) }
                }
                self.listen() // keep receiving until done/error/close
            case .failure(let error):
                DispatchQueue.main.async { self.onEvent?(.error(text: error.localizedDescription)) }
            }
        }
    }

    func send(_ message: String) {
        let payload = try! JSONEncoder().encode(["message": message])
        task?.send(.string(String(data: payload, encoding: .utf8)!)) { _ in }
    }

    func close() {
        task?.cancel(with: .goingAway, reason: nil)
    }
}
```

Usage:

```swift
let chat = ChattyChatSession()
chat.onEvent = { event in
    switch event {
    case .sessionLoaded(let sessionId, let count):
        print("resumed session \(sessionId ?? -1) with \(count) messages")
    case .chunk(let text, let isPush):
        if isPush && currentReply.isEmpty {
            // Unprompted assistant-mode push: start a new bubble rather than
            // appending to whatever the user last sent.
            beginNewAssistantBubble()
        }
        currentReply += text // append to the in-progress assistant message
    case .done:
        break // mark message complete, ready for the next send
    case .error(let text):
        print("chat error: \(text)")
    }
}
chat.connect(baseURL: ChattyAPIClient.shared.baseURL, apiKey: apiKey, deviceId: deviceId, sessionId: existingSessionId)
chat.send("What's on my calendar today?")
```

## 5. Typical iOS app flow

1. **Launch:** load the API key from Keychain (prompt for it if absent) →
   `GET /api/chatty/sessions` to populate a conversation list.
2. **Resume a chat:** connect the WebSocket with that session's `id`; the
   `session_loaded` event confirms the resume and gives a message count so the
   UI can show/fetch prior messages via `GET /api/chatty/sessions/{id}`.
3. **Start a new chat:** connect without `session_id`.
4. **Send a message:** WS `send`, accumulate `chunk` text into the pending
   assistant bubble, finalize on `done`.
5. **Secondary screens** (notes, watchlist, insights, reminders, memory,
   system status, code browser, feature requests) are plain REST CRUD — the
   single `ChattyAPIClient` above covers all of them with the same
   `X-API-Key` header.

## 6. Error handling

- REST: `401` on bad/missing API key; treat other non-2xx as generic failures.
- WebSocket: watch for `{"type": "error"}` frames as well as abnormal socket
  closes (network drop, server restart) — surface both to the user and offer
  a reconnect.

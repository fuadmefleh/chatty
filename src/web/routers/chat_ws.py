import asyncio
import contextlib
import json
import time
from typing import Dict, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.web import config, state
from src.web.media_processing import _load_chat_attachment_context

router = APIRouter(tags=["chat_ws"])

# Protocol (client -> server): {"type": "message", "text": ..., "attachment_id": ...}
#                               {"type": "stop"}
#                               {"type": "regenerate"}
#                               {"type": "edit_resend", "text": ...}
# `attachment_id` (optional, "message" only) references a file already
# uploaded via POST /api/chatty/chat/attachments.
# Protocol (server -> client): {"type": "session_loaded", ...}
#                               {"type": "chunk", "text": ...}
#                               {"type": "done", "duration_ms": ...}
#                               {"type": "stopped", "duration_ms": ...}
#                               {"type": "error", "text": ..., "duration_ms": ...}
# `duration_ms` is wall-clock time from when generation started to when it
# finished/stopped/errored, so a client can show how long the response took.
# Proactive push (assistant mode, unprompted - see routers.audio._push_assistant_response):
#                               {"type": "chunk", "content": ...}
#                               {"type": "done"}
_WS_DISCONNECT = object()  # queue sentinel: the websocket has disconnected


@router.websocket("/api/chatty/chat")
async def websocket_chat(websocket: WebSocket, api_key: str = Query(default=""), session_id: str = Query(default="")):
    if api_key != config.API_KEY:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    # Register this connection so the audio pipeline can push a proactive
    # assistant response onto it (assistant mode, wake-word detection). Only
    # devices that send X-Device-Id on the WS handshake are reachable that way.
    device_id = websocket.headers.get("x-device-id") or None
    connection = state._ChatConnection(websocket) if device_id else None
    if connection is not None:
        state._active_chat_connections[device_id] = connection

    async def send_json(payload: dict) -> None:
        if connection is not None:
            await connection.send_json(payload)
        else:
            await websocket.send_text(json.dumps(payload))

    # Import here to avoid circular deps at module load
    from src.agents.web_chat_agent import WebChatAgent
    from src.core.memory import MemoryManager, ConversationHistoryManager

    memory_manager = MemoryManager(config.WEB_USER_ID)
    agent = WebChatAgent(skills_manager=state.skills_manager, memory_manager=memory_manager)

    # Conversation history manager for persistent JSON history
    history_mgr = ConversationHistoryManager(config.WEB_USER_ID)

    # Load session context if a session_id is provided
    active_session_id: Optional[int] = None
    if session_id and session_id.isdigit():
        active_session_id = int(session_id)
        try:
            session_msgs = await history_mgr.get_session(active_session_id)
            if session_msgs:
                # Pre-populate agent history with session messages
                agent._history = session_msgs
        except Exception as e:
            state.logger.error(f"Failed to preload session {active_session_id} for user {config.WEB_USER_ID}: {e}")

    # Notify client of active session
    await send_json({
        "type": "session_loaded",
        "session_id": active_session_id,
        "message_count": len(agent._history) if active_session_id is not None else 0,
    })

    # A dedicated receiver task decouples "read the next frame" from "consume a
    # streaming response", so a control frame (e.g. "stop") can be observed while
    # a generation is in flight. Frames are handed off through a queue; a sentinel
    # marks disconnection so it can flow through the same queue as normal frames.
    queue: "asyncio.Queue" = asyncio.Queue()

    async def receiver():
        try:
            while True:
                raw = await websocket.receive_text()
                await queue.put(raw)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            state.logger.error(f"WS receiver error for user {config.WEB_USER_ID}: {e}")
        finally:
            await queue.put(_WS_DISCONNECT)

    receiver_task = asyncio.create_task(receiver())
    stream_task: Optional[asyncio.Task] = None

    async def run_agent_stream(gen, holder: Dict[str, str]):
        """Forward chunks and accumulate full text. Never sends done/error/stopped itself."""
        async for chunk in gen:
            holder["text"] += chunk
            try:
                await send_json({"type": "chunk", "text": chunk})
            except Exception:
                # Client socket may already be dead; keep generating so the full
                # response still gets persisted even if the client never sees it.
                pass

    async def finalize_stream(
        mode: str, user_text: Optional[str], task: asyncio.Task, holder: Dict[str, str],
        attachment_meta: Optional[Dict] = None,
    ):
        """Await a finished/cancelled/errored stream task, persist, and send exactly
        one control frame. This is the single place that does either, to avoid
        concurrent send_text calls on the same socket."""
        status = "done"
        error_text = None
        try:
            await task
        except asyncio.CancelledError:
            status = "stopped"
        except Exception as e:
            status = "error"
            error_text = str(e)

        duration_ms = int((time.monotonic() - holder["start_time"]) * 1000)

        response_text = holder["text"]
        try:
            if mode == "message":
                await history_mgr.append(user_text, response_text, attachment=attachment_meta)
            elif mode == "regenerate":
                await history_mgr.replace_last_assistant(response_text)
            elif mode == "edit_resend":
                await history_mgr.replace_last_pair(user_text, response_text)
        except Exception as e:
            state.logger.error(f"Failed to persist chat history for user {config.WEB_USER_ID}: {e}")

        try:
            if status == "error":
                await send_json({"type": "error", "text": error_text, "duration_ms": duration_ms})
            elif status == "stopped":
                await send_json({"type": "stopped", "duration_ms": duration_ms})
            else:
                await send_json({"type": "done", "duration_ms": duration_ms})
        except Exception:
            pass

    def start_stream(mode: str, text: Optional[str], attachment_context: Optional[str] = None):
        holder = {"text": "", "start_time": time.monotonic()}
        if mode == "message":
            gen = agent.stream(text, attachment_context=attachment_context)
        elif mode == "regenerate":
            gen = agent.regenerate()
        elif mode == "edit_resend":
            gen = agent.edit_last_user_message(text)
        else:
            return None, None
        return asyncio.create_task(run_agent_stream(gen, holder)), holder

    try:
        while True:
            raw = await queue.get()
            if raw is _WS_DISCONNECT:
                break

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                with contextlib.suppress(Exception):
                    await send_json({"type": "error", "text": "Invalid JSON"})
                continue

            msg_type = data.get("type")
            stream_mode: Optional[str] = None
            stream_user_text: Optional[str] = None
            attachment_context: Optional[str] = None
            attachment_meta: Optional[Dict] = None

            if msg_type == "message":
                text = data.get("text", "").strip()
                attachment_id = (data.get("attachment_id") or "").strip()
                if not text and not attachment_id:
                    continue
                if attachment_id:
                    attachment_context, attachment_meta = await _load_chat_attachment_context(
                        attachment_id, text or None
                    )
                stream_mode, stream_user_text = "message", text or "(sent an attachment)"
            elif msg_type == "regenerate":
                stream_mode, stream_user_text = "regenerate", None
            elif msg_type == "edit_resend":
                text = data.get("text", "").strip()
                if not text:
                    continue
                stream_mode, stream_user_text = "edit_resend", text
            else:
                # "stop" (or anything unrecognized) while idle: nothing to stop, ignore.
                continue

            stream_task, stream_holder = start_stream(stream_mode, stream_user_text, attachment_context)
            if stream_task is None:
                continue

            # Keep consuming frames while this generation is in flight, so a
            # "stop" (or disconnect) can be observed without blocking on the stream.
            while stream_task is not None:
                getter = asyncio.create_task(queue.get())
                done, _pending = await asyncio.wait(
                    {stream_task, getter}, return_when=asyncio.FIRST_COMPLETED
                )

                incoming = None
                if getter in done:
                    incoming = getter.result()
                else:
                    getter.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await getter

                if stream_task in done:
                    # Finalize the completed stream before dispatching whatever
                    # frame just arrived, so a "stop" racing natural completion
                    # becomes a no-op against an idle connection instead of a
                    # lost or misapplied frame.
                    await finalize_stream(stream_mode, stream_user_text, stream_task, stream_holder, attachment_meta)
                    stream_task = None
                    if incoming is not None:
                        await queue.put(incoming)
                    break

                if incoming is _WS_DISCONNECT:
                    stream_task.cancel()
                    await finalize_stream(stream_mode, stream_user_text, stream_task, stream_holder, attachment_meta)
                    stream_task = None
                    await queue.put(_WS_DISCONNECT)
                    break
                elif incoming is not None:
                    try:
                        incoming_data = json.loads(incoming)
                    except json.JSONDecodeError:
                        incoming_data = {}
                    if incoming_data.get("type") == "stop":
                        stream_task.cancel()
                        await finalize_stream(stream_mode, stream_user_text, stream_task, stream_holder, attachment_meta)
                        stream_task = None
                        break
                    # Any other frame type while busy is ignored (not requeued —
                    # requeuing here would busy-loop against the still-running stream).

    except WebSocketDisconnect:
        pass
    finally:
        if device_id and state._active_chat_connections.get(device_id) is connection:
            del state._active_chat_connections[device_id]
        receiver_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await receiver_task
        if stream_task is not None and not stream_task.done():
            stream_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await stream_task

#!/usr/bin/env python3
"""WebSocket relay server for Linux Player watch parties."""

import asyncio
import json
import os
import secrets
import socket
import string
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

try:
    import websockets  # noqa: F401
except ImportError as exc:
    raise RuntimeError(
        "WebSocket support is missing. Install server dependencies with: "
        "python3 -m pip install -r requirements-chat-server.txt"
    ) from exc


INVITE_ALPHABET = string.ascii_uppercase + string.digits


@dataclass
class Participant:
    websocket: WebSocket
    user_id: str
    name: str


@dataclass
class Room:
    code: str
    host_id: str
    participants: Dict[str, Participant] = field(default_factory=dict)
    playback: dict = field(
        default_factory=lambda: {
            "playing": False,
            "position": 0.0,
            "speed": 1.0,
            "media_name": "",
            "media_size": 0,
            "stream_url": "",
            "updated_at": 0.0,
        }
    )


app = FastAPI(title="Linux Player Watch Party Server")
rooms: Dict[str, Room] = {}
rooms_lock = asyncio.Lock()


def local_ipv4_addresses() -> list:
    addresses = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith("127."):
                addresses.add(address)
    except socket.gaierror:
        pass

    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        addresses.add(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    return sorted(addresses)


def new_invite_code() -> str:
    while True:
        code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(6))
        if code not in rooms:
            return code


async def send_json(websocket: WebSocket, payload: dict) -> None:
    await websocket.send_text(json.dumps(payload, ensure_ascii=False))


async def broadcast(room: Room, payload: dict, exclude: Optional[str] = None) -> None:
    stale = []
    message = json.dumps(payload, ensure_ascii=False)
    for user_id, participant in list(room.participants.items()):
        if user_id == exclude:
            continue
        try:
            await participant.websocket.send_text(message)
        except Exception:
            stale.append(user_id)
    for user_id in stale:
        room.participants.pop(user_id, None)


async def broadcast_participants(room: Room) -> None:
    await broadcast(
        room,
        {
            "type": "participants",
            "users": [
                {
                    "id": participant.user_id,
                    "name": participant.name,
                    "is_host": participant.user_id == room.host_id,
                }
                for participant in room.participants.values()
            ],
        },
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "rooms": len(rooms)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    room: Optional[Room] = None
    user_id: Optional[str] = None
    try:
        hello = json.loads(await websocket.receive_text())
        action = hello.get("action")
        name = str(hello.get("name", "")).strip()[:30] or "Anonymous"
        user_id = secrets.token_hex(8)

        async with rooms_lock:
            if action == "create":
                code = new_invite_code()
                room = Room(code=code, host_id=user_id)
                rooms[code] = room
            elif action == "join":
                code = str(hello.get("code", "")).strip().upper()
                room = rooms.get(code)
                if room is None:
                    await send_json(
                        websocket, {"type": "error", "message": "Invite code not found."}
                    )
                    await websocket.close(code=4004)
                    return
            else:
                await send_json(
                    websocket, {"type": "error", "message": "Invalid room action."}
                )
                await websocket.close(code=4000)
                return

            room.participants[user_id] = Participant(websocket, user_id, name)

        await send_json(
            websocket,
            {
                "type": "joined",
                "room": room.code,
                "user_id": user_id,
                "is_host": user_id == room.host_id,
                "playback": room.playback,
            },
        )
        await broadcast(
            room,
            {
                "type": "system",
                "message": f"{name} joined the room.",
                "timestamp": time.time(),
            },
        )
        await broadcast_participants(room)

        while True:
            payload = json.loads(await websocket.receive_text())
            message_type = payload.get("type")
            if message_type == "chat":
                text = str(payload.get("text", "")).strip()[:500]
                if text:
                    await broadcast(
                        room,
                        {
                            "type": "chat",
                            "user_id": user_id,
                            "name": name,
                            "text": text,
                            "timestamp": time.time(),
                        },
                    )
            elif message_type == "playback" and user_id == room.host_id:
                room.playback = {
                    "playing": bool(payload.get("playing")),
                    "position": max(0.0, float(payload.get("position", 0.0))),
                    "speed": min(4.0, max(0.25, float(payload.get("speed", 1.0)))),
                    "media_name": str(payload.get("media_name", ""))[:255],
                    "media_size": max(0, int(payload.get("media_size", 0))),
                    "stream_url": str(payload.get("stream_url", ""))[:2048],
                    "updated_at": time.time(),
                }
                await broadcast(
                    room, {"type": "playback", **room.playback}, exclude=user_id
                )
            elif message_type == "request_state":
                await send_json(websocket, {"type": "playback", **room.playback})
    except (WebSocketDisconnect, json.JSONDecodeError):
        pass
    finally:
        if room is None or user_id is None:
            return
        participant = room.participants.pop(user_id, None)
        if participant:
            await broadcast(
                room,
                {
                    "type": "system",
                    "message": f"{participant.name} left the room.",
                    "timestamp": time.time(),
                },
            )
        if user_id == room.host_id:
            await broadcast(
                room, {"type": "room_closed", "message": "The host closed the room."}
            )
            async with rooms_lock:
                rooms.pop(room.code, None)
        elif room.participants:
            await broadcast_participants(room)


if __name__ == "__main__":
    port = int(os.getenv("WATCH_PARTY_PORT", "8765"))
    print("Watch party server addresses:")
    print(f"  Local machine: ws://127.0.0.1:{port}")
    for address in local_ipv4_addresses():
        print(f"  Other machines: ws://{address}:{port}")
    print("Clients in other VMs must not use 127.0.0.1.")
    uvicorn.run(
        "chat_server:app",
        host=os.getenv("WATCH_PARTY_HOST", "0.0.0.0"),
        port=port,
        ws="websockets",
    )

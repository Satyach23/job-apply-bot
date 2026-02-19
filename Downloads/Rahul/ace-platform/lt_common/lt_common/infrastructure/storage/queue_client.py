"""lt_common - Queue client (SQS or mock in-memory)."""
import asyncio
import json
from typing import Any

from lt_common.config import settings


class QueueClient:
    """Queue client - mock in-memory or real SQS."""

    def __init__(self):
        self._books_queue: asyncio.Queue = asyncio.Queue()
        self._case_queue: asyncio.Queue = asyncio.Queue()

    async def send_books_message(self, body: dict[str, Any]) -> str:
        await self._books_queue.put(body)
        return "mock-msg-id"

    async def send_case_message(self, body: dict[str, Any]) -> str:
        await self._case_queue.put(body)
        return "mock-msg-id"

    async def receive_books_messages(self, max_messages: int = 10) -> list[dict]:
        out = []
        for _ in range(max_messages):
            if self._books_queue.empty():
                break
            try:
                m = self._books_queue.get_nowait()
                out.append(m)
            except asyncio.QueueEmpty:
                break
        return out

    async def receive_case_messages(self, max_messages: int = 10) -> list[dict]:
        out = []
        for _ in range(max_messages):
            if self._case_queue.empty():
                break
            try:
                m = self._case_queue.get_nowait()
                out.append(m)
            except asyncio.QueueEmpty:
                break
        return out

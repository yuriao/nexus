"""
WebSocket consumer for real-time report progress streaming.
Subscribes to Redis pub/sub channel `report:{report_id}` and forwards
all events to the connected browser client.
"""
import asyncio
import json
import logging
import os

import redis.asyncio as aioredis
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class ReportConsumer(AsyncJsonWebsocketConsumer):
    """
    Accepts WebSocket connections at /ws/reports/{report_id}/
    and streams report progress events published to Redis.
    """

    async def connect(self):
        self.report_id = self.scope["url_route"]["kwargs"]["report_id"]
        self.redis_channel = f"report:{self.report_id}"
        self._listener_task: asyncio.Task | None = None

        await self.accept()
        logger.info("WS connected: report=%s", self.report_id)

        # Send an initial ack
        await self.send_json({"type": "connected", "report_id": self.report_id})

        # Start listening to Redis pub/sub in the background
        self._listener_task = asyncio.create_task(self._redis_listener())

    async def disconnect(self, close_code):
        logger.info("WS disconnected: report=%s code=%s", self.report_id, close_code)
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

    async def receive_json(self, content, **kwargs):
        """Handle messages from the client (e.g. ping)."""
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def _redis_listener(self):
        """Subscribe to Redis pub/sub and forward messages to the WebSocket."""
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        try:
            r = await aioredis.from_url(redis_url, decode_responses=True)
            pubsub = r.pubsub()
            await pubsub.subscribe(self.redis_channel)
            logger.debug("Subscribed to Redis channel: %s", self.redis_channel)

            async for raw_message in pubsub.listen():
                if raw_message["type"] != "message":
                    continue
                try:
                    payload = json.loads(raw_message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue

                await self.send_json(payload)

                # Close connection when report is done
                if payload.get("type") in ("report.completed", "report.failed"):
                    await pubsub.unsubscribe(self.redis_channel)
                    await self.close()
                    return

        except asyncio.CancelledError:
            logger.debug("Redis listener cancelled for report=%s", self.report_id)
        except Exception as exc:
            logger.error("Redis listener error for report=%s: %s", self.report_id, exc)
            await self.send_json({"type": "error", "detail": str(exc)})
            await self.close()
        finally:
            try:
                await r.aclose()
            except Exception:
                pass

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class SessionConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for live therapy session rooms.

    Handles real-time text chat and WebRTC signaling for audio/video calls.
    """

    async def connect(self):
        self.room_code = self.scope["url_route"]["kwargs"]["room_code"]
        self.room_group_name = f"session_{self.room_code}"
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        session = await self.get_session()
        if not session:
            await self.close()
            return

        self.session_id = session["id"]

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Notify room that this user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_event",
                "event": "joined",
                "user_id": self.user.id,
                "user_name": self.user.full_name,
            },
        )

    async def disconnect(self, close_code):
        if not hasattr(self, "room_group_name"):
            return
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_event",
                "event": "left",
                "user_id": self.user.id,
                "user_name": self.user.full_name,
            },
        )
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type")

        if msg_type == "chat_message":
            content = data.get("message", "").strip()
            if not content:
                return
            # Persist message to DB
            await self.save_message(content)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": content,
                    "sender_id": self.user.id,
                    "sender_name": self.user.full_name,
                    "timestamp": timezone.now().strftime("%I:%M %p"),
                },
            )

        elif msg_type in (
            "webrtc_offer",
            "webrtc_answer",
            "webrtc_ice_candidate",
            "call_request",
            "call_accept",
            "call_reject",
            "call_end",
        ):
            # Forward WebRTC signaling to the other peer in the room
            await self.channel_layer.group_send(
                self.room_group_name,
                {**data, "from_user_id": self.user.id},
            )

    # ── Group message handlers ──────────────────────────────────────────────

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def user_event(self, event):
        await self.send(text_data=json.dumps(event))

    async def webrtc_offer(self, event):
        # Only forward to the OTHER user (not the sender)
        if event.get("from_user_id") != self.user.id:
            await self.send(text_data=json.dumps(event))

    async def webrtc_answer(self, event):
        if event.get("from_user_id") != self.user.id:
            await self.send(text_data=json.dumps(event))

    async def webrtc_ice_candidate(self, event):
        if event.get("from_user_id") != self.user.id:
            await self.send(text_data=json.dumps(event))

    async def call_request(self, event):
        if event.get("from_user_id") != self.user.id:
            await self.send(text_data=json.dumps(event))

    async def call_accept(self, event):
        if event.get("from_user_id") != self.user.id:
            await self.send(text_data=json.dumps(event))

    async def call_reject(self, event):
        if event.get("from_user_id") != self.user.id:
            await self.send(text_data=json.dumps(event))

    async def call_end(self, event):
        if event.get("from_user_id") != self.user.id:
            await self.send(text_data=json.dumps(event))

    # ── DB helpers ──────────────────────────────────────────────────────────

    @database_sync_to_async
    def get_session(self):
        from .models import TherapySession

        try:
            session = TherapySession.objects.select_related(
                "appointment__patient", "appointment__therapist"
            ).get(room_code=self.room_code)
            apt = session.appointment
            if self.user in (apt.patient, apt.therapist):
                return {"id": session.id}
            return None
        except TherapySession.DoesNotExist:
            return None

    @database_sync_to_async
    def save_message(self, content):
        from .models import TherapySession, SessionMessage

        try:
            session = TherapySession.objects.get(id=self.session_id)
            SessionMessage.objects.create(
                session=session,
                sender=self.user,
                content=content,
            )
        except Exception:
            pass

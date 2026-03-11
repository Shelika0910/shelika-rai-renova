from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r"^ws/session/(?P<room_code>[0-9a-f\-]+)/$",
        consumers.SessionConsumer.as_asgi(),
    ),
]

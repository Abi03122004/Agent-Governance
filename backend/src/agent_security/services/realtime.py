"""Real-time event broadcasting for Dashboard via WebSocket."""

from collections import defaultdict
from datetime import datetime
import json
from typing import Any, Dict, Optional, Set
from fastapi import WebSocket


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)



class ConnectionManager:
    def __init__(self):
        self.org_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.connection_orgs: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, organization_id: str):
        """Accept WebSocket and bind exclusively to the authorized tenant organization."""
        await websocket.accept()
        self.org_connections[organization_id].add(websocket)
        self.connection_orgs[websocket] = organization_id

    def disconnect(self, websocket: WebSocket):
        """Cleanly unbind and disconnect a WebSocket."""
        org_id = self.connection_orgs.pop(websocket, None)
        if org_id and org_id in self.org_connections:
            self.org_connections[org_id].discard(websocket)
            if not self.org_connections[org_id]:
                del self.org_connections[org_id]

    async def broadcast(self, message: dict, organization_id: Optional[str] = None):
        """Broadcast events strictly within tenant isolation boundary."""
        target_org = organization_id or message.get("organization_id")
        if not target_org or target_org not in self.org_connections:
            return

        payload = json.dumps(message, cls=DateTimeEncoder)
        disconnected = []
        for connection in list(self.org_connections[target_org]):
            try:
                await connection.send_text(payload)
            except Exception:
                disconnected.append(connection)

        for dead_conn in disconnected:
            self.disconnect(dead_conn)


ws_manager = ConnectionManager()


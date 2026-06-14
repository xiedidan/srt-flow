"""
WebSocket API for real-time status updates.

Provides WebSocket endpoint for pushing task status and progress updates.
"""
import asyncio
import json
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core import get_logger


router = APIRouter(tags=["WebSocket"])
logger = get_logger("api.websocket")


# ============================================================================
# Connection Manager
# ============================================================================

class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.
    
    Supports broadcasting messages to all connected clients.
    """
    
    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info(f"WebSocket connected. Total: {len(self._connections)}")
    
    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            self._connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")
    
    async def broadcast(self, message: Dict) -> None:
        """Broadcast message to all connected clients."""
        if not self._connections:
            return
        
        data = json.dumps(message)
        disconnected = set()
        
        async with self._lock:
            for connection in self._connections:
                try:
                    await connection.send_text(data)
                except Exception as e:
                    logger.warning(f"Failed to send to client: {e}")
                    disconnected.add(connection)
            
            # Remove disconnected clients
            self._connections -= disconnected

    
    async def send_to_client(self, websocket: WebSocket, message: Dict) -> bool:
        """Send message to a specific client."""
        try:
            await websocket.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.warning(f"Failed to send to client: {e}")
            return False
    
    @property
    def connection_count(self) -> int:
        """Get number of active connections."""
        return len(self._connections)


# Global connection manager instance
manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    return manager


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    """
    WebSocket endpoint for real-time task status updates.
    
    Clients connect to receive:
    - Task status changes (pending -> running -> completed/failed)
    - Task progress updates
    - System notifications
    
    Message format:
    {
        "type": "task_update" | "task_progress" | "notification",
        "data": { ... }
    }
    """
    await manager.connect(websocket)
    
    try:
        # Send welcome message
        await manager.send_to_client(websocket, {
            "type": "connected",
            "data": {"message": "Connected to SRT Flow status stream"}
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages (ping/pong or commands)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # Heartbeat timeout
                )
                
                # Handle client messages
                try:
                    message = json.loads(data)
                    msg_type = message.get("type")
                    
                    if msg_type == "ping":
                        await manager.send_to_client(websocket, {"type": "pong"})
                    elif msg_type == "subscribe":
                        # Future: handle subscription to specific tasks/videos
                        await manager.send_to_client(websocket, {
                            "type": "subscribed",
                            "data": message.get("data", {})
                        })
                    else:
                        logger.debug(f"Unknown message type: {msg_type}")
                        
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {data}")
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await manager.send_to_client(websocket, {"type": "heartbeat"})
                except Exception:
                    break
                    
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await manager.disconnect(websocket)


# ============================================================================
# Broadcast Helper Functions
# ============================================================================

async def broadcast_task_update(
    task_id: str,
    task_type: str,
    status: str,
    video_id: str = None,
    error: str = None,
    result: Dict = None,
) -> None:
    """Broadcast task status update to all clients."""
    await manager.broadcast({
        "type": "task_update",
        "data": {
            "task_id": task_id,
            "task_type": task_type,
            "status": status,
            "video_id": video_id,
            "error": error,
            "result": result,
        }
    })


async def broadcast_task_progress(
    task_id: str,
    progress: int,
    message: str = None,
) -> None:
    """Broadcast task progress update to all clients."""
    await manager.broadcast({
        "type": "task_progress",
        "data": {
            "task_id": task_id,
            "progress": progress,
            "message": message,
        }
    })


async def broadcast_task_metadata(
    task_id: str,
    metadata: dict,
) -> None:
    """Broadcast task metadata update to all clients (e.g., download video info)."""
    await manager.broadcast({
        "type": "task_metadata",
        "data": {
            "task_id": task_id,
            "metadata": metadata,
        }
    })


async def broadcast_notification(
    level: str,
    title: str,
    message: str,
    data: Dict = None,
) -> None:
    """Broadcast system notification to all clients."""
    await manager.broadcast({
        "type": "notification",
        "data": {
            "level": level,  # info, warning, error, success
            "title": title,
            "message": message,
            "extra": data,
        }
    })

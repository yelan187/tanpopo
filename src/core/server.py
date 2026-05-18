from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request

from src.adapters import IncomingEvent
from src.agent import AgentCore
from src.runtime import global_config, register_logger


logger = register_logger("core-http", global_config.log_level)


def create_app(agent_core: AgentCore) -> FastAPI:
    app = FastAPI(title="Tanpopo Core", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"ok": True}

    @app.post("/v1/adapter/message")
    async def adapter_message(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
            event = IncomingEvent.from_dict(body)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid json: {exc}") from exc

        await agent_core.handle_incoming_event(event)
        logger.info(f"接收 adapter 事件[{event.context_id}] type={event.event_type}")
        return {
            "ok": True,
            "context_id": event.context_id,
            "event_type": event.event_type,
        }

    @app.get("/v1/contexts")
    async def list_contexts() -> dict[str, Any]:
        return {"ok": True, "contexts": await agent_core.list_contexts()}

    @app.delete("/v1/contexts/{context_id:path}")
    async def close_context(context_id: str) -> dict[str, Any]:
        closed = await agent_core.close_context(context_id)
        return {"ok": True, "closed": closed, "context_id": context_id}

    @app.post("/v1/contexts/{context_id:path}/reset")
    async def reset_context(context_id: str) -> dict[str, Any]:
        reset = await agent_core.reset_context(context_id)
        return {"ok": True, "reset": reset, "context_id": context_id}

    return app

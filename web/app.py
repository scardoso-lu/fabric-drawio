"""Web viewer for Fabric Architecture Generator — stream agent progress via SSE."""

import asyncio
import json
import os
import queue
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

load_dotenv()

app = FastAPI(title="Fabric Architecture Generator")

_ROOT = Path(__file__).parent.parent
_OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(_ROOT / "output"))).resolve()
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("OUTPUT_DIR", str(_OUTPUT_DIR))

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Prevents multiple concurrent agent runs (the agent uses global sys.stdout redirection)
_agent_lock = threading.Lock()


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (_TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/generate")
async def generate(
    epic_id: int | None = None,
    workspace: str | None = None,
    cross_workspaces: str | None = None,
    llm: str = "claude",
    demo: bool = False,
    state: str = "Active",
    area_path: str | None = None,
) -> StreamingResponse:
    """SSE endpoint — streams log lines then a final 'complete' event with file info."""
    if not demo and epic_id is None:
        raise HTTPException(status_code=422, detail="epic_id is required when not using demo mode")

    cross_ws = [w.strip() for w in cross_workspaces.split(",")] if cross_workspaces else None

    async def event_stream():
        if not _agent_lock.acquire(blocking=False):
            msg = "Another generation is already running. Please wait."
            yield _sse({"type": "error", "text": msg})
            return

        msg_queue: queue.Queue[str | None] = queue.Queue()
        result_holder: list[dict] = []

        def _run() -> None:
            try:
                from agent.llm import make_client
                from agent.main import run

                if demo:
                    from agent.demo import DevOpsClientStub, PurviewClientStub, ScriptedClient

                    devops_client = DevOpsClientStub()
                    purview_client = PurviewClientStub()
                    llm_client = ScriptedClient()
                else:
                    from devops.client import DevOpsClient
                    from purview.client import PurviewClient

                    def _require(var: str) -> str:
                        val = os.getenv(var)
                        if not val:
                            raise OSError(f"Environment variable {var} is not set.")
                        return val

                    devops_client = DevOpsClient(
                        org=_require("AZURE_DEVOPS_ORG"),
                        project=_require("AZURE_DEVOPS_PROJECT"),
                        pat=_require("AZURE_DEVOPS_PAT"),
                    )
                    purview_client = PurviewClient(
                        tenant_id=_require("AZURE_TENANT_ID"),
                        client_id=_require("AZURE_CLIENT_ID"),
                        client_secret=_require("AZURE_CLIENT_SECRET"),
                        account_name=_require("PURVIEW_ACCOUNT_NAME"),
                    )
                    llm_client = make_client(llm)

                class _LineCapture:
                    def __init__(self) -> None:
                        self._buf = ""

                    def write(self, text: str) -> int:
                        self._buf += text
                        while "\n" in self._buf:
                            line, self._buf = self._buf.split("\n", 1)
                            if line.strip():
                                msg_queue.put(_sse({"type": "log", "text": line}))
                        return len(text)

                    def flush(self) -> None:
                        pass

                old_stdout = sys.stdout
                sys.stdout = _LineCapture()
                try:
                    before = set(_OUTPUT_DIR.iterdir())
                    run(
                        epic_id=epic_id,
                        area_path=area_path,
                        state=state,
                        workspace=workspace,
                        cross_workspaces=cross_ws,
                        llm_client=llm_client,
                        devops=devops_client,
                        purview=purview_client,
                    )
                    after = set(_OUTPUT_DIR.iterdir())
                    new_files = sorted(after - before, key=lambda p: p.name)

                    files = []
                    for f in new_files:
                        entry: dict = {"name": f.name, "ext": f.suffix}
                        if f.suffix == ".md":
                            entry["content"] = f.read_text(encoding="utf-8")
                        files.append(entry)
                    result_holder.append({"files": files})
                except Exception as exc:
                    msg_queue.put(_sse({"type": "error", "text": str(exc)}))
                finally:
                    sys.stdout = old_stdout

            except Exception as exc:
                msg_queue.put(_sse({"type": "error", "text": str(exc)}))
            finally:
                msg_queue.put(None)  # sentinel

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        try:
            while True:
                try:
                    item = msg_queue.get_nowait()
                    if item is None:
                        payload: dict = {"type": "complete"}
                        if result_holder:
                            payload.update(result_holder[0])
                        yield _sse(payload)
                        break
                    yield item
                except queue.Empty:
                    yield _sse({"type": "ping"})
                    await asyncio.sleep(0.2)
        finally:
            _agent_lock.release()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/output/{filename}")
async def download(filename: str) -> FileResponse:
    path = (_OUTPUT_DIR / filename).resolve()
    if not path.is_relative_to(_OUTPUT_DIR):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def start() -> None:
    import uvicorn

    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    start()

"""Claude Code CLI communication layer."""

import json
import subprocess
import threading
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class ToolUseInfo:
    tool_name: str
    tool_input: dict


@dataclass
class StreamCallbacks:
    on_token: Callable[[str], None]
    on_tool_use: Callable[[ToolUseInfo], None]
    on_complete: Callable[[str, Optional[float], str], None]
    on_error: Callable[[str], None]
    on_session_init: Callable[[str], None]


class ClaudeCLI:
    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def send_message(
        self,
        message: str,
        project_dir: str,
        callbacks: StreamCallbacks,
        session_id: Optional[str] = None,
        model: str = "sonnet",
    ) -> None:
        if self.is_running:
            return

        self._stop_event.clear()

        cmd = [
            "claude", "-p",
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]

        if model:
            cmd.extend(["--model", model])

        if project_dir:
            cmd.extend(["--cwd", project_dir])

        if session_id:
            cmd.extend(["--resume", session_id])

        cmd.append(message)

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            callbacks.on_error("Claude Code CLI が見つかりません。インストールしてください。")
            return

        self._thread = threading.Thread(
            target=self._read_stream,
            args=(self._proc, callbacks),
            daemon=True,
        )
        self._thread.start()

    def _read_stream(self, proc: subprocess.Popen, callbacks: StreamCallbacks) -> None:
        try:
            for line in proc.stdout:
                if self._stop_event.is_set():
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "")

                if msg_type == "system" and data.get("subtype") == "init":
                    sid = data.get("session_id", "")
                    if sid:
                        callbacks.on_session_init(sid)

                elif msg_type == "content_block_delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            callbacks.on_token(text)

                elif msg_type == "stream_event":
                    event = data.get("event", {})
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                callbacks.on_token(text)

                elif msg_type == "assistant":
                    msg = data.get("message", {})
                    for block in msg.get("content", []):
                        if block.get("type") == "tool_use":
                            info = ToolUseInfo(
                                tool_name=block.get("name", ""),
                                tool_input=block.get("input", {}),
                            )
                            callbacks.on_tool_use(info)
                        elif block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                callbacks.on_token(text)

                elif msg_type == "result":
                    result_text = data.get("result", "")
                    cost = data.get("total_cost_usd")
                    sid = data.get("session_id", "")
                    callbacks.on_complete(result_text, cost, sid)

            stderr = proc.stderr.read()
            if stderr and proc.returncode and proc.returncode != 0:
                callbacks.on_error(stderr.strip())

        except Exception as e:
            callbacks.on_error(str(e))
        finally:
            self._proc = None

    def stop(self) -> None:
        self._stop_event.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

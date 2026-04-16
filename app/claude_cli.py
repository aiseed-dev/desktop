"""Claude Code CLI communication layer.

Handles the stream-json protocol from Claude Code CLI:
  system (subtype=init)  → session initialization
  stream_event           → Claude API streaming events (text, tools, thinking)
  result                 → final completion with cost/token data
"""

import json
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ToolUseInfo:
    tool_name: str
    tool_input: dict
    tool_id: str = ""


@dataclass
class ResultInfo:
    text: str
    session_id: str
    cost_usd: Optional[float] = None
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    stop_reason: str = ""


@dataclass
class StreamCallbacks:
    on_token: Callable[[str], None]
    on_thinking: Callable[[str], None]
    on_tool_start: Callable[[ToolUseInfo], None]
    on_tool_end: Callable[[int], None]
    on_complete: Callable[[ResultInfo], None]
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
        ]

        if model:
            cmd.extend(["--model", model])

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
                cwd=project_dir or None,
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
        # Track active tool blocks by index for input accumulation
        active_tools: dict[int, ToolUseInfo] = {}
        tool_input_buffers: dict[int, str] = {}

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

                # --- system init ---
                if msg_type == "system" and data.get("subtype") == "init":
                    sid = data.get("session_id", "")
                    if sid:
                        callbacks.on_session_init(sid)

                # --- stream_event (main protocol) ---
                elif msg_type == "stream_event":
                    event = data.get("event", {})
                    event_type = event.get("type", "")

                    if event_type == "content_block_start":
                        block = event.get("content_block", {})
                        index = event.get("index", 0)

                        if block.get("type") == "tool_use":
                            info = ToolUseInfo(
                                tool_name=block.get("name", ""),
                                tool_input={},
                                tool_id=block.get("id", ""),
                            )
                            active_tools[index] = info
                            tool_input_buffers[index] = ""
                            callbacks.on_tool_start(info)

                    elif event_type == "content_block_delta":
                        index = event.get("index", 0)
                        delta = event.get("delta", {})
                        delta_type = delta.get("type", "")

                        if delta_type == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                callbacks.on_token(text)

                        elif delta_type == "thinking_delta":
                            thinking = delta.get("thinking", "")
                            if thinking:
                                callbacks.on_thinking(thinking)

                        elif delta_type == "input_json_delta":
                            # Accumulate tool input JSON fragments
                            partial = delta.get("partial_json", "")
                            if index in tool_input_buffers:
                                tool_input_buffers[index] += partial

                    elif event_type == "content_block_stop":
                        index = event.get("index", 0)

                        # Parse accumulated tool input
                        if index in active_tools:
                            buf = tool_input_buffers.pop(index, "")
                            if buf:
                                try:
                                    active_tools[index].tool_input = json.loads(buf)
                                except json.JSONDecodeError:
                                    pass
                            del active_tools[index]

                        callbacks.on_tool_end(index)

                    elif event_type == "error":
                        error = event.get("error", {})
                        msg = error.get("message", str(error))
                        callbacks.on_error(msg)

                # --- result ---
                elif msg_type == "result":
                    info = ResultInfo(
                        text=data.get("result", ""),
                        session_id=data.get("session_id", ""),
                        cost_usd=data.get("total_cost_usd"),
                        input_tokens=data.get("total_input_tokens", 0),
                        output_tokens=data.get("total_output_tokens", 0),
                        duration_ms=data.get("duration_ms", 0),
                        stop_reason=data.get("stop_reason", ""),
                    )
                    callbacks.on_complete(info)

            proc.wait()
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

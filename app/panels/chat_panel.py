"""Chat Panel - Main interaction with Claude Code CLI."""

import flet as ft
from typing import Optional, Callable

from app.claude_cli import ClaudeCLI, StreamCallbacks, ToolUseInfo, ResultInfo
from app.sessions import Session, SessionManager


TOOL_LABELS = {
    "Read": "ファイル読取",
    "Edit": "ファイル編集",
    "Write": "ファイル作成",
    "Bash": "コマンド実行",
    "Glob": "ファイル検索",
    "Grep": "内容検索",
    "WebSearch": "Web検索",
    "WebFetch": "Web取得",
    "Agent": "サブエージェント",
    "TodoWrite": "タスク管理",
    "NotebookEdit": "ノートブック編集",
}


class ChatMessage(ft.Container):
    """A single chat message bubble."""

    def __init__(self, role: str, content: str = "", is_tool: bool = False, is_thinking: bool = False):
        self.role = role
        self._content = content

        if is_thinking:
            bg_color = ft.Colors.with_opacity(0.06, ft.Colors.PURPLE)
            icon = ft.Icons.PSYCHOLOGY_ROUNDED
            text_color = ft.Colors.PURPLE_200
        elif is_tool:
            bg_color = ft.Colors.with_opacity(0.1, ft.Colors.ORANGE)
            icon = ft.Icons.BUILD_ROUNDED
            text_color = ft.Colors.ORANGE_200
        elif role == "user":
            bg_color = ft.Colors.with_opacity(0.15, ft.Colors.BLUE)
            icon = ft.Icons.PERSON_ROUNDED
            text_color = ft.Colors.BLUE_200
        else:
            bg_color = ft.Colors.with_opacity(0.08, ft.Colors.WHITE)
            icon = ft.Icons.SMART_TOY_ROUNDED
            text_color = None

        self.text_control = ft.Text(
            content,
            selectable=True,
            color=text_color,
            size=13 if is_thinking else 14,
            italic=is_thinking,
        )

        self.md_control = ft.Markdown(
            content,
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            code_theme=ft.MarkdownCodeTheme.MONOKAI,
            visible=False,
        )

        super().__init__(
            content=ft.Row(
                [
                    ft.Icon(icon, size=20, color=text_color or ft.Colors.WHITE54),
                    ft.Column(
                        [self.text_control, self.md_control],
                        expand=True,
                        spacing=0,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=10,
            ),
            bgcolor=bg_color,
            border_radius=8,
            padding=ft.padding.all(12),
            margin=ft.margin.only(bottom=4),
        )

    def append_text(self, text: str) -> None:
        self._content += text
        self.text_control.value = self._content

    def finalize_as_markdown(self) -> None:
        """Switch to Markdown rendering for the final message."""
        if "```" in self._content or "#" in self._content or "**" in self._content or "|" in self._content:
            self.md_control.value = self._content
            self.md_control.visible = True
            self.text_control.visible = False


class ToolStatusMessage(ft.Container):
    """A tool use status indicator with spinner."""

    def __init__(self, tool_name: str):
        label = TOOL_LABELS.get(tool_name, tool_name)
        self._label = label
        self._detail = ""

        self.label_text = ft.Text(
            f"{label}...",
            size=13,
            color=ft.Colors.ORANGE_200,
        )

        self.spinner = ft.ProgressRing(
            width=14,
            height=14,
            stroke_width=2,
            color=ft.Colors.ORANGE_300,
        )

        self.done_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE_ROUNDED,
            size=14,
            color=ft.Colors.GREEN_400,
            visible=False,
        )

        super().__init__(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.BUILD_ROUNDED, size=16, color=ft.Colors.ORANGE_200),
                    self.label_text,
                    self.spinner,
                    self.done_icon,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ORANGE),
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            margin=ft.margin.only(bottom=2),
        )

    def set_detail(self, detail: str) -> None:
        self._detail = detail
        self.label_text.value = f"{self._label}: {detail}"

    def mark_done(self) -> None:
        self.spinner.visible = False
        self.done_icon.visible = True
        if self._detail:
            self.label_text.value = f"{self._label}: {self._detail}"
        else:
            self.label_text.value = self._label


class ChatPanel(ft.Column):
    """Chat panel with message list and input."""

    def __init__(
        self,
        cli: ClaudeCLI,
        session_manager: SessionManager,
        get_project_dir: Callable[[], str],
        get_model: Callable[[], str],
        on_session_change: Optional[Callable[[str], None]] = None,
    ):
        self.cli = cli
        self.session_manager = session_manager
        self.get_project_dir = get_project_dir
        self.get_model = get_model
        self.on_session_change = on_session_change

        self.current_session_id: Optional[str] = None
        self._current_message: Optional[ChatMessage] = None
        self._thinking_message: Optional[ChatMessage] = None
        self._active_tools: dict[int, ToolStatusMessage] = {}
        self._page: Optional[ft.Page] = None

        # Message list
        self.message_list = ft.ListView(
            expand=True,
            spacing=4,
            padding=ft.padding.all(12),
            auto_scroll=True,
        )

        # Cost / stats display
        self.cost_text = ft.Text("", size=12, color=ft.Colors.WHITE38)

        # Session selector
        self.session_dropdown = ft.Dropdown(
            label="セッション",
            hint_text="新規会話",
            width=250,
            height=45,
            text_size=13,
            dense=True,
            on_select=self._on_session_selected,
            border_color=ft.Colors.WHITE24,
        )

        # Model selector
        self.model_dropdown = ft.Dropdown(
            value="sonnet",
            width=130,
            height=45,
            text_size=13,
            dense=True,
            border_color=ft.Colors.WHITE24,
            options=[
                ft.dropdown.Option("opus", "Opus"),
                ft.dropdown.Option("sonnet", "Sonnet"),
                ft.dropdown.Option("haiku", "Haiku"),
            ],
        )

        # Input
        self.input_field = ft.TextField(
            hint_text="メッセージを入力...",
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=5,
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.BLUE_400,
            on_submit=self._on_send,
            shift_enter=True,
        )

        self.send_button = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED,
            icon_color=ft.Colors.BLUE_400,
            tooltip="送信 (Enter)",
            on_click=self._on_send,
        )

        self.stop_button = ft.IconButton(
            icon=ft.Icons.STOP_CIRCLE_ROUNDED,
            icon_color=ft.Colors.RED_400,
            tooltip="停止",
            on_click=self._on_stop,
            visible=False,
        )

        self.new_session_button = ft.IconButton(
            icon=ft.Icons.ADD_COMMENT_ROUNDED,
            icon_color=ft.Colors.WHITE54,
            tooltip="新規会話",
            on_click=self._on_new_session,
        )

        # Status indicator
        self.status_text = ft.Text("", size=12, color=ft.Colors.WHITE38, italic=True)

        # Header
        header = ft.Row(
            [
                ft.Icon(ft.Icons.CHAT_ROUNDED, color=ft.Colors.BLUE_400, size=20),
                ft.Text("Chat", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                self.model_dropdown,
                self.session_dropdown,
                self.new_session_button,
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        )

        # Input row
        input_row = ft.Row(
            [self.input_field, self.send_button, self.stop_button],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.END,
        )

        # Status bar
        status_bar = ft.Row(
            [self.status_text, ft.Container(expand=True), self.cost_text],
            spacing=8,
        )

        super().__init__(
            [
                ft.Container(header, padding=ft.padding.only(left=12, right=12, top=8, bottom=4)),
                ft.Divider(height=1, color=ft.Colors.WHITE10),
                self.message_list,
                ft.Divider(height=1, color=ft.Colors.WHITE10),
                ft.Container(
                    ft.Column([input_row, status_bar], spacing=4),
                    padding=ft.padding.all(8),
                ),
            ],
            expand=True,
            spacing=0,
        )

    def did_mount(self):
        self._page = self.page
        self._refresh_session_list()

    def _safe_update(self) -> None:
        try:
            if self._page:
                self._page.update()
        except Exception:
            pass

    def _refresh_session_list(self) -> None:
        sessions = self.session_manager.list_all()
        self.session_dropdown.options = [
            ft.dropdown.Option(
                s.session_id,
                f"{s.name[:30]} (${s.total_cost:.3f})" if s.total_cost else s.name[:40],
            )
            for s in sessions[:20]
        ]
        self._safe_update()

    def _on_session_selected(self, e) -> None:
        sid = e.control.value
        if sid:
            self.current_session_id = sid
            self.message_list.controls.clear()
            session = self.session_manager.get(sid)
            if session:
                self._add_system_message(f"セッション復元: {session.name}")
            self._safe_update()

    def _on_new_session(self, e) -> None:
        self.current_session_id = None
        self.message_list.controls.clear()
        self.session_dropdown.value = None
        self.cost_text.value = ""
        self._add_system_message("新しい会話を開始します")
        self._safe_update()

    def _add_system_message(self, text: str) -> None:
        msg = ft.Container(
            ft.Text(text, size=12, color=ft.Colors.WHITE38, italic=True, text_align=ft.TextAlign.CENTER),
            alignment=ft.alignment.center,
            margin=ft.margin.symmetric(vertical=4),
        )
        self.message_list.controls.append(msg)

    def _on_send(self, e) -> None:
        message = self.input_field.value.strip()
        if not message or self.cli.is_running:
            return

        # Add user message
        user_msg = ChatMessage("user", message)
        self.message_list.controls.append(user_msg)

        # Clear input and state
        self.input_field.value = ""
        self._thinking_message = None
        self._active_tools.clear()

        # Show assistant placeholder
        self._current_message = ChatMessage("assistant", "")
        self.message_list.controls.append(self._current_message)

        # Toggle buttons
        self.send_button.visible = False
        self.stop_button.visible = True
        self.status_text.value = "応答中..."
        self._safe_update()

        callbacks = StreamCallbacks(
            on_token=self._on_token,
            on_thinking=self._on_thinking,
            on_tool_start=self._on_tool_start,
            on_tool_end=self._on_tool_end,
            on_complete=self._on_complete,
            on_error=self._on_error,
            on_session_init=self._on_session_init,
        )

        project_dir = self.get_project_dir()
        model = self.model_dropdown.value or self.get_model()

        self.cli.send_message(
            message=message,
            project_dir=project_dir,
            callbacks=callbacks,
            session_id=self.current_session_id,
            model=model,
        )

    def _on_stop(self, e) -> None:
        self.cli.stop()
        self.status_text.value = "停止しました"
        self._finish_response()

    def _on_token(self, text: str) -> None:
        # End thinking display when real text starts
        if self._thinking_message:
            self._thinking_message = None

        if self._current_message:
            self._current_message.append_text(text)
            self._safe_update()

    def _on_thinking(self, text: str) -> None:
        if self._thinking_message is None:
            self._thinking_message = ChatMessage("assistant", "", is_thinking=True)
            self.message_list.controls.append(self._thinking_message)

        self._thinking_message.append_text(text)
        self.status_text.value = "思考中..."
        self._safe_update()

    def _on_tool_start(self, info: ToolUseInfo) -> None:
        # Finalize current text message before tool display
        if self._current_message and self._current_message._content:
            self._current_message.finalize_as_markdown()
            self._current_message = ChatMessage("assistant", "")
            self.message_list.controls.append(self._current_message)

        tool_status = ToolStatusMessage(info.tool_name)

        # Try to show detail from tool input (name, path, etc.)
        inp = info.tool_input
        if "file_path" in inp:
            tool_status.set_detail(inp["file_path"])
        elif "command" in inp:
            cmd = inp["command"]
            tool_status.set_detail(cmd[:60] + ("..." if len(cmd) > 60 else ""))
        elif "pattern" in inp:
            tool_status.set_detail(inp["pattern"])

        # Track by a simple incrementing key since index resets
        idx = len(self._active_tools)
        self._active_tools[idx] = tool_status
        self.message_list.controls.append(tool_status)

        self.status_text.value = f"ツール実行中: {TOOL_LABELS.get(info.tool_name, info.tool_name)}"
        self._safe_update()

    def _on_tool_end(self, index: int) -> None:
        # Mark the most recent active tool as done
        if self._active_tools:
            last_key = max(self._active_tools.keys())
            tool_status = self._active_tools.get(last_key)
            if tool_status:
                tool_status.mark_done()
                del self._active_tools[last_key]

        self.status_text.value = "応答中..."
        self._safe_update()

    def _on_complete(self, result: ResultInfo) -> None:
        if self._current_message:
            if not self._current_message._content and result.text:
                self._current_message.append_text(result.text)
            self._current_message.finalize_as_markdown()

        # Mark remaining tools as done
        for tool_status in self._active_tools.values():
            tool_status.mark_done()
        self._active_tools.clear()

        session_id = result.session_id

        if session_id and session_id != self.current_session_id:
            self.current_session_id = session_id
            short_text = result.text[:50] if result.text else "会話"
            session = Session(
                session_id=session_id,
                name=short_text,
                project_dir=self.get_project_dir(),
                total_cost=result.cost_usd or 0.0,
                last_message=short_text,
            )
            self.session_manager.add(session)
            self._refresh_session_list()
            self.session_dropdown.value = session_id

        # Build stats display
        stats_parts = []
        if result.cost_usd is not None:
            stats_parts.append(f"${result.cost_usd:.4f}")
        if result.input_tokens or result.output_tokens:
            stats_parts.append(f"in:{result.input_tokens} out:{result.output_tokens}")
        if result.duration_ms:
            secs = result.duration_ms / 1000
            stats_parts.append(f"{secs:.1f}s")

        self.cost_text.value = " | ".join(stats_parts) if stats_parts else ""

        if result.cost_usd is not None:
            self.session_manager.update(session_id, cost=result.cost_usd)

        self.status_text.value = "完了"
        self._finish_response()

    def _on_error(self, error: str) -> None:
        error_msg = ChatMessage("tool", f"エラー: {error}", is_tool=True)
        self.message_list.controls.append(error_msg)
        self.status_text.value = "エラー"
        self._finish_response()

    def _on_session_init(self, session_id: str) -> None:
        self.current_session_id = session_id

    def _finish_response(self) -> None:
        self._current_message = None
        self._thinking_message = None
        self.send_button.visible = True
        self.stop_button.visible = False
        self._safe_update()

    def insert_text(self, text: str) -> None:
        """Insert text into the input field (e.g., file path from File Panel)."""
        current = self.input_field.value or ""
        self.input_field.value = current + text
        self._safe_update()

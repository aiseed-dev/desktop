"""Preview Panel - Markdown/HTML preview and text file editor."""

from pathlib import Path
from typing import Callable, Optional

import flet as ft


class PreviewPanel(ft.Column):
    """Markdown/HTML preview and code editor panel with mode toggle."""

    def __init__(self, on_file_saved: Optional[Callable[[str], None]] = None):
        self._current_file: Optional[str] = None
        self._is_edit_mode = False
        self._is_dirty = False
        self.on_file_saved = on_file_saved

        # File path display
        self.file_path_text = ft.Text(
            "ファイルを選択してください",
            size=12,
            color=ft.Colors.WHITE38,
            italic=True,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
        )

        # Dirty indicator
        self.dirty_indicator = ft.Text(
            "●",
            size=14,
            color=ft.Colors.ORANGE_400,
            visible=False,
            tooltip="未保存の変更があります",
        )

        # Mode toggle button
        self.mode_button = ft.IconButton(
            icon=ft.Icons.EDIT_ROUNDED,
            icon_size=16,
            icon_color=ft.Colors.WHITE54,
            tooltip="編集モードに切替",
            on_click=self._toggle_mode,
        )

        # Save button
        self.save_button = ft.IconButton(
            icon=ft.Icons.SAVE_ROUNDED,
            icon_size=16,
            icon_color=ft.Colors.GREEN_400,
            tooltip="保存 (Ctrl+S)",
            on_click=self._on_save,
            visible=False,
        )

        # --- Preview mode controls ---
        self.markdown_view = ft.Markdown(
            "",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            code_theme=ft.MarkdownCodeTheme.MONOKAI,
            expand=True,
        )

        self.preview_container = ft.Container(
            ft.Column(
                [self.markdown_view],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            expand=True,
            padding=ft.padding.all(12),
        )

        # --- Edit mode controls ---
        self.editor = ft.TextField(
            value="",
            multiline=True,
            expand=True,
            text_size=13,
            text_style=ft.TextStyle(font_family="Courier New, monospace"),
            border_color=ft.Colors.WHITE10,
            focused_border_color=ft.Colors.BLUE_400,
            bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
            color=ft.Colors.WHITE70,
            on_change=self._on_editor_change,
        )

        # Editor status bar
        self.line_count_text = ft.Text("", size=11, color=ft.Colors.WHITE38)
        self.encoding_text = ft.Text("UTF-8", size=11, color=ft.Colors.WHITE38)

        self.editor_status_bar = ft.Container(
            ft.Row(
                [
                    self.line_count_text,
                    ft.Container(expand=True),
                    self.encoding_text,
                ],
                spacing=12,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=2),
            bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
            visible=False,
        )

        self.edit_container = ft.Container(
            self.editor,
            expand=True,
            padding=ft.padding.only(left=4, right=4, bottom=0),
            visible=False,
        )

        # Header
        header = ft.Row(
            [
                ft.Icon(ft.Icons.PREVIEW_ROUNDED, color=ft.Colors.GREEN_400, size=18),
                ft.Text("Preview", size=14, weight=ft.FontWeight.BOLD),
                ft.Container(width=4),
                self.dirty_indicator,
                self.file_path_text,
                self.save_button,
                self.mode_button,
                ft.IconButton(
                    icon=ft.Icons.REFRESH_ROUNDED,
                    icon_size=16,
                    icon_color=ft.Colors.WHITE54,
                    tooltip="再読み込み",
                    on_click=self._on_refresh,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        )

        super().__init__(
            [
                ft.Container(header, padding=ft.padding.only(left=12, right=4, top=4, bottom=4)),
                ft.Divider(height=1, color=ft.Colors.WHITE10),
                self.preview_container,
                self.edit_container,
                self.editor_status_bar,
            ],
            expand=True,
            spacing=0,
        )

    def _safe_update(self) -> None:
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def _toggle_mode(self, e=None) -> None:
        if not self._current_file:
            return

        if self._is_edit_mode:
            # Switch to preview mode
            self._switch_to_preview()
        else:
            # Switch to edit mode
            self._switch_to_edit()
        self._safe_update()

    def _switch_to_preview(self) -> None:
        self._is_edit_mode = False
        self.mode_button.icon = ft.Icons.EDIT_ROUNDED
        self.mode_button.tooltip = "編集モードに切替"
        self.mode_button.icon_color = ft.Colors.WHITE54
        self.save_button.visible = False
        self.edit_container.visible = False
        self.editor_status_bar.visible = False
        self.preview_container.visible = True

        # Refresh preview if there was content in editor
        if self._current_file:
            self._load_preview(self._current_file)

    def _switch_to_edit(self) -> None:
        self._is_edit_mode = True
        self.mode_button.icon = ft.Icons.PREVIEW_ROUNDED
        self.mode_button.tooltip = "プレビューモードに切替"
        self.mode_button.icon_color = ft.Colors.GREEN_400
        self.save_button.visible = True
        self.preview_container.visible = False
        self.edit_container.visible = True
        self.editor_status_bar.visible = True

        # Load file content into editor
        if self._current_file:
            self._load_editor(self._current_file)

    def _load_editor(self, file_path: str) -> None:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            self.editor.value = f"# ファイルを読み込めません: {e}"
            self.editor.read_only = True
            return

        self.editor.value = content
        self.editor.read_only = False
        self._is_dirty = False
        self.dirty_indicator.visible = False

        lines = content.count("\n") + 1
        self.line_count_text.value = f"{lines} 行"

    def _load_preview(self, file_path: str) -> None:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            self.markdown_view.value = f"*ファイルを読み込めません: {e}*"
            return

        ext = Path(file_path).suffix.lower()

        if ext in (".md", ".markdown"):
            self.markdown_view.value = content
        elif ext in (".html", ".htm"):
            self.markdown_view.value = f"```html\n{content}\n```"
        else:
            lang = _get_language(ext)
            self.markdown_view.value = f"```{lang}\n{content}\n```" if lang else f"```\n{content}\n```"

    def load_file(self, file_path: str) -> None:
        self._current_file = file_path
        self.file_path_text.value = file_path
        self.file_path_text.italic = False
        self.file_path_text.color = ft.Colors.WHITE54
        self._is_dirty = False
        self.dirty_indicator.visible = False

        if self._is_edit_mode:
            self._load_editor(file_path)
        else:
            self._load_preview(file_path)

        self._safe_update()

    def _on_editor_change(self, e) -> None:
        if not self._is_dirty:
            self._is_dirty = True
            self.dirty_indicator.visible = True

        # Update line count
        content = self.editor.value or ""
        lines = content.count("\n") + 1
        self.line_count_text.value = f"{lines} 行"
        self._safe_update()

    def _on_save(self, e=None) -> None:
        if not self._current_file or not self._is_dirty:
            return

        content = self.editor.value or ""
        try:
            Path(self._current_file).write_text(content, encoding="utf-8")
            self._is_dirty = False
            self.dirty_indicator.visible = False
            if self.on_file_saved:
                self.on_file_saved(self._current_file)
            self._safe_update()
        except OSError as e:
            if self.page:
                self.page.show_dialog(
                    ft.AlertDialog(
                        title=ft.Text("保存エラー"),
                        content=ft.Text(str(e)),
                    )
                )

    def _on_refresh(self, e=None) -> None:
        if self._current_file:
            self.load_file(self._current_file)

    def save_current(self) -> None:
        """Public save method for keyboard shortcut integration."""
        self._on_save()


def _get_language(ext: str) -> str:
    lang_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "jsx",
        ".tsx": "tsx",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".css": "css",
        ".scss": "scss",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".sql": "sql",
        ".xml": "xml",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".lua": "lua",
        ".r": "r",
        ".md": "markdown",
        ".markdown": "markdown",
        ".html": "html",
        ".htm": "html",
    }
    return lang_map.get(ext, "")

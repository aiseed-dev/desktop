"""Preview Panel - Markdown and HTML preview."""

from pathlib import Path
from typing import Optional

import flet as ft

try:
    from markdown_it import MarkdownIt
    _MD = MarkdownIt("commonmark", {"html": True}).enable("table")
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False


class PreviewPanel(ft.Column):
    """Markdown/HTML preview panel."""

    def __init__(self):
        self._current_file: Optional[str] = None

        # File path display
        self.file_path_text = ft.Text(
            "ファイルを選択してください",
            size=12,
            color=ft.Colors.WHITE38,
            italic=True,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # Markdown rendered view
        self.markdown_view = ft.Markdown(
            "",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            code_theme=ft.MarkdownCodeTheme.MONOKAI,
            expand=True,
        )

        # Raw text view (for non-markdown files)
        self.text_view = ft.TextField(
            value="",
            multiline=True,
            read_only=True,
            expand=True,
            text_size=13,
            border_color=ft.Colors.TRANSPARENT,
            visible=False,
        )

        # Scrollable content area
        self.content_area = ft.Column(
            [self.markdown_view, self.text_view],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        # Header
        header = ft.Row(
            [
                ft.Icon(ft.Icons.PREVIEW_ROUNDED, color=ft.Colors.GREEN_400, size=18),
                ft.Text("Preview", size=14, weight=ft.FontWeight.BOLD),
                ft.Container(width=8),
                self.file_path_text,
                ft.Container(expand=True),
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
                ft.Container(self.content_area, expand=True, padding=ft.padding.all(12)),
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

    def load_file(self, file_path: str) -> None:
        self._current_file = file_path
        self.file_path_text.value = file_path
        self.file_path_text.italic = False
        self.file_path_text.color = ft.Colors.WHITE54

        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            self.markdown_view.value = f"*ファイルを読み込めません: {e}*"
            self.markdown_view.visible = True
            self.text_view.visible = False
            self._safe_update()
            return

        ext = Path(file_path).suffix.lower()

        if ext in (".md", ".markdown"):
            self.markdown_view.value = content
            self.markdown_view.visible = True
            self.text_view.visible = False
        elif ext in (".html", ".htm"):
            self.markdown_view.value = f"```html\n{content}\n```"
            self.markdown_view.visible = True
            self.text_view.visible = False
        else:
            lang = _get_language(ext)
            if lang:
                self.markdown_view.value = f"```{lang}\n{content}\n```"
                self.markdown_view.visible = True
                self.text_view.visible = False
            else:
                self.text_view.value = content
                self.text_view.visible = True
                self.markdown_view.visible = False

        self._safe_update()

    def _on_refresh(self, e=None) -> None:
        if self._current_file:
            self.load_file(self._current_file)


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
    }
    return lang_map.get(ext, "")

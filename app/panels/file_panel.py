"""File Panel - Project file browser and management."""

import os
import subprocess
from pathlib import Path
from typing import Callable, Optional, Set

import flet as ft


# Directories/files to hide in the tree
IGNORE_PATTERNS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".tox", ".eggs",
    "*.pyc", "*.pyo", ".DS_Store", "Thumbs.db",
}


def _should_ignore(name: str) -> bool:
    if name in IGNORE_PATTERNS:
        return True
    for pat in IGNORE_PATTERNS:
        if pat.startswith("*.") and name.endswith(pat[1:]):
            return True
    return False


def _get_file_icon(name: str) -> str:
    ext = Path(name).suffix.lower()
    icons = {
        ".py": ft.Icons.CODE,
        ".js": ft.Icons.JAVASCRIPT,
        ".ts": ft.Icons.JAVASCRIPT,
        ".html": ft.Icons.WEB,
        ".css": ft.Icons.STYLE,
        ".md": ft.Icons.ARTICLE,
        ".json": ft.Icons.DATA_OBJECT,
        ".yaml": ft.Icons.SETTINGS,
        ".yml": ft.Icons.SETTINGS,
        ".toml": ft.Icons.SETTINGS,
        ".txt": ft.Icons.TEXT_SNIPPET,
        ".png": ft.Icons.IMAGE,
        ".jpg": ft.Icons.IMAGE,
        ".jpeg": ft.Icons.IMAGE,
        ".gif": ft.Icons.IMAGE,
        ".webp": ft.Icons.IMAGE,
        ".svg": ft.Icons.IMAGE,
    }
    return icons.get(ext, ft.Icons.INSERT_DRIVE_FILE)


class FilePanel(ft.Column):
    """File tree panel for browsing project files."""

    def __init__(
        self,
        get_project_dir: Callable[[], str],
        on_file_select: Optional[Callable[[str], None]] = None,
        on_path_insert: Optional[Callable[[str], None]] = None,
    ):
        self.get_project_dir = get_project_dir
        self.on_file_select = on_file_select
        self.on_path_insert = on_path_insert
        self._git_modified: Set[str] = set()

        # File tree
        self.tree_view = ft.ListView(
            expand=True,
            spacing=0,
            padding=ft.padding.only(left=4),
        )

        # Header with refresh button
        header = ft.Row(
            [
                ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, color=ft.Colors.AMBER_400, size=20),
                ft.Text("Files", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.REFRESH_ROUNDED,
                    icon_size=18,
                    icon_color=ft.Colors.WHITE54,
                    tooltip="更新",
                    on_click=self._on_refresh,
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        )

        super().__init__(
            [
                ft.Container(header, padding=ft.padding.only(left=12, right=4, top=8, bottom=4)),
                ft.Divider(height=1, color=ft.Colors.WHITE10),
                self.tree_view,
            ],
            expand=True,
            spacing=0,
        )

    def did_mount(self):
        self.refresh_tree()

    def _on_refresh(self, e=None) -> None:
        self.refresh_tree()

    def refresh_tree(self) -> None:
        project_dir = self.get_project_dir()
        if not project_dir or not os.path.isdir(project_dir):
            self.tree_view.controls = [
                ft.Container(
                    ft.Text(
                        "プロジェクトディレクトリを設定してください",
                        size=12,
                        color=ft.Colors.WHITE38,
                        italic=True,
                    ),
                    padding=ft.padding.all(12),
                )
            ]
            self._safe_update()
            return

        self._load_git_status(project_dir)
        self.tree_view.controls.clear()
        self._build_tree(project_dir, self.tree_view.controls, depth=0)
        self._safe_update()

    def _safe_update(self) -> None:
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def _load_git_status(self, project_dir: str) -> None:
        self._git_modified.clear()
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line and len(line) > 3:
                        filepath = line[3:].strip()
                        if " -> " in filepath:
                            filepath = filepath.split(" -> ")[1]
                        self._git_modified.add(filepath)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    def _build_tree(self, dir_path: str, controls: list, depth: int) -> None:
        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        project_dir = self.get_project_dir()

        for entry in entries:
            if _should_ignore(entry.name):
                continue

            rel_path = os.path.relpath(entry.path, project_dir)
            is_modified = rel_path in self._git_modified

            if entry.is_dir():
                self._add_dir_node(entry, controls, depth, is_modified)
            else:
                self._add_file_node(entry, controls, depth, rel_path, is_modified)

    def _add_dir_node(self, entry, controls: list, depth: int, is_modified: bool) -> None:
        children_container = ft.Column(visible=False, spacing=0)

        def toggle_dir(e):
            if not children_container.controls:
                self._build_tree(entry.path, children_container.controls, depth + 1)
            children_container.visible = not children_container.visible
            icon_btn.icon = ft.Icons.FOLDER_OPEN_ROUNDED if children_container.visible else ft.Icons.FOLDER_ROUNDED
            self._safe_update()

        icon_btn = ft.Icon(ft.Icons.FOLDER_ROUNDED, size=16, color=ft.Colors.AMBER_400)

        name_text = ft.Text(
            entry.name,
            size=13,
            color=ft.Colors.ORANGE_300 if is_modified else ft.Colors.WHITE70,
        )

        row = ft.Container(
            ft.Row(
                [icon_btn, name_text],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=depth * 16 + 4, top=2, bottom=2, right=4),
            on_click=toggle_dir,
            ink=True,
            border_radius=4,
        )

        controls.append(row)
        controls.append(children_container)

    def _add_file_node(self, entry, controls: list, depth: int, rel_path: str, is_modified: bool) -> None:
        icon = _get_file_icon(entry.name)

        def on_click(e):
            if self.on_file_select:
                self.on_file_select(entry.path)

        def on_insert_path(e):
            if self.on_path_insert:
                self.on_path_insert(rel_path)

        name_color = ft.Colors.ORANGE_300 if is_modified else ft.Colors.WHITE70
        mod_indicator = ft.Text("M", size=10, color=ft.Colors.ORANGE_300) if is_modified else ft.Container()

        row = ft.Container(
            ft.Row(
                [
                    ft.Icon(icon, size=16, color=ft.Colors.WHITE38),
                    ft.Text(entry.name, size=13, color=name_color, expand=True),
                    mod_indicator,
                    ft.IconButton(
                        icon=ft.Icons.CONTENT_COPY_ROUNDED,
                        icon_size=14,
                        icon_color=ft.Colors.WHITE24,
                        tooltip="パスをChatに挿入",
                        on_click=lambda e: on_insert_path(e),
                        width=28,
                        height=28,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=depth * 16 + 4, top=1, bottom=1, right=4),
            on_click=on_click,
            ink=True,
            border_radius=4,
        )

        controls.append(row)

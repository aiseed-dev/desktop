"""File Panel - Project file browser and management."""

import os
import shutil
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
        self._expanded_dirs: Set[str] = set()  # Track which dirs are open

        # File tree
        self.tree_view = ft.ListView(
            expand=True,
            spacing=0,
            padding=ft.padding.only(left=4),
        )

        # Header with action buttons
        header = ft.Row(
            [
                ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, color=ft.Colors.AMBER_400, size=20),
                ft.Text("Files", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.CREATE_NEW_FOLDER_ROUNDED,
                    icon_size=16,
                    icon_color=ft.Colors.WHITE54,
                    tooltip="新規フォルダ",
                    on_click=self._on_new_folder,
                ),
                ft.IconButton(
                    icon=ft.Icons.NOTE_ADD_ROUNDED,
                    icon_size=16,
                    icon_color=ft.Colors.WHITE54,
                    tooltip="新規ファイル",
                    on_click=self._on_new_file,
                ),
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
            spacing=2,
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
                self.update()
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
        dir_path = entry.path
        is_expanded = dir_path in self._expanded_dirs

        children_container = ft.Column(visible=is_expanded, spacing=0)

        # Pre-build children if already expanded
        if is_expanded:
            self._build_tree(dir_path, children_container.controls, depth + 1)

        def toggle_dir(e):
            if dir_path in self._expanded_dirs:
                self._expanded_dirs.discard(dir_path)
                children_container.visible = False
                children_container.controls.clear()
            else:
                self._expanded_dirs.add(dir_path)
                children_container.controls.clear()
                self._build_tree(dir_path, children_container.controls, depth + 1)
                children_container.visible = True
            icon_btn.icon = ft.Icons.FOLDER_OPEN_ROUNDED if children_container.visible else ft.Icons.FOLDER_ROUNDED
            arrow.icon = ft.Icons.EXPAND_MORE_ROUNDED if children_container.visible else ft.Icons.CHEVRON_RIGHT_ROUNDED
            self._safe_update()

        arrow_icon = ft.Icons.EXPAND_MORE_ROUNDED if is_expanded else ft.Icons.CHEVRON_RIGHT_ROUNDED
        folder_icon = ft.Icons.FOLDER_OPEN_ROUNDED if is_expanded else ft.Icons.FOLDER_ROUNDED

        arrow = ft.Icon(arrow_icon, size=14, color=ft.Colors.WHITE38)
        icon_btn = ft.Icon(folder_icon, size=16, color=ft.Colors.AMBER_400)

        name_text = ft.Text(
            entry.name,
            size=13,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.ORANGE_300 if is_modified else ft.Colors.WHITE70,
        )

        row = ft.Container(
            ft.Row(
                [arrow, icon_btn, name_text],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(left=depth * 16 + 4, top=6, bottom=6, right=8),
            on_click=toggle_dir,
            on_long_press=lambda e, path=entry.path, name=entry.name: self._show_context_menu(path, name, is_dir=True),
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
                    ft.Container(width=14),  # align with folder arrow
                    ft.Icon(icon, size=16, color=ft.Colors.WHITE38),
                    ft.Text(entry.name, size=13, color=name_color, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
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
            padding=ft.padding.only(left=depth * 16 + 4, top=5, bottom=5, right=8),
            on_click=on_click,
            on_long_press=lambda e, path=entry.path, name=entry.name: self._show_context_menu(path, name, is_dir=False),
            border_radius=4,
        )

        controls.append(row)

    # --- File operations ---

    def _on_new_file(self, e=None) -> None:
        project_dir = self.get_project_dir()
        if not project_dir:
            return
        self._show_name_dialog(
            title="新規ファイル",
            hint="ファイル名 (例: src/main.py)",
            on_submit=lambda name: self._create_file(os.path.join(project_dir, name)),
        )

    def _on_new_folder(self, e=None) -> None:
        project_dir = self.get_project_dir()
        if not project_dir:
            return
        self._show_name_dialog(
            title="新規フォルダ",
            hint="フォルダ名 (例: src/utils)",
            on_submit=lambda name: self._create_folder(os.path.join(project_dir, name)),
        )

    def _create_file(self, path: str) -> None:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            Path(path).touch()
            self.refresh_tree()
            if self.on_file_select:
                self.on_file_select(path)
        except OSError as e:
            self._show_error(f"ファイル作成に失敗: {e}")

    def _create_folder(self, path: str) -> None:
        try:
            os.makedirs(path, exist_ok=True)
            self.refresh_tree()
        except OSError as e:
            self._show_error(f"フォルダ作成に失敗: {e}")

    def _rename_item(self, old_path: str, new_name: str) -> None:
        new_path = os.path.join(os.path.dirname(old_path), new_name)
        try:
            os.rename(old_path, new_path)
            self.refresh_tree()
        except OSError as e:
            self._show_error(f"リネームに失敗: {e}")

    def _delete_item(self, path: str, is_dir: bool) -> None:
        try:
            if is_dir:
                shutil.rmtree(path)
            else:
                os.remove(path)
            self.refresh_tree()
        except OSError as e:
            self._show_error(f"削除に失敗: {e}")

    def _show_context_menu(self, path: str, name: str, is_dir: bool) -> None:
        if not self.page:
            return

        def on_rename(e):
            self.page.pop_dialog()
            self._show_name_dialog(
                title="リネーム",
                hint="新しい名前",
                initial_value=name,
                on_submit=lambda new_name: self._rename_item(path, new_name),
            )

        def on_delete(e):
            self.page.pop_dialog()
            self._show_confirm_dialog(
                title="削除確認",
                message=f"「{name}」を削除しますか？\nこの操作は取り消せません。",
                on_confirm=lambda: self._delete_item(path, is_dir),
            )

        def on_copy_path(e):
            self.page.pop_dialog()
            if self.on_path_insert:
                project_dir = self.get_project_dir()
                rel = os.path.relpath(path, project_dir)
                self.on_path_insert(rel)

        dialog = ft.AlertDialog(
            title=ft.Text(name, size=14),
            content=ft.Column(
                [
                    ft.TextButton(
                        "リネーム",
                        icon=ft.Icons.DRIVE_FILE_RENAME_OUTLINE,
                        on_click=on_rename,
                    ),
                    ft.TextButton(
                        "削除",
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        on_click=on_delete,
                        style=ft.ButtonStyle(color=ft.Colors.RED_400),
                    ),
                    ft.TextButton(
                        "パスをChatに挿入",
                        icon=ft.Icons.CONTENT_COPY_ROUNDED,
                        on_click=on_copy_path,
                    ),
                ],
                tight=True,
                spacing=0,
            ),
            actions=[ft.TextButton("閉じる", on_click=lambda e: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)

    def _show_name_dialog(self, title: str, hint: str, on_submit: Callable, initial_value: str = "") -> None:
        if not self.page:
            return

        name_field = ft.TextField(
            value=initial_value,
            hint_text=hint,
            autofocus=True,
            expand=True,
        )

        def submit(e):
            val = name_field.value.strip()
            if val:
                self.page.pop_dialog()
                on_submit(val)

        name_field.on_submit = submit

        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Container(name_field, width=400),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda e: self.page.pop_dialog()),
                ft.ElevatedButton("作成", on_click=submit),
            ],
        )
        self.page.show_dialog(dialog)

    def _show_confirm_dialog(self, title: str, message: str, on_confirm: Callable) -> None:
        if not self.page:
            return

        def confirm(e):
            self.page.pop_dialog()
            on_confirm()

        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda e: self.page.pop_dialog()),
                ft.ElevatedButton(
                    "削除",
                    on_click=confirm,
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.RED_700,
                ),
            ],
        )
        self.page.show_dialog(dialog)

    def _show_error(self, message: str) -> None:
        if not self.page:
            return
        dialog = ft.AlertDialog(
            title=ft.Text("エラー"),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=lambda e: self.page.pop_dialog())],
        )
        self.page.show_dialog(dialog)

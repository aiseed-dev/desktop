"""Main Flet application - Claude Code GUI."""

import asyncio
import threading

import flet as ft

from app.claude_cli import ClaudeCLI
from app.config import AppConfig
from app.file_watcher import FileWatcher
from app.sessions import SessionManager
from app.panels.chat_panel import ChatPanel
from app.panels.file_panel import FilePanel
from app.panels.image_panel import ImagePanel
from app.panels.preview_panel import PreviewPanel
from app.panels.build_panel import BuildPanel


class SettingsDialog(ft.AlertDialog):
    """Settings dialog for app configuration."""

    def __init__(self, config: AppConfig, on_save):
        self.config = config
        self._on_save_callback = on_save

        self.project_dir_field = ft.TextField(
            label="プロジェクトディレクトリ",
            value=config.project_dir,
            expand=True,
        )
        self.model_field = ft.Dropdown(
            label="デフォルトモデル",
            value=config.model,
            options=[
                ft.dropdown.Option("opus", "Opus"),
                ft.dropdown.Option("sonnet", "Sonnet"),
                ft.dropdown.Option("haiku", "Haiku"),
            ],
            width=200,
        )
        self.build_cmd_field = ft.TextField(
            label="ビルドコマンド",
            value=config.build_command,
            expand=True,
        )
        self.deploy_cmd_field = ft.TextField(
            label="デプロイコマンド",
            value=config.deploy_command,
            expand=True,
        )
        self.image_dir_field = ft.TextField(
            label="画像ディレクトリ",
            value=config.image_dir,
            width=300,
        )
        self.image_max_width_field = ft.TextField(
            label="画像最大幅",
            value=str(config.image_max_width),
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.image_format_field = ft.Dropdown(
            label="画像形式",
            value=config.image_format,
            options=[
                ft.dropdown.Option("webp", "WebP"),
                ft.dropdown.Option("png", "PNG"),
                ft.dropdown.Option("jpg", "JPEG"),
            ],
            width=150,
        )

        super().__init__(
            title=ft.Text("設定"),
            content=ft.Container(
                ft.Column(
                    [
                        self.project_dir_field,
                        ft.Row([self.model_field], spacing=12),
                        self.build_cmd_field,
                        self.deploy_cmd_field,
                        ft.Row(
                            [self.image_dir_field, self.image_max_width_field, self.image_format_field],
                            spacing=12,
                        ),
                    ],
                    spacing=16,
                    tight=True,
                ),
                width=600,
            ),
            actions=[
                ft.TextButton("キャンセル", on_click=self._on_cancel),
                ft.ElevatedButton("保存", on_click=self._do_save),
            ],
        )

    def _on_cancel(self, e) -> None:
        if self.page:
            self.page.pop_dialog()

    def _do_save(self, e) -> None:
        self.config.project_dir = self.project_dir_field.value or ""
        self.config.model = self.model_field.value or "sonnet"
        self.config.build_command = self.build_cmd_field.value or ""
        self.config.deploy_command = self.deploy_cmd_field.value or ""
        self.config.image_dir = self.image_dir_field.value or "images"
        try:
            self.config.image_max_width = int(self.image_max_width_field.value)
        except (ValueError, TypeError):
            pass
        self.config.image_format = self.image_format_field.value or "webp"
        self.config.save()
        if self.page:
            self.page.pop_dialog()
        self._on_save_callback()


def create_app(page: ft.Page) -> None:
    """Main entry point for the Flet app."""
    # Load config
    config = AppConfig.load()

    # Page setup
    page.title = "Flet Claude Code"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#1a1a2e"
    page.window.width = config.window_width
    page.window.height = config.window_height
    page.padding = 0
    page.spacing = 0

    # Core services
    cli = ClaudeCLI()
    session_manager = SessionManager()
    file_watcher = FileWatcher()

    # Getters
    def get_project_dir() -> str:
        return config.project_dir

    def get_model() -> str:
        return config.model

    def get_image_dir() -> str:
        return config.image_dir

    def get_max_width() -> int:
        return config.image_max_width

    def get_image_format() -> str:
        return config.image_format

    def get_build_command() -> str:
        return config.build_command

    def get_deploy_command() -> str:
        return config.deploy_command

    # Preview panel
    preview_panel = PreviewPanel()

    # Build panel
    build_panel = BuildPanel(
        get_project_dir=get_project_dir,
        get_build_command=get_build_command,
        get_deploy_command=get_deploy_command,
    )

    # Chat panel
    chat_panel = ChatPanel(
        cli=cli,
        session_manager=session_manager,
        get_project_dir=get_project_dir,
        get_model=get_model,
    )

    # File panel
    file_panel = FilePanel(
        get_project_dir=get_project_dir,
        on_file_select=lambda path: preview_panel.load_file(path),
        on_path_insert=lambda path: chat_panel.insert_text(path),
    )

    # Image panel
    image_panel = ImagePanel(
        get_project_dir=get_project_dir,
        get_image_dir=get_image_dir,
        get_max_width=get_max_width,
        get_image_format=get_image_format,
        on_image_insert=lambda text: chat_panel.insert_text(text),
    )

    # File watcher callbacks
    def on_file_changed(changed_path: str):
        """Called by watchdog when a file changes in the project directory."""
        file_panel.refresh_tree()
        # Auto-reload preview if the changed file is currently displayed
        if preview_panel._current_file == changed_path:
            if not preview_panel._is_edit_mode or not preview_panel._is_dirty:
                preview_panel.load_file(changed_path)
        # Refresh images if change is in image dir
        image_dir = image_panel._get_full_image_dir()
        if image_dir and changed_path.startswith(image_dir):
            image_panel.refresh_images()

    file_watcher.add_callback(on_file_changed)

    # Start watcher if project dir is set
    def start_watcher():
        project_dir = get_project_dir()
        if project_dir:
            file_watcher.start(project_dir)

    start_watcher()

    # Settings dialog
    def open_settings(e):
        dialog = SettingsDialog(config, on_save=on_settings_saved)
        page.show_dialog(dialog)

    def on_settings_saved():
        file_panel.refresh_tree()
        image_panel.refresh_images()
        chat_panel.model_dropdown.value = config.model
        # Restart watcher with new project dir
        start_watcher()
        page.update()

    # Folder picker
    folder_picker = ft.FilePicker()
    page.overlay.append(folder_picker)

    def pick_folder(e):
        def do_pick():
            result = folder_picker.get_directory_path(
                dialog_title="プロジェクトディレクトリを選択"
            )
            if result:
                config.project_dir = result
                config.save()
                project_dir_text.value = result
                file_panel.refresh_tree()
                image_panel.refresh_images()
                start_watcher()
                page.update()

        threading.Thread(target=do_pick, daemon=True).start()

    # Top bar
    project_dir_text = ft.Text(
        config.project_dir or "プロジェクト未設定",
        size=12,
        color=ft.Colors.WHITE54,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
        expand=True,
    )

    top_bar = ft.Container(
        ft.Row(
            [
                ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=ft.Colors.BLUE_400, size=22),
                ft.Text("Flet Claude Code", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Container(width=16),
                ft.Icon(ft.Icons.FOLDER_ROUNDED, color=ft.Colors.AMBER_400, size=16),
                project_dir_text,
                ft.IconButton(
                    icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                    icon_size=18,
                    icon_color=ft.Colors.WHITE54,
                    tooltip="プロジェクトを開く",
                    on_click=pick_folder,
                ),
                ft.IconButton(
                    icon=ft.Icons.SETTINGS_ROUNDED,
                    icon_size=18,
                    icon_color=ft.Colors.WHITE54,
                    tooltip="設定",
                    on_click=open_settings,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        bgcolor="#16162a",
        padding=ft.padding.symmetric(horizontal=12, vertical=6),
    )

    # Bottom panel - manual tab switching
    bottom_tab_content = ft.Container(expand=True)
    bottom_tab_content.content = preview_panel

    def switch_bottom_tab(index: int):
        if index == 0:
            bottom_tab_content.content = preview_panel
        else:
            bottom_tab_content.content = build_panel
        page.update()

    bottom_tab_bar = ft.Row(
        [
            ft.TextButton(
                "Preview / Editor",
                icon=ft.Icons.PREVIEW_ROUNDED,
                on_click=lambda e: switch_bottom_tab(0),
            ),
            ft.TextButton(
                "Build",
                icon=ft.Icons.BUILD_ROUNDED,
                on_click=lambda e: switch_bottom_tab(1),
            ),
        ],
        spacing=4,
    )

    bottom_panel = ft.Column(
        [
            ft.Container(bottom_tab_bar, padding=ft.padding.only(left=8, top=4, bottom=2)),
            ft.Divider(height=1, color=ft.Colors.WHITE10),
            bottom_tab_content,
        ],
        expand=True,
        spacing=0,
    )

    # Main layout
    main_content = ft.Column(
        [
            top_bar,
            ft.Row(
                [
                    # Left: File Panel
                    ft.Container(
                        file_panel,
                        width=250,
                        bgcolor="#16162a",
                        border=ft.Border.only(right=ft.BorderSide(1, ft.Colors.WHITE10)),
                    ),
                    # Center: Chat Panel
                    ft.Container(
                        chat_panel,
                        expand=True,
                        bgcolor="#1a1a2e",
                    ),
                    # Right: Image Panel
                    ft.Container(
                        image_panel,
                        width=250,
                        bgcolor="#16162a",
                        border=ft.Border.only(left=ft.BorderSide(1, ft.Colors.WHITE10)),
                    ),
                ],
                expand=3,
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            # Bottom: Preview/Editor / Build
            ft.Container(
                bottom_panel,
                height=250,
                bgcolor="#16162a",
                border=ft.Border.only(top=ft.BorderSide(1, ft.Colors.WHITE10)),
            ),
        ],
        expand=True,
        spacing=0,
    )

    page.add(main_content)

    # Keyboard shortcut: Ctrl+S to save
    def on_keyboard(e: ft.KeyboardEvent):
        if e.ctrl and e.key == "S":
            preview_panel.save_current()

    page.on_keyboard_event = on_keyboard

    # Handle window close
    async def on_close(e):
        cli.stop()
        file_watcher.stop()
        config.window_width = int(page.window.width or 1400)
        config.window_height = int(page.window.height or 900)
        config.save()
        await page.window.destroy()

    page.window.prevent_close = True
    page.window.on_event = on_close

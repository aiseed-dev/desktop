"""Image Panel - Image management and Claude integration."""

import os
import shutil
import threading
from pathlib import Path
from typing import Callable, Optional

import flet as ft

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff"}


class ImagePanel(ft.Column):
    """Image management panel with thumbnails and drag-drop support."""

    def __init__(
        self,
        get_project_dir: Callable[[], str],
        get_image_dir: Callable[[], str],
        on_image_insert: Optional[Callable[[str], None]] = None,
    ):
        self.get_project_dir = get_project_dir
        self.get_image_dir = get_image_dir
        self.on_image_insert = on_image_insert

        # Thumbnail grid
        self.image_grid = ft.ListView(
            expand=True,
            spacing=4,
            padding=ft.padding.all(8),
        )

        # Header
        header = ft.Row(
            [
                ft.Icon(ft.Icons.IMAGE_ROUNDED, color=ft.Colors.PURPLE_400, size=20),
                ft.Text("Images", size=16, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.ADD_PHOTO_ALTERNATE_ROUNDED,
                    icon_size=18,
                    icon_color=ft.Colors.WHITE54,
                    tooltip="画像を追加",
                    on_click=self._on_add_image,
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
            spacing=4,
        )

        super().__init__(
            [
                ft.Container(header, padding=ft.padding.only(left=12, right=4, top=8, bottom=4)),
                ft.Divider(height=1, color=ft.Colors.WHITE10),
                self.image_grid,
            ],
            expand=True,
            spacing=0,
        )

    def did_mount(self):
        self.refresh_images()

    def _safe_update(self) -> None:
        try:
            if self.page:
                self.page.update()
        except Exception:
            pass

    def _on_refresh(self, e=None) -> None:
        self.refresh_images()

    def _on_add_image(self, e) -> None:
        if not self.page:
            return

        def pick():
            fp = ft.FilePicker()
            self.page.overlay.append(fp)
            self.page.update()
            files = fp.pick_files(
                allowed_extensions=["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"],
                allow_multiple=True,
                dialog_title="画像を追加",
            )
            self.page.overlay.remove(fp)
            self.page.update()
            if files:
                self._import_files(files)

        threading.Thread(target=pick, daemon=True).start()

    def _import_files(self, files: list) -> None:
        image_dir = self._get_full_image_dir()
        if not image_dir:
            return

        os.makedirs(image_dir, exist_ok=True)

        for f in files:
            src = f.path
            if src:
                dst = os.path.join(image_dir, os.path.basename(src))
                try:
                    shutil.copy2(src, dst)
                except (shutil.SameFileError, OSError):
                    pass

        self.refresh_images()

    def _get_full_image_dir(self) -> Optional[str]:
        project_dir = self.get_project_dir()
        image_dir = self.get_image_dir()
        if not project_dir:
            return None
        if os.path.isabs(image_dir):
            return image_dir
        return os.path.join(project_dir, image_dir)

    def refresh_images(self) -> None:
        self.image_grid.controls.clear()

        image_dir = self._get_full_image_dir()
        if not image_dir or not os.path.isdir(image_dir):
            self.image_grid.controls.append(
                ft.Container(
                    ft.Text("画像ディレクトリが見つかりません", size=12, color=ft.Colors.WHITE38, italic=True),
                    padding=ft.padding.all(12),
                )
            )
            self._safe_update()
            return

        project_dir = self.get_project_dir()
        images = []

        for entry in sorted(os.scandir(image_dir), key=lambda e: e.name.lower()):
            if entry.is_file() and Path(entry.name).suffix.lower() in IMAGE_EXTENSIONS:
                images.append(entry)

        if not images:
            self.image_grid.controls.append(
                ft.Container(
                    ft.Text("画像がありません", size=12, color=ft.Colors.WHITE38, italic=True),
                    padding=ft.padding.all(12),
                )
            )
            self._safe_update()
            return

        for entry in images:
            rel_path = os.path.relpath(entry.path, project_dir)
            self.image_grid.controls.append(
                self._create_image_tile(entry.path, entry.name, rel_path)
            )

        self._safe_update()

    def _create_image_tile(self, abs_path: str, name: str, rel_path: str) -> ft.Container:
        def on_click(e):
            if self.on_image_insert:
                self.on_image_insert(f"この画像を見て: {abs_path}")

        def on_copy_md(e):
            if self.page:
                md_text = f"![{name}]({rel_path})"
                self.page.clipboard = md_text
                self.page.update()

        try:
            thumbnail = ft.Image(
                src=abs_path,
                width=200,
                height=120,
                fit=ft.ImageFit.COVER,
                border_radius=6,
            )
        except Exception:
            thumbnail = ft.Container(
                ft.Icon(ft.Icons.BROKEN_IMAGE, color=ft.Colors.WHITE24),
                width=200,
                height=120,
                alignment=ft.alignment.center,
            )

        return ft.Container(
            ft.Column(
                [
                    thumbnail,
                    ft.Row(
                        [
                            ft.Text(name, size=11, color=ft.Colors.WHITE54, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.IconButton(
                                icon=ft.Icons.CONTENT_COPY_ROUNDED,
                                icon_size=14,
                                icon_color=ft.Colors.WHITE38,
                                tooltip="Markdownパスをコピー",
                                on_click=on_copy_md,
                                width=26,
                                height=26,
                            ),
                        ],
                        spacing=2,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=on_click,
            ink=True,
            border_radius=8,
            padding=ft.padding.all(6),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
        )

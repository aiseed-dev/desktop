"""Image Panel - Image management, resize, WebP conversion and Claude integration."""

import os
import shutil
from pathlib import Path
from typing import Callable, Optional

import flet as ft

try:
    from PIL import Image as PILImage
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff"}


def resize_and_convert(
    src_path: str,
    dst_path: str,
    max_width: int = 1200,
    fmt: str = "webp",
    quality: int = 85,
) -> str:
    """Resize image to max_width and convert to target format. Returns output path."""
    if not HAS_PILLOW:
        shutil.copy2(src_path, dst_path)
        return dst_path

    img = PILImage.open(src_path)

    # Convert RGBA to RGB for JPEG
    if fmt in ("jpg", "jpeg") and img.mode == "RGBA":
        bg = PILImage.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg

    # Resize if wider than max_width
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), PILImage.LANCZOS)

    # Determine output path with correct extension
    ext_map = {"webp": ".webp", "png": ".png", "jpg": ".jpg", "jpeg": ".jpg"}
    target_ext = ext_map.get(fmt, f".{fmt}")
    stem = Path(dst_path).stem
    out_path = str(Path(dst_path).with_name(stem + target_ext))

    save_fmt = fmt.upper()
    if save_fmt == "JPG":
        save_fmt = "JPEG"

    img.save(out_path, format=save_fmt, quality=quality)
    return out_path


def get_image_info(path: str) -> str:
    """Get image dimensions and file size."""
    try:
        size_kb = os.path.getsize(path) / 1024
        if HAS_PILLOW:
            img = PILImage.open(path)
            return f"{img.width}x{img.height} | {size_kb:.0f} KB"
        else:
            return f"{size_kb:.0f} KB"
    except Exception:
        return ""


class ImagePanel(ft.Column):
    """Image management panel with thumbnails, resize, and WebP conversion."""

    def __init__(
        self,
        get_project_dir: Callable[[], str],
        get_image_dir: Callable[[], str],
        get_max_width: Callable[[], int],
        get_image_format: Callable[[], str],
        on_image_insert: Optional[Callable[[str], None]] = None,
    ):
        self.get_project_dir = get_project_dir
        self.get_image_dir = get_image_dir
        self.get_max_width = get_max_width
        self.get_image_format = get_image_format
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
                    tooltip="画像を追加（リサイズ＆変換）",
                    on_click=self._on_add_image,
                ),
                ft.IconButton(
                    icon=ft.Icons.PHOTO_SIZE_SELECT_LARGE_ROUNDED,
                    icon_size=18,
                    icon_color=ft.Colors.WHITE54,
                    tooltip="全画像を一括リサイズ＆変換",
                    on_click=self._on_batch_convert,
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

    async def _on_add_image(self, e) -> None:
        if not self.page:
            return

        try:
            fp = ft.FilePicker()
            self.page.services.append(fp)
            files = await fp.pick_files(
                allowed_extensions=["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"],
                allow_multiple=True,
                dialog_title="画像を追加",
            )
            if files:
                self._import_files(files)
        except Exception:
            # Fallback: text input for image path (e.g. when Zenity is not installed on Linux)
            self._show_image_path_dialog()

    def _show_image_path_dialog(self) -> None:
        if not self.page:
            return

        path_field = ft.TextField(
            hint_text="画像ファイルのパス (例: /home/user/photo.png)",
            autofocus=True,
            expand=True,
        )

        def submit(e):
            val = (path_field.value or "").strip()
            if val and os.path.isfile(val):
                self.page.pop_dialog()

                class FakeFile:
                    def __init__(self, p):
                        self.path = p
                self._import_files([FakeFile(val)])

        path_field.on_submit = submit

        dialog = ft.AlertDialog(
            title=ft.Text("画像ファイルのパスを入力"),
            content=ft.Container(path_field, width=500),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda e: self.page.pop_dialog()),
                ft.ElevatedButton("追加", on_click=submit),
            ],
        )
        self.page.show_dialog(dialog)

    def _import_files(self, files: list) -> None:
        image_dir = self._get_full_image_dir()
        if not image_dir:
            return

        os.makedirs(image_dir, exist_ok=True)
        max_width = self.get_max_width()
        fmt = self.get_image_format()

        for f in files:
            src = f.path
            if not src:
                continue

            dst = os.path.join(image_dir, os.path.basename(src))

            # Skip SVG (can't be processed by Pillow)
            if Path(src).suffix.lower() == ".svg":
                try:
                    shutil.copy2(src, dst)
                except (shutil.SameFileError, OSError):
                    pass
                continue

            try:
                resize_and_convert(src, dst, max_width=max_width, fmt=fmt)
            except Exception:
                # Fallback: just copy
                try:
                    shutil.copy2(src, dst)
                except (shutil.SameFileError, OSError):
                    pass

        self.refresh_images()

    def _on_batch_convert(self, e) -> None:
        """Convert all images in the image directory to the configured format."""
        if not HAS_PILLOW:
            if self.page:
                self.page.show_dialog(ft.AlertDialog(
                    title=ft.Text("エラー"),
                    content=ft.Text("Pillow がインストールされていません。\npip install Pillow"),
                ))
            return

        image_dir = self._get_full_image_dir()
        if not image_dir or not os.path.isdir(image_dir):
            return

        max_width = self.get_max_width()
        fmt = self.get_image_format()
        converted = 0

        for entry in os.scandir(image_dir):
            if not entry.is_file():
                continue
            ext = Path(entry.name).suffix.lower()
            if ext not in IMAGE_EXTENSIONS or ext == ".svg":
                continue

            target_ext = {"webp": ".webp", "png": ".png", "jpg": ".jpg", "jpeg": ".jpg"}.get(fmt, f".{fmt}")
            if ext == target_ext:
                # Check if resize needed
                try:
                    img = PILImage.open(entry.path)
                    if img.width <= max_width:
                        continue
                except Exception:
                    continue

            try:
                out_path = resize_and_convert(entry.path, entry.path, max_width=max_width, fmt=fmt)
                # Remove original if extension changed
                if out_path != entry.path and os.path.exists(entry.path):
                    os.remove(entry.path)
                converted += 1
            except Exception:
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
            info = get_image_info(entry.path)
            self.image_grid.controls.append(
                self._create_image_tile(entry.path, entry.name, rel_path, info)
            )

        self._safe_update()

    def _create_image_tile(self, abs_path: str, name: str, rel_path: str, info: str) -> ft.Container:
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
                            ft.Column(
                                [
                                    ft.Text(name, size=11, color=ft.Colors.WHITE54, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Text(info, size=9, color=ft.Colors.WHITE24) if info else ft.Container(),
                                ],
                                spacing=0,
                                expand=True,
                            ),
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

"""Build Panel - Build execution, Git operations, and deploy."""

import shlex
import subprocess
import threading
from typing import Callable, Optional, Union

import flet as ft


class BuildPanel(ft.Column):
    """Build and deployment panel with log output."""

    def __init__(
        self,
        get_project_dir: Callable[[], str],
        get_build_command: Callable[[], str],
        get_deploy_command: Callable[[], str],
    ):
        self.get_project_dir = get_project_dir
        self.get_build_command = get_build_command
        self.get_deploy_command = get_deploy_command
        self._proc: Optional[subprocess.Popen] = None

        # Log output
        self.log_output = ft.TextField(
            value="",
            multiline=True,
            read_only=True,
            expand=True,
            text_size=12,
            border_color=ft.Colors.TRANSPARENT,
            color=ft.Colors.GREEN_200,
            bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
        )

        # Custom command input
        self.cmd_input = ft.TextField(
            hint_text="コマンドを入力...",
            expand=True,
            text_size=13,
            height=40,
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.GREEN_400,
            on_submit=self._on_run_custom,
        )

        # Git commit message input
        self.commit_msg_input = ft.TextField(
            hint_text="コミットメッセージ",
            expand=True,
            text_size=13,
            height=40,
            border_color=ft.Colors.WHITE24,
            focused_border_color=ft.Colors.GREEN_400,
        )

        # Header
        header = ft.Row(
            [
                ft.Icon(ft.Icons.BUILD_ROUNDED, color=ft.Colors.TEAL_400, size=18),
                ft.Text("Build", size=14, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.CLEAR_ALL_ROUNDED,
                    icon_size=16,
                    icon_color=ft.Colors.WHITE54,
                    tooltip="ログクリア",
                    on_click=self._on_clear_log,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        )

        # Action buttons
        build_btn = ft.ElevatedButton(
            "Build",
            icon=ft.Icons.BUILD_ROUNDED,
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.TEAL_700,
            on_click=self._on_build,
        )
        deploy_btn = ft.ElevatedButton(
            "Deploy",
            icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.BLUE_700,
            on_click=self._on_deploy,
        )

        # Git buttons
        git_status_btn = ft.OutlinedButton(
            "Status",
            icon=ft.Icons.INFO_OUTLINE_ROUNDED,
            on_click=self._on_git_status,
        )
        git_add_btn = ft.OutlinedButton(
            "Add All",
            icon=ft.Icons.ADD_ROUNDED,
            on_click=self._on_git_add,
        )
        git_commit_btn = ft.OutlinedButton(
            "Commit",
            icon=ft.Icons.CHECK_ROUNDED,
            on_click=self._on_git_commit,
        )
        git_push_btn = ft.OutlinedButton(
            "Push",
            icon=ft.Icons.UPLOAD_ROUNDED,
            on_click=self._on_git_push,
        )

        self.stop_btn = ft.IconButton(
            icon=ft.Icons.STOP_CIRCLE_ROUNDED,
            icon_color=ft.Colors.RED_400,
            tooltip="停止",
            on_click=self._on_stop,
            visible=False,
        )

        button_row = ft.Row(
            [build_btn, deploy_btn, ft.VerticalDivider(width=1), git_status_btn, git_add_btn, git_commit_btn, git_push_btn, self.stop_btn],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )

        # Custom command row
        cmd_row = ft.Row(
            [
                self.cmd_input,
                ft.IconButton(
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    icon_color=ft.Colors.GREEN_400,
                    tooltip="実行",
                    on_click=self._on_run_custom,
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # Commit message row
        commit_row = ft.Row(
            [self.commit_msg_input],
            spacing=4,
        )

        super().__init__(
            [
                ft.Container(header, padding=ft.padding.only(left=12, right=4, top=4, bottom=4)),
                ft.Divider(height=1, color=ft.Colors.WHITE10),
                ft.Container(
                    ft.Column([button_row, commit_row, cmd_row], spacing=6),
                    padding=ft.padding.only(left=8, right=8, top=6, bottom=4),
                ),
                ft.Divider(height=1, color=ft.Colors.WHITE10),
                ft.Container(self.log_output, expand=True, padding=ft.padding.all(4)),
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

    def _append_log(self, text: str) -> None:
        current = self.log_output.value or ""
        self.log_output.value = current + text + "\n"
        self._safe_update()

    def _run_command(self, cmd: Union[str, list[str]], label: str = "") -> None:
        project_dir = self.get_project_dir()
        if not project_dir:
            self._append_log("[ERROR] プロジェクトディレクトリが設定されていません")
            return

        if self._proc and self._proc.poll() is None:
            self._append_log("[WARN] 別のコマンドが実行中です")
            return

        use_shell = isinstance(cmd, str)
        display = cmd if use_shell else shlex.join(cmd)

        if label:
            self._append_log(f"--- {label} ---")
        self._append_log(f"$ {display}")
        self.stop_btn.visible = True
        self._safe_update()

        def run():
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    shell=use_shell,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=project_dir,
                    bufsize=1,
                )
                for line in self._proc.stdout:
                    self._append_log(line.rstrip())
                self._proc.wait()
                rc = self._proc.returncode
                self._append_log(f"[exit code: {rc}]")
            except Exception as e:
                self._append_log(f"[ERROR] {e}")
            finally:
                self._proc = None
                self.stop_btn.visible = False
                self._safe_update()

        threading.Thread(target=run, daemon=True).start()

    def _on_build(self, e) -> None:
        cmd = self.get_build_command()
        if cmd:
            self._run_command(cmd, "Build")
        else:
            self._append_log("[ERROR] ビルドコマンドが設定されていません。設定画面で設定してください。")

    def _on_deploy(self, e) -> None:
        cmd = self.get_deploy_command()
        if cmd:
            self._run_command(cmd, "Deploy")
        else:
            self._append_log("[ERROR] デプロイコマンドが設定されていません。設定画面で設定してください。")

    def _on_git_status(self, e) -> None:
        self._run_command(["git", "status"], "Git Status")

    def _on_git_add(self, e) -> None:
        self._run_command(["git", "add", "-A"], "Git Add All")

    def _on_git_commit(self, e) -> None:
        msg = self.commit_msg_input.value
        if not msg:
            self._append_log("[ERROR] コミットメッセージを入力してください")
            return
        self._run_command(["git", "commit", "-m", msg], "Git Commit")
        self.commit_msg_input.value = ""
        self._safe_update()

    def _on_git_push(self, e) -> None:
        self._run_command(["git", "push"], "Git Push")

    def _on_run_custom(self, e) -> None:
        cmd = self.cmd_input.value
        if cmd:
            self._run_command(cmd.strip())
            self.cmd_input.value = ""
            self._safe_update()

    def _on_stop(self, e) -> None:
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            self._append_log("[STOPPED]")

    def _on_clear_log(self, e) -> None:
        self.log_output.value = ""
        self._safe_update()

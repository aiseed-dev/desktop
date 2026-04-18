# Flet Claude Code

Claude Code CLI の GUI ラッパーアプリケーション。

Claude Code が持つ全機能（ファイル編集、Git、ビルド、Web検索等）をそのまま活用し、
GUI は「チャット表示」と「ファイル・画像管理」に専念します。

## スクリーンショット

```
┌───────────┬────────────────────────────────┬───────────┐
│           │                                │           │
│   File    │         Chat Panel             │   Image   │
│   Panel   │                                │   Panel   │
│           │  ┌──────────────────────────┐  │           │
│  [tree]   │  │ streaming text...        │  │  [thumb]  │
│           │  │ 🔧 ツール実行中...       │  │  [thumb]  │
│           │  │ 🧠 思考中...             │  │  [thumb]  │
│           │  └──────────────────────────┘  │           │
│           │  ┌──────────────────────────┐  │           │
│           │  │ [message input]  [Send]  │  │           │
│           │  └──────────────────────────┘  │           │
├───────────┴────────────────────────────────┴───────────┤
│  [Preview / Editor] [Build]                            │
│  Markdown preview / Code editor / Build output         │
└────────────────────────────────────────────────────────┘
```

## 必要なもの

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) がインストール済みで認証済みであること

## インストール

```bash
git clone https://github.com/aiseed-dev/desktop.git
cd desktop
pip install -r requirements.txt
```

## 起動

```bash
python main.py
```

初回起動時は設定画面（右上の歯車アイコン）またはフォルダアイコンからプロジェクトディレクトリを指定してください。

## 機能

### Chat Panel（中央）

- Claude Code CLI とのリアルタイムストリーミング対話
- 思考過程（thinking）の表示
- ツール使用のライフサイクル表示（スピナー → 完了チェック）
- コスト・トークン数・所要時間の表示
- セッション保存・復元（`--resume`）
- モデル切替（Opus / Sonnet / Haiku）

### File Panel（左）

- プロジェクトのディレクトリツリー表示
- Git 変更ファイルのマーカー表示（M）
- ファイル新規作成・フォルダ作成
- リネーム・削除（長押しでコンテキストメニュー）
- ファイルパスを Chat に挿入
- ファイル選択で Preview に表示

### Image Panel（右）

- プロジェクト内画像のサムネイル一覧
- 画像追加時に自動リサイズ・WebP 変換（Pillow）
- 全画像の一括変換
- 画像サイズ・解像度の表示
- クリックで Chat に画像分析依頼を挿入
- Markdown パスのクリップボードコピー

### Preview / Editor Panel（下部タブ1）

- Markdown プレビュー（GitHub Flavored Markdown）
- コードファイルのシンタックスハイライト表示
- 編集モード切替（プレビュー ↔ エディタ）
- モノスペースエディタ、行数表示、未保存インジケーター
- Ctrl+S で保存
- watchdog によるライブリロード

### Build Panel（下部タブ2）

- ビルド・デプロイコマンドの実行
- Git 操作（status / add / commit / push）
- カスタムコマンド実行
- リアルタイムログ出力

## 設定

設定は `~/.flet-claude/config.json` に保存されます。

```json
{
  "project_dir": "/home/user/my-project",
  "model": "sonnet",
  "theme": "dark",
  "build_command": "python tools/build.py",
  "deploy_command": "rsync -avz dist/ server:/var/www/",
  "image_dir": "images",
  "image_max_width": 1200,
  "image_format": "webp"
}
```

API キー管理は不要です。Claude Code CLI が認証を処理します。

## 技術スタック

| 用途 | ライブラリ |
|---|---|
| GUI | [Flet](https://flet.dev/) |
| 画像処理 | [Pillow](https://pillow.readthedocs.io/) |
| Markdown | [markdown-it-py](https://github.com/executablebooks/markdown-it-py) |
| ファイル監視 | [watchdog](https://github.com/gorakhargosh/watchdog) |
| CLI 通信 | subprocess（標準ライブラリ） |

## アーキテクチャ

```
Flet App
  │
  ├── subprocess.Popen(["claude", "-p", ...])
  │     ├── --output-format stream-json
  │     ├── --verbose
  │     ├── --include-partial-messages
  │     ├── --cwd <project_dir>
  │     ├── --resume <session_id>
  │     └── --model opus|sonnet|haiku
  │
  └── stdout を1行ずつ JSON parse → Chat Panel に表示
```

AI の頭脳は全て Claude Code CLI が提供します。
このアプリが実装するのは「表示」と「ファイル・画像の管理 UI」だけです。

## 同梱ツール: aiseed_web ビルダー

`aiseed_web/` は [aiseed-web](https://github.com/aiseed-dev/aiseed-web) 静的サイトの
ビルダー。テンプレート・既定スタイル・検索スクリプト・Python ツールを同梱する。

データ(content / data / images)は別リポジトリ `aiseed-web/` に置き、
ビルド時に `--site <aiseed-web パス>` で指定する。詳細は
[aiseed_web/README.md](./aiseed_web/README.md) 参照。

```bash
python aiseed_web/tools/build.py --site /path/to/aiseed-web
python aiseed_web/tools/serve.py --site /path/to/aiseed-web
python aiseed_web/tools/optimize_images.py --site /path/to/aiseed-web
```

## ライセンス

[GPL-3.0](LICENSE)

# Flet Claude Code GUI — 仕様書

## 概要

Claude Code CLI のGUIラッパー。
Claude Code が持つ全機能（ファイル編集、Git、ビルド、Web検索等）をそのまま活用し、
GUIは「チャット表示」と「ファイル・画像管理」に専念する。

**基本原則**: AIとの対話は全て Claude Code CLI に委譲。自前実装はGUIだけ。

---

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│                    Flet GUI (Python)                     │
├─────────────┬──────────────────────────┬────────────────┤
│  File Panel │      Chat Panel          │  Image Panel   │
│  (Python    │  (claude CLI subprocess) │  (Python       │
│   標準)     │                          │   標準)        │
├─────────────┴──────────────────────────┴────────────────┤
│  Preview / Build (タブ切替)  — Python 標準               │
└─────────────────────────────────────────────────────────┘
```

Claude Code CLI との通信:
```
Flet App
  │
  ├── subprocess.Popen(["claude", "-p", ...])
  │     ├── --output-format stream-json
  │     ├── --verbose
  │     ├── --include-partial-messages  (リアルタイム表示)
  │     ├── --cwd <project_dir>
  │     ├── --resume <session_id>       (会話継続)
  │     └── --model opus|sonnet|haiku
  │
  └── stdout を1行ずつ JSON parse → Chat Panel に表示
```

---

## CLI 通信プロトコル

### 新規会話

```python
proc = subprocess.Popen(
    [
        "claude", "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--cwd", project_dir,
        message
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
```

### 会話継続

```python
proc = subprocess.Popen(
    [
        "claude", "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--resume", session_id,
        message
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
```

### ストリーミング JSON の処理

stdout から1行ずつ読み、JSON parse:

```python
import json
import threading

def read_stream(proc, on_token, on_complete):
    """Claude Code CLI の stream-json 出力を処理"""
    for line in proc.stdout:
        data = json.loads(line)

        match data["type"]:
            # 初期化 — session_id を保存
            case "system" if data.get("subtype") == "init":
                session_id = data["session_id"]

            # テキストの断片（リアルタイム表示用）
            case "stream_event":
                event = data["event"]
                if event["type"] == "content_block_delta":
                    delta = event["delta"]
                    if delta["type"] == "text_delta":
                        on_token(delta["text"])

            # ツール使用イベント（ファイル編集等の通知）
            case "assistant":
                msg = data["message"]
                for block in msg.get("content", []):
                    if block["type"] == "tool_use":
                        # ファイル編集・Bash実行等をUIに反映
                        handle_tool_use(block)

            # 完了
            case "result":
                on_complete(
                    text=data["result"],
                    cost=data.get("total_cost_usd"),
                    session_id=data["session_id"],
                )

# 別スレッドで実行（GUI をブロックしない）
thread = threading.Thread(target=read_stream, args=(proc, on_token, on_complete))
thread.start()
```

---

## パネル構成

### 1. Chat Panel（中央・メイン）

**役割**: Claude Code CLI との対話表示

- テキスト入力欄 + 送信ボタン
- ストリーミング表示（token 単位でリアルタイム）
- Markdown レンダリング（コードブロック、テーブル等）
- ツール使用の表示（「ファイル編集中: path/to/file」等）
- コスト表示（result の total_cost_usd）
- セッション一覧・切替（session_id で resume）
- モデル切替（opus / sonnet / haiku）

**画像送信**:
```
ユーザーが画像をドラッグ&ドロップ
  → プロジェクトの images/ に保存
  → メッセージに「この画像を見て: {path}」を自動挿入
  → Claude Code の Read ツールが画像を認識
```

### 2. File Panel（左）

**役割**: プロジェクトファイルの管理（Python標準ライブラリ）

- ディレクトリツリー表示
- ファイル選択 → Preview Panel に表示
- 新規ファイル作成・リネーム・削除
- Git ステータス表示（変更ファイルにマーク）
- ファイルパスをクリック → Chat にパスを挿入

**実装**: `os.walk()`, `pathlib`, `watchdog`（ファイル変更監視）

### 3. Image Panel（右）

**役割**: 画像ファイルの管理と Claude への送信

- プロジェクト内画像のサムネイル一覧
- プレビュー表示
- ドラッグ&ドロップで追加
- 画像クリック → Chat Panel にパス挿入（Claudeに分析依頼）
- リサイズ・WebP 変換（Pillow）
- Markdown 用パス生成（`![alt](images/name.webp)` をクリップボードにコピー）

**実装**: `Pillow`, `shutil`

### 4. Preview Panel（下部・タブ1）

**役割**: Markdown / HTML のプレビュー

- Markdown 表示（カスタムブロック対応: `:::chain`, `:::highlight`, `:::quote`, `:::compare`）
- File Panel でファイル選択 → 即座にプレビュー
- HTML プレビュー（build 後の出力確認）
- ライブリロード（ファイル変更を watchdog で検知）

**実装**: `markdown-it-py` + カスタムプラグイン（既存の build_article.py のパーサーを再利用）

### 5. Build Panel（下部・タブ2）

**役割**: ビルド・デプロイ操作

- `python tools/build_article.py` 実行ボタン
- ビルドログ表示
- Git 操作: commit, push, status
- デプロイコマンド実行
- 出力はリアルタイムストリーミング

**実装**: `subprocess.Popen` でコマンド実行、stdout/stderr をリアルタイム表示

---

## データ構造

### セッション管理

```python
@dataclass
class Session:
    session_id: str          # Claude Code の session_id
    name: str                # 表示名
    project_dir: str         # プロジェクトディレクトリ
    created_at: datetime
    last_message: str        # 最後のメッセージ（プレビュー用）
    total_cost: float        # 累計コスト
```

セッション情報は `~/.flet-claude/sessions.json` に保存。
Claude Code 側のセッション永続化（`--resume`）と連携。

### 設定

```python
# ~/.flet-claude/config.json
{
    "project_dir": "/home/user/website",
    "model": "opus",
    "theme": "dark",
    "build_command": "python tools/build_article.py",
    "deploy_command": "rsync -avz html/ server:/var/www/",
    "image_dir": "html/images",
    "image_max_width": 1200,
    "image_format": "webp"
}
```

API キー管理は不要 — Claude Code CLI が認証を処理。

---

## 技術スタック

| 用途 | ライブラリ |
|---|---|
| GUI | flet |
| 画像処理 | Pillow |
| Markdown | markdown-it-py |
| ファイル監視 | watchdog |
| CLI通信 | subprocess (標準) |
| JSON処理 | json (標準) |
| 設定管理 | json (標準) |

**依存パッケージ（4つだけ）**:
```
flet
Pillow
markdown-it-py
watchdog
```
fletの
---

## 実装フェーズ

### Phase 1: Chat + ファイル（MVP）
- Chat Panel: メッセージ送受信、ストリーミング表示
- CLI通信: 新規会話、会話継続（resume）
- File Panel: ディレクトリツリー、ファイル選択
- 設定: プロジェクトディレクトリ、モデル選択

### Phase 2: 画像 + プレビュー
- Image Panel: サムネイル一覧、ドラッグ&ドロップ
- 画像 → Chat 送信フロー
- Preview Panel: Markdown プレビュー
- リサイズ・WebP 変換

### Phase 3: ビルド + 統合
- Build Panel: ビルド実行、ログ表示
- Git 操作 UI
- カスタムブロックプレビュー（:::chain 等）
- ファイル変更のライブリロード

---

## やらないこと

- API キー管理（Claude Code が処理）
- ツール実装（Claude Code が処理）
- 会話のコンテキスト管理（Claude Code が処理）
- 権限管理（Claude Code が処理）
- クラウド同期
- プラグインシステム
- Electron / Web技術

---

## Claude Code CLI が処理すること（自前実装不要）

| 機能 | CLI が提供 |
|---|---|
| AI モデル呼び出し | Messages API |
| ファイル読み書き | Read / Edit / Write ツール |
| コマンド実行 | Bash ツール |
| ファイル検索 | Glob / Grep ツール |
| Web 検索・取得 | WebSearch / WebFetch ツール |
| 会話の永続化 | --resume / --continue |
| モデル切替 | --model |
| 認証 | OAuth / API キー |
| コスト計算 | result の total_cost_usd |
| MCP サーバー | 設定済みのサーバーを自動利用 |

**つまり**: Flet アプリが実装するのは「表示」と「ファイル・画像の管理UI」だけ。
AI の頭脳は全て Claude Code CLI が提供する。

---

## 画面レイアウト

```
┌───────────┬────────────────────────────────┬───────────┐
│           │                                │           │
│   File    │         Chat Panel             │   Image   │
│   Panel   │                                │   Panel   │
│           │  ┌──────────────────────────┐  │           │
│  [tree]   │  │ streaming text...        │  │  [thumb]  │
│           │  │                          │  │  [thumb]  │
│           │  └──────────────────────────┘  │  [thumb]  │
│           │  ┌──────────────────────────┐  │           │
│           │  │ [message input]  [Send]  │  │           │
│           │  └──────────────────────────┘  │           │
├───────────┴────────────────────────────────┴───────────┤
│  [Preview] [Build]                                     │
│                                                        │
│  Markdown preview / Build output                       │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## Anthropic SDK 版との比較

| 項目 | Anthropic SDK 版 | Claude Code CLI 版 |
|---|---|---|
| 認証 | 自前実装 | 不要 |
| ツール | 全て自前実装 | 不要 |
| ストリーミング | 自前実装 | `--include-partial-messages` |
| 会話管理 | 自前実装 | `--resume` |
| MCP | 自前実装 | 不要 |
| コスト管理 | 自前計算 | CLI が返す |
| 依存パッケージ | anthropic + 多数 | flet + 3つ |
| コスト | API 従量課金 | Max plan に含まれる |
| 実装量 | 大 | **小（GUIだけ）** |

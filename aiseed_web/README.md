# aiseed_web builder

aiseed-web 静的サイトのビルダー(このリポジトリに同梱)。
テンプレート・既定スタイル・検索スクリプト・Python ツールをここに置き、
サイトのデータ(content / data / images)は別リポジトリ `aiseed-web/` に置く。

## 役割分担

| ここ(desktop/aiseed_web/) | aiseed-web/ |
|---|---|
| ビルドスクリプト(Python) | Markdown 原稿(content/) |
| Jinja2 テンプレート | 構造化データ(data/*.json) |
| 既定スタイル・JavaScript | 生画像(images/) |
| 依存管理(`desktop/requirements.txt`) | — |

## ビルド

```bash
python aiseed_web/tools/build.py --site /path/to/aiseed-web
```

または `AISEED_WEB_SITE` 環境変数で既定値を与えると `--site` 省略可:

```bash
export AISEED_WEB_SITE=/path/to/aiseed-web
python aiseed_web/tools/build.py
```

出力は `<site>/build/`。

## 開発サーバー

```bash
python aiseed_web/tools/serve.py --site /path/to/aiseed-web --port 8000
```

`<site>/{content,data,images}` と `aiseed_web/{templates,assets}` を監視し、
変更があれば自動で再ビルドする(ブラウザのリロードは手動)。

## 画像最適化

```bash
python aiseed_web/tools/optimize_images.py --site /path/to/aiseed-web
```

`<site>/images/**/*` を WebP にし、`<site>/build/assets/images/` に
`<stem>.webp` / `<stem>-480.webp` / `-800.webp` / `-1200.webp` を出力する。

## desktop アプリ(Flet Claude Code)からの使用

設定画面で次のように指定:

```json
{
  "project_dir": "/path/to/aiseed-web",
  "build_command": "python /path/to/desktop/aiseed_web/tools/build.py --site .",
  "deploy_command": "rsync -avz --delete build/ user@server:/var/www/aiseed/"
}
```

File / Image / Preview パネルは aiseed-web の content・data・images をそのまま
編集できる。Build パネルから上の `build_command` を実行する。

## 依存

`desktop/requirements.txt` にまとめてある。別途インストール不要:

- Jinja2
- markdown-it-py
- Pillow
- watchdog

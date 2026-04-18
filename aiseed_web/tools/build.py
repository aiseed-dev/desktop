"""Static site generator for aiseed-web sites.

Data layout expected under --site <dir>:
    <site>/content/  — Markdown (farmers/, products/, blog/, about.md)
    <site>/data/     — JSON (farmers.json, products.json, shops.json)
    <site>/images/   — raw images (copied to build/assets/images/)

Templates, scripts and default styles live alongside this script in
desktop/aiseed_web/. Output is written to <site>/build/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markdown_it import MarkdownIt

BUILDER_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BUILDER_ROOT / "templates"
ASSETS_DIR = BUILDER_ROOT / "assets"

SITE_URL = "https://aiseed.dev"
SITE_TITLE = "aiseed — 自然農の農家と消費者を直接つなぐ"


@dataclass
class Document:
    meta: dict[str, Any]
    body_html: str


@dataclass
class Paths:
    site: Path
    content: Path
    data: Path
    images: Path
    build: Path

    @classmethod
    def from_site(cls, site: Path) -> "Paths":
        return cls(
            site=site,
            content=site / "content",
            data=site / "data",
            images=site / "images",
            build=site / "build",
        )


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = _coerce(value.strip())
    return meta, text[match.end():]


def _coerce(raw: str) -> Any:
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_coerce(p.strip()) for p in inner.split(",")]
    if raw in ("true", "false"):
        return raw == "true"
    if raw.lstrip("-").isdigit():
        return int(raw)
    try:
        return float(raw)
    except ValueError:
        pass
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    return raw


def load_documents(folder: Path, md: MarkdownIt) -> dict[str, Document]:
    docs: dict[str, Document] = {}
    if not folder.exists():
        return docs
    for path in sorted(folder.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        meta.setdefault("id", path.stem)
        docs[path.stem] = Document(meta=meta, body_html=md.render(body))
    return docs


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def clean_build(build: Path) -> None:
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)


def copy_static_assets(build: Path) -> None:
    out = build / "assets"
    (out / "styles").mkdir(parents=True, exist_ok=True)
    (out / "scripts").mkdir(parents=True, exist_ok=True)
    for css in (ASSETS_DIR / "styles").glob("*.css"):
        shutil.copy2(css, out / "styles" / css.name)
    for js in (ASSETS_DIR / "scripts").glob("*.js"):
        shutil.copy2(js, out / "scripts" / js.name)


def copy_images(images_src: Path, build: Path) -> None:
    if not images_src.exists():
        return
    out = build / "assets" / "images"
    out.mkdir(parents=True, exist_ok=True)
    for img in images_src.rglob("*"):
        if img.is_file() and not img.name.startswith("."):
            rel = img.relative_to(images_src)
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(img, dest)


def write(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def generate(env: Environment, paths: Paths, farmers: list[dict], products: list[dict],
             shops: list[dict], content_docs: dict[str, dict[str, Document]]) -> list[str]:
    urls: list[str] = ["/"]
    farmer_by_id = {f["id"]: f for f in farmers}
    products_by_farmer: dict[str, list[dict]] = {}
    for p in products:
        products_by_farmer.setdefault(p["farmer_id"], []).append(p)

    ctx_base = {"site_title": SITE_TITLE, "site_url": SITE_URL, "year": datetime.now().year}

    write(paths.build / "index.html", env.get_template("index.html").render(
        **ctx_base, farmers=farmers[:6], products=products[:9]))

    write(paths.build / "farmers" / "index.html",
          env.get_template("farmers_index.html").render(**ctx_base, farmers=farmers))
    urls.append("/farmers/")
    for farmer in farmers:
        doc = content_docs.get("farmers", {}).get(farmer["id"])
        body = doc.body_html if doc else ""
        write(paths.build / "farmers" / f"{farmer['id']}.html",
              env.get_template("farmer.html").render(
                  **ctx_base,
                  farmer=farmer,
                  body=body,
                  products=products_by_farmer.get(farmer["id"], [])))
        urls.append(f"/farmers/{farmer['id']}.html")

    write(paths.build / "products" / "index.html",
          env.get_template("products_index.html").render(**ctx_base, products=products))
    urls.append("/products/")
    for product in products:
        doc = content_docs.get("products", {}).get(product["id"])
        body = doc.body_html if doc else ""
        farmer = farmer_by_id.get(product["farmer_id"])
        write(paths.build / "products" / f"{product['id']}.html",
              env.get_template("product.html").render(
                  **ctx_base, product=product, farmer=farmer, body=body))
        urls.append(f"/products/{product['id']}.html")

    write(paths.build / "shops" / "index.html",
          env.get_template("shops.html").render(**ctx_base, shops=shops))
    urls.append("/shops/")

    about_doc = content_docs.get("_root", {}).get("about")
    if about_doc:
        write(paths.build / "about" / "index.html",
              env.get_template("about.html").render(
                  **ctx_base, meta=about_doc.meta, body=about_doc.body_html))
        urls.append("/about/")

    blog_docs = content_docs.get("blog", {})
    posts = sorted(
        (d.meta | {"body_html": d.body_html, "slug": key} for key, d in blog_docs.items()),
        key=lambda p: p.get("date", ""),
        reverse=True,
    )
    write(paths.build / "blog" / "index.html",
          env.get_template("blog_index.html").render(**ctx_base, posts=posts))
    urls.append("/blog/")

    return urls


def write_sitemap(build: Path, urls: list[str]) -> None:
    today = datetime.now().date().isoformat()
    items = "\n".join(
        f"  <url><loc>{SITE_URL}{u}</loc><lastmod>{today}</lastmod></url>"
        for u in urls
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}\n</urlset>\n'
    (build / "sitemap.xml").write_text(xml, encoding="utf-8")


def write_robots(build: Path) -> None:
    (build / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8",
    )


def resolve_site(cli_value: str | None) -> Path:
    candidate = cli_value or os.environ.get("AISEED_WEB_SITE") or os.getcwd()
    site = Path(candidate).resolve()
    if not (site / "content").exists() and not (site / "data").exists():
        raise SystemExit(
            f"[build] {site} does not look like an aiseed-web site "
            "(no content/ or data/). Pass --site <path> or set AISEED_WEB_SITE."
        )
    return site


def build(site: Path) -> list[str]:
    paths = Paths.from_site(site)
    md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True})
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    farmers = load_json(paths.data / "farmers.json", [])
    products = load_json(paths.data / "products.json", [])
    shops = load_json(paths.data / "shops.json", [])

    content_docs = {
        "farmers": load_documents(paths.content / "farmers", md),
        "products": load_documents(paths.content / "products", md),
        "blog": load_documents(paths.content / "blog", md),
        "_root": load_documents(paths.content, md),
    }

    clean_build(paths.build)
    copy_static_assets(paths.build)
    copy_images(paths.images, paths.build)
    urls = generate(env, paths, farmers, products, shops, content_docs)
    write_sitemap(paths.build, urls)
    write_robots(paths.build)
    return urls


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an aiseed-web static site.")
    parser.add_argument("--site", help="Path to the site data directory (content/, data/, images/).")
    args = parser.parse_args()

    site = resolve_site(args.site)
    urls = build(site)
    print(f"Built {len(urls)} pages → {site / 'build'}")


if __name__ == "__main__":
    main()

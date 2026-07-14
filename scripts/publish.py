#!/usr/bin/env python3
"""
publish.py — 把 Obsidian vault 里标记 publish: true 的笔记发布到 Hugo 站点。

用法:
    python3 scripts/publish.py            # 同步 + commit + push（触发网站部署）
    python3 scripts/publish.py --no-push  # 只同步到本地仓库，不推送
    python3 scripts/publish.py --dry-run  # 只显示会发生什么，不改任何文件

在 Obsidian 笔记的 frontmatter 里加:
    ---
    publish: true
    title: 文章标题          # 可选，默认用文件名
    slug: my-post           # 可选，URL 用，默认用文件名
    section: bodyfactory    # 可选，默认按文件夹映射
    date: 2026-07-14        # 可选，默认取文件修改时间（日记按文件名日期）
    tags: [健身, 体态]       # 可选
    ---

白名单模型：只有显式标记 publish: true 的笔记才会被发布。
脚本只管理带 obsidian_source 标记的页面；源笔记取消标记后，再次运行会自动下线对应页面。
"""

import argparse
import datetime
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

VAULT = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents"
SITE = Path(__file__).resolve().parent.parent
CONTENT = SITE / "content"

GIT_AUTHOR = "Orange <orangeorchard95@users.noreply.github.com>"

# vault 顶层文件夹 → 网站栏目
SECTION_MAP = {
    "dairy": "thoughts",
    "Quant": "quant",
    "body factory": "bodyfactory",
    "movies": "sharing",
}
DEFAULT_SECTION = "sharing"
VALID_SECTIONS = {"thoughts", "quant", "bodyfactory", "sharing"}

SKIP_DIRS = {".obsidian", ".trash", "Attachments", "node_modules"}

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".heic"}


def parse_frontmatter(text):
    """极简 YAML frontmatter 解析（key: value / 布尔 / [a, b] 列表 / - 列表项）。"""
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        return {}, text
    meta, body = {}, text[m.end():]
    key = None
    for line in m.group(1).splitlines():
        if re.match(r"^\s*-\s+", line) and key:
            meta.setdefault(key, [])
            if isinstance(meta[key], list):
                meta[key].append(line.split("-", 1)[1].strip())
            continue
        kv = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if not kv:
            continue
        key, val = kv.group(1), kv.group(2).strip()
        if val == "":
            meta[key] = []
        elif val.lower() in ("true", "false"):
            meta[key] = val.lower() == "true"
        elif val.startswith("[") and val.endswith("]"):
            meta[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
        else:
            meta[key] = val.strip("'\"")
    return meta, body


def find_attachment(name, note_path):
    """按文件名在 vault 里找附件（优先同一子库的 Attachments）。"""
    name = name.split("|")[0].strip()
    # 相对路径直接命中
    direct = (note_path.parent / name)
    if direct.exists():
        return direct
    matches = [p for p in VAULT.rglob(name.split("/")[-1]) if p.is_file() and ".obsidian" not in p.parts]
    if not matches:
        return None
    # 优先与笔记同顶层文件夹的
    top = note_path.relative_to(VAULT).parts[0]
    same = [p for p in matches if p.relative_to(VAULT).parts[0] == top]
    return (same or matches)[0]


def safe_asset_name(path, used):
    """附件重命名为 URL 安全的文件名，避免空格和重名。"""
    stem = re.sub(r"[^\w一-鿿-]+", "-", path.stem).strip("-") or "img"
    name = f"{stem}{path.suffix.lower()}"
    i = 1
    while name in used:
        name = f"{stem}-{i}{path.suffix.lower()}"
        i += 1
    used.add(name)
    return name


def copy_html_attachment(src, dry_run):
    """HTML 附件（含其引用的图片）复制到 static/embeds/ 原样发布，返回 URL 路径。
    不能放进 content bundle：Hugo 会把 .html 当内容页处理。"""
    html = src.read_text(encoding="utf-8")
    stem = re.sub(r"[^\w一-鿿-]+", "-", src.stem).strip("-") or "doc"
    embed_dir = SITE / "static" / "embeds" / stem
    used, assets = set(), []

    def src_repl(m):
        ref = urllib.parse.unquote(m.group(1))
        if re.match(r"^(https?:|data:|/)", ref):
            return m.group(0)
        img = find_attachment(ref, src)
        if img is None:
            return m.group(0)
        name = safe_asset_name(img, used)
        assets.append((img, name))
        return f'src="{urllib.parse.quote(name)}"'

    html = re.sub(r'src="([^"]+)"', src_repl, html)
    # 注入自适应缩放：固定宽度的文档（如 A4 排版）在窄 iframe 里整体缩小而不是横向裁切
    fit = ("<script>(function(){function fit(){var d=document.documentElement,b=document.body;"
           "b.style.zoom='';var w=Math.max(b.scrollWidth,d.scrollWidth);"
           "var s=d.clientWidth/w;if(s<1)b.style.zoom=s;}"
           "addEventListener('load',fit);addEventListener('resize',fit);})();</script>")
    if "</body>" in html:
        html = html.replace("</body>", fit + "</body>", 1)
    else:
        html += fit
    if not dry_run:
        embed_dir.mkdir(parents=True, exist_ok=True)
        (embed_dir / "index.html").write_text(html, encoding="utf-8")
        for img, name in assets:
            shutil.copy2(img, embed_dir / name)
    return f"/embeds/{urllib.parse.quote(stem)}/"


def convert_body(body, note_path, bundle_dir, dry_run):
    """转换 Obsidian 语法为标准 markdown，复制引用的图片进 page bundle。"""
    used = set()
    copied = []

    def embed_repl(m):
        target = m.group(1)
        alt = target.split("|")[1] if "|" in target else Path(target.split("|")[0]).stem
        src = find_attachment(target, note_path)
        if src is None:
            return f"<!-- 未找到附件: {target} -->"
        if src.suffix.lower() in IMAGE_EXTS:
            name = safe_asset_name(src, used)
            copied.append((src, name))
            return f"![{alt}]({urllib.parse.quote(name)})"
        if src.suffix.lower() in (".html", ".htm"):
            url = copy_html_attachment(src, dry_run)
            return (
                f'<iframe src="{url}" '
                'style="width: 100%; height: 80vh; border: 1px solid #d2d2d7; border-radius: 0.5rem;" '
                'loading="lazy"></iframe>\n\n'
                f'[⛶ 全屏查看]({url})'
            )
        if src.suffix.lower() == ".pdf":
            stem = re.sub(r"[^\w一-鿿-]+", "-", src.stem).strip("-") or "file"
            name = f"{stem}.pdf"
            if not dry_run:
                files_dir = SITE / "static" / "files"
                files_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, files_dir / name)
            return f"[📄 下载打印版 PDF](/files/{urllib.parse.quote(name)})"
        return f"<!-- 跳过非图片附件: {target} -->"

    # ![[embed]] → 图片；[[link|text]] → text；[[link]] → link 文本
    body = re.sub(r"!\[\[([^\]]+)\]\]", embed_repl, body)
    body = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", body)
    body = re.sub(r"\[\[([^\]|]+)\]\]", r"\1", body)

    if not dry_run:
        bundle_dir.mkdir(parents=True, exist_ok=True)
        for src, name in copied:
            shutil.copy2(src, bundle_dir / name)
    return body, [n for _, n in copied]


def note_date(meta, path):
    if isinstance(meta.get("date"), str) and meta["date"]:
        return meta["date"][:10]
    m = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem)
    if m:
        return m.group(1)
    return datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()


def toml_escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def collect_published():
    """扫描 vault，返回 {bundle相对路径: (源文件, 生成的index.md内容)}。"""
    out = {}
    for md in sorted(VAULT.rglob("*.md")):
        rel = md.relative_to(VAULT)
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts):
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        meta, body = parse_frontmatter(text)
        if meta.get("publish") is not True:
            continue

        section = str(meta.get("section", "")) or SECTION_MAP.get(rel.parts[0], DEFAULT_SECTION)
        if section not in VALID_SECTIONS:
            print(f"  ⚠️  {rel}: 未知栏目 {section!r}，改用 {DEFAULT_SECTION}")
            section = DEFAULT_SECTION
        slug = str(meta.get("slug", "")) or re.sub(r"\s+", "-", md.stem).strip("-")
        title = str(meta.get("title", "")) or md.stem
        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]

        fm = ['---',
              f'title: "{toml_escape(title)}"',
              f'date: {note_date(meta, md)}']
        if tags:
            fm.append("tags: [" + ", ".join(f'"{t}"' for t in tags) + "]")
        if meta.get("series"):
            fm.append(f'series: ["{meta["series"]}"]')
            if meta.get("series_order"):
                fm.append(f'series_order: {meta["series_order"]}')
        if meta.get("description"):
            fm.append(f'description: "{meta["description"]}"')
        fm.append(f"obsidian_source: \"{rel.as_posix()}\"")
        fm.append("---")
        out[f"{section}/{slug}"] = (md, "\n".join(fm) + "\n" + body)
    return out


def managed_bundles():
    """站点里所有由本脚本生成（带 obsidian_source 标记）的 bundle。"""
    found = {}
    for idx in CONTENT.glob("*/*/index.md"):
        if "obsidian_source:" in idx.read_text(encoding="utf-8"):
            found[idx.parent.relative_to(CONTENT).as_posix()] = idx.parent
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true", help="不推送到 GitHub")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    args = ap.parse_args()

    print(f"📖 扫描 vault: {VAULT}")
    published = collect_published()
    existing = managed_bundles()

    added = updated = 0
    for key, (src, content) in published.items():
        bundle = CONTENT / key
        idx = bundle / "index.md"
        body, assets = convert_body(content, src, bundle, args.dry_run)
        if idx.exists() and idx.read_text(encoding="utf-8") == body:
            continue
        verb = "更新" if key in existing else "新增"
        print(f"  ✅ {verb} {key}  ← {src.relative_to(VAULT)}" + (f"（{len(assets)} 张图）" if assets else ""))
        if not args.dry_run:
            idx.write_text(body, encoding="utf-8")
        if key in existing:
            updated += 1
        else:
            added += 1

    removed = 0
    for key, path in existing.items():
        if key not in published:
            print(f"  🗑  下线 {key}（源笔记已取消 publish 标记）")
            if not args.dry_run:
                shutil.rmtree(path)
            removed += 1

    print(f"\n共 {len(published)} 篇已发布：新增 {added}，更新 {updated}，下线 {removed}")
    if args.dry_run:
        print("（dry-run，未写入任何文件）")
        return

    if added or updated or removed:
        msg = f"发布更新：新增{added} 更新{updated} 下线{removed}"
    else:
        msg = "发布更新：附件资源更新"
    subprocess.run(["git", "-C", str(SITE), "add", "content", "static"], check=True)
    dirty = subprocess.run(["git", "-C", str(SITE), "diff", "--cached", "--quiet"]).returncode != 0
    if dirty:
        subprocess.run(
            ["git", "-C", str(SITE), "commit",
             f"--author={GIT_AUTHOR}",
             "-m", msg],
            check=True,
            env={"GIT_COMMITTER_NAME": "Orange",
                 "GIT_COMMITTER_EMAIL": "orangeorchard95@users.noreply.github.com",
                 "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
        )
        if not args.no_push:
            subprocess.run(["git", "-C", str(SITE), "push"], check=True)
            print("🚀 已推送，GitHub Actions 正在部署（约 1-2 分钟后生效）")
        else:
            print("📦 已提交到本地仓库（--no-push，未推送）")
    else:
        print("没有变化，无需提交。")


if __name__ == "__main__":
    sys.exit(main())

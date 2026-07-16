# Orange Orchard 🍊

个人网站，部署在 https://orangeorchard95.github.io — Hugo + [Blowfish](https://blowfish.page) + GitHub Pages。

## 日常发布流程

1. 在 Obsidian 笔记的 frontmatter 里加 `publish: true`（可选 `title` / `slug` / `section` / `tags` / `date` / `series`；`cover: 图片名.png` 指定列表卡片的封面图）
2. 运行一条命令：

```bash
python3 scripts/publish.py
```

脚本会：扫描 vault 里所有标记发布的笔记 → 转换 Obsidian 语法（`![[图片]]`、`[[链接]]`）→ 复制到对应栏目 → commit + push → GitHub Actions 自动部署。

把 `publish: true` 改回 `false` 再运行，文章自动下线。

## 栏目映射

| vault 文件夹 | 网站栏目 |
|---|---|
| dairy | 思考 /thoughts/ |
| Quant | 量化 /quant/ |
| body factory | 身体工厂 /bodyfactory/ |
| movies | 书影 /media/ |
| reading | 书影 /media/ |

frontmatter 里写 `section: xxx` 可覆盖默认映射。

## 书影墙

vault 的 `movies/`（电影）和 `reading/`（书）里**一部作品一个 md**，frontmatter 极简五字段（模版见各文件夹里的 `模版.md`）：

```yaml
---
publish: true
title: 星际穿越
rating: 4.5        # 5 星制，支持半星
date: 2026-07-16   # 看完/读完日期
# cover: 海报.png   # 可省略：默认取正文第一张图当海报
---
```

正文随意：粘贴海报/剧照 + 写心得。发布后 `/media/` 是豆瓣式海报墙（书 📖 和电影 🎬 按日期混排），点海报进详情页（左海报右信息栏，下方心得）。

注意：不写 `cover` 时，正文第一张图会被提升为海报并**从正文移除**（避免详情页重复出现）；想让它留在正文里，就显式写 `cover:` 指定另一张图。

## 照片墙

vault 的 `photos/` 仓库下**每个含图片的子文件夹自动发布为一个合集**（如 `photos/面包🥖/` → `/photos/面包/`），发布时自动压缩到最长边 1600px。注意：photos 仓库整体视为白名单，放进去的照片都会公开。

- 往文件夹里加照片 → 运行发布命令即更新合集
- 文件夹里放一个 md 文件可自定义元信息（`title` / `description` / `cover: 图片文件名` / `publish: false` 排除整个文件夹）
- 删除文件夹 → 再运行发布命令即下线合集

## 常用操作

```bash
python3 scripts/publish.py --dry-run     # 预览会发布/下线什么
python3 scripts/publish.py --no-push     # 只提交本地不推送
python3 scripts/publish.py --no-commit   # 只同步文件（配合 hugo server 本地预览）
hugo server                              # 本地预览 http://localhost:1313
```

## B站视频嵌入

文章里写：

```
{{</* bilibili BV1xx411c7mD */>}}
```

## 待办配置

- [ ] giscus 评论：仓库 Settings 开启 Discussions → 安装 giscus app → https://giscus.app 生成 ID → 填入 `config/_default/params.toml` 的 `[giscus]`
- [ ] 访问统计：https://www.goatcounter.com 注册 → 在 `params.toml` 顶层加 `goatcounter = "你的code"`

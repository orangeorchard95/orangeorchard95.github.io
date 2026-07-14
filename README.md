# Orange Orchard 🍊

个人网站，部署在 https://orangeorchard95.github.io — Hugo + [Blowfish](https://blowfish.page) + GitHub Pages。

## 日常发布流程

1. 在 Obsidian 笔记的 frontmatter 里加 `publish: true`（可选 `title` / `slug` / `section` / `tags` / `date` / `series`）
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
| movies | 分享 /sharing/ |

frontmatter 里写 `section: xxx` 可覆盖默认映射。

## 常用操作

```bash
python3 scripts/publish.py --dry-run   # 预览会发布/下线什么
python3 scripts/publish.py --no-push   # 只提交本地不推送
hugo server                            # 本地预览 http://localhost:1313
```

## B站视频嵌入

文章里写：

```
{{</* bilibili BV1xx411c7mD */>}}
```

## 待办配置

- [ ] giscus 评论：仓库 Settings 开启 Discussions → 安装 giscus app → https://giscus.app 生成 ID → 填入 `config/_default/params.toml` 的 `[giscus]`
- [ ] 访问统计：https://www.goatcounter.com 注册 → 在 `params.toml` 顶层加 `goatcounter = "你的code"`

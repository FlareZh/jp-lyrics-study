# jp-lyrics-study

Cursor Agent Skill：根据日语歌名生成**自包含的歌词逐句学习网页**。

面向初学日语、但希望语法讲解尽量精确的学习者。输入歌名（可含歌手），确认官方歌词后，输出单文件 HTML：振假名、分词、语法、翻译、可点击生词浮层，以及按 JLPT 分级的生词总表。

## 功能

- 逐句歌词（`<ruby>` 振假名）
- 点击展开：分词 / 语法 / 中文翻译
- 生词浮层：词性、形态、读音、释义、出处
- 底部生词总表：按 JLPT（N5–N1，未命中索引则「未分级」）分组去重
- 每首歌可定制 hero 配色与氛围动画
- 歌词中的拉丁字母英文原样保留，不做注音/生词/语法处理（片假名外来语仍按日语处理）

## 安装

把本仓库放到 Cursor skills 目录，或作为 skill 引用：

```bash
# 示例：克隆到个人 skills 目录
git clone https://github.com/FlareZh/jp-lyrics-study.git ~/.cursor/skills/jp-lyrics-study
```

确保目录中含有 `SKILL.md`，Cursor 会按 skill 描述自动匹配触发。

## 用法

在 Cursor 对话里说类似：

- 「帮我做《あぶく》的歌词学习网页」
- 「生成日语歌词注音/分词/语法讲解页，歌手 XXX」

Agent 会：

1. 检索官方日文歌词，发给你确认
2. 确认后再按模板填数据并生成 HTML
3. 交付 `歌词名-歌词学习.html`（可直接用浏览器打开）

## 目录结构

```
jp-lyrics-study/
├── SKILL.md                         # Skill 入口与工作流
├── assets/
│   └── lyric-page-template.html     # 成品页面模板（样式 + 交互）
└── references/
    ├── data-guide.md                # S / POS 数据结构与填表规则
    └── jlpt/
        ├── index.jsonl              # 词汇/语法 JLPT 分级索引（检索用）
        ├── build_index.py           # 从各级 md 重建 index.jsonl
        └── n5…n1/                   # vocabulary.md · grammar.md
```

| 文件 | 作用 |
|------|------|
| `SKILL.md` | 触发条件、工作流、硬性规则、索引检索方式 |
| `assets/lyric-page-template.html` | 复制后替换 `S`、`POS` 与 hero 占位即可出页 |
| `references/data-guide.md` | 歌词数组 `S`、词性表 `POS`、读音与分级规则 |
| `references/jlpt/index.jsonl` | 唯一 JLPT 分级源；未命中则不分级 |

## 生成产物概要

模板内需填充两处数据（详见 data-guide）：

- `const S = [...]`：每句歌词的 `jp` / `seg` / `tr` / `gram` / `ws`
- `const POS = {...}`：词形 → 词性；动词/形容词/助动词/句型另附形态表

另需替换 hero 中的歌名、歌手、译名、作词人、简介，并按歌曲情绪调整背景与特效。

## License

MIT

# jp-lyrics-study

通用 AI 助理 Skill：根据日语歌名生成**自包含的单文件歌词逐句学习网页**。

面向初学日语、但希望语法讲解尽量精确的学习者。输入歌名（可含歌手），确认官方歌词后，输出一个 HTML 文件：振假名、分词、语法、翻译、可点击生词浮层、Web Speech 日语发音，以及按 JLPT 分级的生词总表。

## 功能

- 逐句歌词（`<ruby>` 振假名）
- 点击展开：分词 / 语法 / 中文翻译
- 生词浮层：词性、形态、读音、释义、出处
- 喇叭按钮：整句 / 生词朗读（Web Speech API；可自动优选或在设置中选手动音色；语法说明不朗读）
- 设置：可开关振假名、片假名的平假名注音；可选日语音色并调节语速/音调、试听；可改读音并本机保存（按歌曲）
- 底部生词总表：按 JLPT（N5–N1，未命中索引则「NX / 未收录」）分组去重
- 每首歌可定制 hero 配色与氛围动画
- 歌词中的拉丁字母英文原样保留，不做注音/生词/语法处理（片假名外来语仍按日语处理）

## 安装

把本仓库放到所用 AI 助理认读的 skills 目录，或按该产品的方式引用本 skill（需能读到根目录的 `SKILL.md`）。

```bash
# 示例：克隆到本地 skills 目录后由助理加载
git clone https://github.com/FlareZh/jp-lyrics-study.git
```

助理会按 `SKILL.md` 的描述匹配「做歌词学习网页 / 逐句讲解歌词」等请求并触发本流程。

## 用法

对 AI 助理说类似：

- 「帮我做《あぶく》的歌词学习网页」
- 「生成日语歌词注音/分词/语法讲解页，歌手 XXX」

助理会：

1. 检索官方日文歌词，发给你确认
2. 确认后再按模板填数据并生成 HTML
3. 交付 `歌词名-歌词学习.html`（单文件）

## 目录结构

```
jp-lyrics-study/
├── SKILL.md                         # Skill 入口与工作流
├── assets/
│   └── lyric-page-template.html     # 自包含单文件模板
└── references/
    ├── data-guide.md                # S / POS 数据结构与填表规则
    └── jlpt/
        ├── vocabulary.jsonl         # 词汇 JLPT 分级索引
        ├── grammar.jsonl            # 语法 JLPT 分级索引
        ├── build_index.py           # 从各级 md 重建上述索引
        └── n5…n1/                   # vocabulary.md · grammar.md
```

| 文件 | 作用 |
|------|------|
| `SKILL.md` | 触发条件、工作流、硬性规则、索引检索方式 |
| `assets/lyric-page-template.html` | 复制后替换 `SONG_ID`、`S`、`POS` 与 hero 占位即可出页 |
| `references/data-guide.md` | 歌词数组 `S`、词性表 `POS`、读音与分级规则 |
| `references/jlpt/vocabulary.jsonl` | 词汇 JLPT 分级源；未命中则不分级（NX） |
| `references/jlpt/grammar.jsonl` | 语法 JLPT 分级源；未命中则不标注等级 |

## 生成产物概要

模板内需填充（详见 data-guide）：

- `const SONG_ID = '歌名|歌手名'`：本机读音覆盖的隔离键
- `const S = [...]`：每句歌词的 `jp` / `seg` / `tr` / `gram` / `ws`
- `const POS = {...}`：词形 → 词性；动词/形容词/助动词/句型另附形态表

另需替换 hero 中的歌名、歌手、译名、作词人、简介，并按歌曲情绪调整内联 CSS 中的背景与特效。

## License

MIT

# jp-lyrics-study

通用 AI 助理 Skill：根据日语歌名生成**歌词逐句学习网页**（HTML + CSS + JS + 数据）。

面向初学日语、但希望语法讲解尽量精确的学习者。输入歌名（可含歌手），确认官方歌词后，输出歌词逐句学习页（HTML + CSS + JS + 数据）：振假名、分词、语法、翻译、可点击生词浮层、piper-plus 日语发音（OpenJTalk，汉字读音准确），以及按 JLPT 分级的生词总表。

## 功能

- 逐句歌词（`<ruby>` 振假名）
- 点击展开：分词 / 语法 / 中文翻译
- 生词浮层：词性、形态、读音、释义、出处
- 喇叭按钮：整句 / 生词朗读（piper-plus / OpenJTalk；语法说明不朗读；首次需联网下载模型）
- 设置：可开关振假名、片假名的平假名注音（本机记住）
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
3. 交付同目录下的 `歌词名-歌词学习.html` + `lyric-page.css` + `lyric-page.js` + `lyric-data.js`（可直接用浏览器打开 HTML）

## 目录结构

```
jp-lyrics-study/
├── SKILL.md                         # Skill 入口与工作流
├── assets/
│   ├── lyric-page-template.html     # 页面结构
│   ├── lyric-page.css               # 样式（含 hero 氛围）
│   ├── lyric-page.js                # 交互 / 渲染 / 朗读
│   └── lyric-data.js                # S / POS 数据占位
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
| `assets/lyric-page-template.html` | 页面结构与 hero 文案占位 |
| `assets/lyric-page.css` | 样式；按歌定制 hero 配色/特效 |
| `assets/lyric-page.js` | 渲染与交互（一般无需改） |
| `assets/lyric-data.js` | 填入 `S`、`POS` |
| `references/data-guide.md` | 歌词数组 `S`、词性表 `POS`、读音与分级规则 |
| `references/jlpt/vocabulary.jsonl` | 词汇 JLPT 分级源；未命中则不分级（NX） |
| `references/jlpt/grammar.jsonl` | 语法 JLPT 分级源；未命中则不标注等级 |

## 生成产物概要

在 `lyric-data.js` 填充两处数据（详见 data-guide）：

- `export const S = [...]`：每句歌词的 `jp` / `seg` / `tr` / `gram` / `ws`
- `export const POS = {...}`：词形 → 词性；动词/形容词/助动词/句型另附形态表

另需替换 HTML hero 中的歌名、歌手、译名、作词人、简介，并在 CSS 中按歌曲情绪调整背景与特效。交付时四件套须在同一目录。

## License

MIT

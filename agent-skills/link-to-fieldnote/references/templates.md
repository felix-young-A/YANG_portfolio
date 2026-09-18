# 模板（Templates）

> 本文件承载 A/B/C 三类任务的文档骨架模板。选用哪套模板由任务类型决定（见 [task-types.md](task-types.md)）；往模板里填正文时必须同时执行 [writing-standards.md](writing-standards.md) 的对应标准与 [output-format-rules.md](output-format-rules.md) 的格式规则。

## 目录

- [A 类：视频知识笔记模板](#a-类视频知识笔记模板)
- [B 类：视频原生文稿模板](#b-类视频原生文稿模板)
- [C 类：公众号/网页文章模板](#c-类公众号网页文章模板)

---

## A 类：视频知识笔记模板

适用于把视频提炼成可复用知识。

```markdown
---
title: '原视频标题'
host: "作者或频道名"
guest: ""
source: "原链接"
platform: "平台名"
date: "发布日期"
created: "整理日期"
tags:
  - fieldnote
  - interview
---

📂 [[Field_Notes.base|Field Notes 索引]]

# 判断式主标题（一句话核心观点，有张力；禁止直接沿用原视频标题）

> **⚡ 副题（可选）**：设问或补充说明，引导读者进入正文
>
> **⚡ 主题**：主题词 1、主题词 2、主题词 3

---

## 🎬 Video

<!-- 只有在确认 iframe 指向当前主视频时才嵌入。不要使用 companion 或 related video。 -->
<iframe src="https://www.youtube.com/embed/VIDEO_ID?autoplay=0" width="100%" height="400" frameborder="0" allowfullscreen></iframe>

> 📺 [YouTube](YouTube 链接) · [Bilibili](Bilibili 链接) · [官网](原链接)

---

## Abstract

> 用一段简体中文说明视频讨论的问题、核心判断、主要案例和知识价值。

---

## Key Points

- 提炼可复用判断。
- 每条都是完整知识点，不只写关键词。
- 优先提炼方法论、机制、流程、坑点、边界条件。

---

## Full Transcript

> 说明：本笔记基于【公开字幕/音频转写/页面章节/用户提供文稿】整理。这里不是逐字稿，而是基于原内容二次加工的知识笔记。

### 📄 Content

#### 01 判断式小标题（本章核心观点，不是内容概述）

先放核心判断，再用原视频案例/论据支撑。每段控制在 2~4 句，超过 5 行必须拆分；长短句交替，禁止一段到底。

> 摘要：关键要点概述。

#### 02 判断式小标题

（章节按逻辑递进组织，编号 01 / 02 / 03…；每章 3~9 个子主题；可复用结论提炼成金句，独立成段或加粗，全文 3~6 处。）

#### 结语

根据自己对这个整篇内容的内容、主题，进行总结回扣收尾，不强行升华

---

## Related Notes

_暂无相关笔记_
```

---

## B 类：视频原生文稿模板

适用于用户要原文稿、逐字稿、字幕整理。

```markdown
---
title: '原视频标题'
host: "作者或频道名"
source: "原链接"
platform: "平台名"
date: "发布日期"
created: "整理日期"
tags:
  - fieldnote
  - interview
---

📂 [[Field_Notes.base|Field Notes 索引]]

# 原视频标题

---

## 🎬 Video

<!-- 只有在确认 iframe 指向当前主视频时才嵌入。不要使用 companion 或 related video。 -->
<iframe src="https://www.youtube.com/embed/VIDEO_ID?autoplay=0" width="100%" height="400" frameborder="0" allowfullscreen></iframe>

> 📺 [YouTube](YouTube 链接) · [Bilibili](Bilibili 链接) · [官网](原链接)

---

## Abstract

> 简要说明视频主题和文稿来源。

---

## Full Transcript

> 说明：本稿基于【公开字幕/音频转写】整理，已修正明显错字、标点、断句和段落。尽量保留原表达，不做知识改写。

### 📄 Content

整理后的原生文稿。

---

## Related Notes

_暂无相关笔记_
```

---

## C 类：公众号/网页文章模板

适用于微信公众号、网页文章、博客、新闻页、评论页。

```markdown
---
title: '文章标题'
author: "作者名称"
source: "来源名称"
url: "原文链接"
date: "发布日期"
created: "整理日期"
tags:
  - fieldnote
  - article
---

📂 [[Field_Notes.base|Field Notes 索引]]

# 文章标题

---

## Abstract

> 用一段简体中文概括文章核心内容。若用户只要求清理原文，可简短处理。

---

## Key Points

- 可选。用户要求知识笔记或文章本身观点密集时保留。

---

## Content

清理和排版后的文章正文。

---

## Related Notes

_暂无相关笔记_
```

---
name: link-to-fieldnote
description: 将用户提供的视频链接、音频链接、网页文章链接或本地音视频文件，转化为结构化的 Obsidian Field Note 或原生文稿。触发场景：(1) 用户提供 URL 链接并要求转化为笔记、整理、总结、提炼、提取内容、总结这个链接、做成知识笔记；(2) 用户说“帮我做个 field note”“做个笔记”“整理一下这个视频/文章/播客”；(3) 用户说“转成文稿”“生成逐字稿”“转录”“transcribe”“保留原话”；(4) 用户提供 Bilibili/YouTube/抖音/小红书/微信公众号/播客/RSS/任意网页链接，并隐含或明确希望获取其中内容；(5) 用户上传本地音视频文件并要求转录或整理。注意：本技能仅处理外部新增内容（URL 链接/用户上传的本地文件）；处理 Vault 内 Clippings/ 文件夹中已存在的剪藏文件应使用 fieldnote-clipping 技能，不要混淆。
---

# link-to-fieldnote

将用户提供的视频链接、音频链接、网页文章链接或本地音视频文件，转化为结构化的 Obsidian Field Note 或原生文稿。

本技能采用分文件组织：**本文件只包含任务路由、端到端执行流程与全局铁律**；各环节的完整规范、模板与检查清单放在 `references/` 下，按下面的索引在对应阶段**必须加载读取**，不得凭印象跳过。

---

## 1. 任务路由：先判定 A / B / C 类型

本技能覆盖三种输出类型，接到任务后**先根据用户意图判定类型，再走对应流程**。完整定义（触发词、输出格式、内容来源、输出重点、默认规则）见 [references/task-types.md](references/task-types.md)。

| 类型 | 名称 | 典型触发词 | 输出形态 | 默认判定 |
| --- | --- | --- | --- | --- |
| **A 类** | 知识笔记 Knowledge Field Note | 总结、提炼、知识点、做笔记、知识库、方法论、机制、框架、复盘、抓住重点 | `Abstract` + `Key Points` + 二次加工的知识正文 | 用户给视频链接并说“总结一下”“做笔记”“放知识库”，走 A 类 |
| **B 类** | 原生文稿 Native Transcript | 原文稿、完整文稿、逐字稿、转写稿、字幕、不要总结、保留原话 | 按时间轴或章节分段的纯文本，不删减、不改写 | 用户明确要“文稿/逐字稿/原文稿”时，走 B 类 |
| **C 类** | 网页清理 Web Article Cleanup | 公众号、网页、文章、博客、新闻、清理、排版、去广告、剪藏 | 去噪后的纯净正文 Markdown | 链接是公众号/网页文章/博客/新闻页且没要求“总结方法论”，走 C 类 |

> ⚠️ **本技能仅处理外部新增内容**（URL 链接 / 用户上传的本地文件）。如果用户要求处理 Vault 内 `Clippings/` 文件夹中**已存在的**剪藏文件（如“整理这个 clipping”“美化排版”），应使用 `fieldnote-clipping` 技能，不要混淆。

类型判定要点：
- **A 类**内容来源优先级：字幕 > 音频转写 > 网页正文；先尽量获取完整视频音频/字幕，再二次加工。
- **B 类**音频转写是强制步骤（见 [references/transcription.md](references/transcription.md)）。
- **C 类**内容来源优先级：Defuddle（最佳） > Readability > 直接抓取（curl/fetch）；若用户额外要求知识笔记，再按 A 类标准增加 `Abstract` 和 `Key Points`。

---

## 2. 端到端执行流程

按以下顺序推进，每个环节加载对应参考文件并严格执行：

**第 1 步：判定任务类型（A/B/C）**
- 按上方路由表和 [references/task-types.md](references/task-types.md) 判定；意图不明确时先向用户澄清要“知识提炼”还是“原生文稿”。

**第 2 步：获取内容并锁定证据来源**
- 加载 [references/content-fetching.md](references/content-fetching.md)：先看“证据优先级”，再按平台（B站/YouTube/抖音/小红书/播客/网页）选择正确工具链。
- 对已知需要 cookies 或反爬严格的平台（抖音、小红书），直接使用浏览器自动化方案，不要先用 yt-dlp 反复试错。
- 遇到障碍严格按 L0→L4“工具缺失与反爬降级矩阵”分层降级，**禁止原地反复重试同一种方法，禁止伪造内容**。
- 进入 L3 及以下“降级整理模式”时，**必须先中断任务、询问用户是否接受降级模式，等用户确认后再继续**。

**第 3 步：判定并执行音频转写**
- 加载 [references/transcription.md](references/transcription.md)：按“音频转写判定规则”决定是否强制转写；原则是**宁可多转写，不可遗漏**，不确定字幕是否完整时就转写。
- Whisper 安装、模型选择、强制参数、音频预处理、预期耗时、转写后纠错表均在该文件中。

**第 4 步：按模板与写作标准产出文档**
- 加载 [references/templates.md](references/templates.md)，取用与任务类型对应的模板（A/B/C）。
- 加载 [references/writing-standards.md](references/writing-standards.md)：A 类执行五步流程、写作协议、精校六条、去 AI 味完整版等全部写作标准；B 类执行 B 类处理标准；C 类执行 C 类清理标准。

**第 5 步：全程遵守输出格式规范**
- 加载 [references/output-format-rules.md](references/output-format-rules.md)：Obsidian 引用/Callout 规范、排版、iframe 校验、语言标题、frontmatter 与标签、关键帧截图、文件命名、通用格式共 8 条核心规则。

**第 6 步：生成前自查、交付前质检、按模板回复**
- 加载 [references/quality-assurance.md](references/quality-assurance.md)：生成最终文档前必须先过“执行检查点”，任一不满足不得进入生成阶段；交付前逐项过“质量检查”清单；完成后按“回复用户”模板简洁说明处理类型、依据和文件链接。

---

## 3. 全局铁律（跨环节，任何阶段都生效）

1. **不伪造内容**：处理任何链接都必须明确内容依据。只能拿到页面章节/简介等第 3 类信息时，不能声称“基于完整音频内容”，必须在文档中说明依据；完全无法获取时明确告知限制并请求用户上传，不得编造。
2. **证据必须标注**：每篇产出都要标注依据来源（公开字幕 / 音频转写 / 页面章节 / 用户提供正文 / 公开报道）；降级场景在显眼位置标注来源限制，关键引用区分“原视频内容”与“外部补充信息”。
3. **转写宁多勿缺**：B 类任务必须转写；A 类需要完整内容才能准确提炼时也必须转写；只有“完整公开字幕已全部获取”或“用户明确要求只基于页面信息”才可跳过。B站仅有的不完整自动字幕不算完整字幕。
4. **按层降级，不原地重试**：下载/浏览器/网络捕获每一层失败都按降级矩阵切换方案；滑块最多试 2~3 次；降级整理前必须先征得用户同意。
5. **信息守恒**：核心观点、关键案例、重要数据、补充说明、警示块、引用块、对比细节、数据出处不得因排版或“精简”被整体删除；同时严禁新增原稿未出现的事实、数据、案例或立场。
6. **格式服从 Obsidian 规范**：默认普通 `>` 引用为主、Callout 按场景克制使用；frontmatter 字段纯文本、信息不在正文重复；标签固定为 `fieldnote` + 内容类型；顶级模块标题用英文、正文用简体中文。
7. **iframe 必须可验证**：只嵌入当前主视频且默认 `autoplay=0`，至少比对标题/作者/时长/日期等两项；无法确认就写“待确认”或只留安全链接，绝不放错 iframe、不留坏 iframe。
8. **交付双件**：默认先给 Markdown 单文件链接，再给 ZIP 完整包；含截图时 ZIP 必交且内含 `assets/` 并保持相对路径可用；中间文件（音频、视频、模型、转写底稿、临时脚本）只放临时目录，不进最终工作区。

---

## 4. 参考文件索引（按需加载，缺一不可）

| 参考文件 | 承载的原内容 | 何时必须读取 |
| --- | --- | --- |
| [references/task-types.md](references/task-types.md) | 三类任务（A 知识笔记 / B 原生文稿 / C 网页清理）的完整定义、触发词、输出格式、内容来源、输出重点与默认规则 | 第 1 步判定类型时 |
| [references/content-fetching.md](references/content-fetching.md) | 证据优先级；视频/音频获取总则；工具缺失与反爬降级矩阵（L0-L4、降级整理模式）；B站/YouTube/抖音/小红书/播客分平台策略与通用 Fallback；平台处理要点汇总表 | 第 2 步获取任何链接内容时 |
| [references/transcription.md](references/transcription.md) | 音频转写判定规则（强制/可跳过场景、速查表）；Whisper 安装与备选方案、模型下载失败与 ffmpeg 缺失应对、模型选择表、强制参数、音频预处理、预期耗时与进度要求、转写后纠错表 | 第 3 步判定/执行转写时 |
| [references/output-format-rules.md](references/output-format-rules.md) | 核心规则 1-8：Obsidian 格式规范、排版规范、视频链接与 iframe 校验、语言与标题规范、frontmatter 与标签规范、关键帧截图与图片交付、文件命名、通用格式要求 | 第 4-5 步撰写与排版时 |
| [references/writing-standards.md](references/writing-standards.md) | A 类写作标准（五步流程、写作协议、精校六条、金句标准、去 AI 味完整版、排版红线、融合式结构、得意忘言、对谈协议、可选风格库）；B 类处理标准；C 类清理标准 | 第 4 步撰写正文时 |
| [references/templates.md](references/templates.md) | A 类视频知识笔记模板、B 类视频原生文稿模板、C 类公众号/网页文章模板 | 第 4 步创建文档骨架时 |
| [references/quality-assurance.md](references/quality-assurance.md) | 执行检查点（Pre-Delivery Checklist）、质量检查（QA 全部分项清单）、回复用户模板（A/B/C 示例） | 第 6 步生成前自查、交付前质检与最终回复时 |

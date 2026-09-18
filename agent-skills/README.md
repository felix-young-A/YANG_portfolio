# Agent Skills · 技能专区

本目录是个人 **AI Agent 技能（Skill）专区**：集中存放我编写、整理并持续迭代的技能。每个技能都是一个独立、自包含的文件夹，可直接复制到 Agent 的技能目录中使用。

## 技能索引

| 技能 | 简介 | 状态 |
| --- | --- | --- |
| [`link-to-fieldnote`](./link-to-fieldnote) | 将视频/音频/网页链接或本地音视频文件，转化为结构化的 Obsidian Field Note 或原生文稿；知识笔记、原生文稿、网页清理三类任务自动路由 | 可用 |

> 以后新增技能统一放在本目录下：一个技能一个同名文件夹，并在上表登记。

## 什么是 Skill

Skill 是模块化、自包含的能力文件夹，通过专门的工作流程、领域知识与工具集成，让通用 AI Agent 获得完成特定任务的专属能力。每个技能通常包含：

- `SKILL.md`（必需）：YAML frontmatter（`name`、`description`）+ 使用说明，Agent 据此判断何时触发；
- `references/`（按需）：执行过程中按需加载的参考文档、规范与模板；
- `scripts/`、`assets/`（按需）：可执行脚本与产出用资源。

## 目录结构

```text
agent-skills/
├── README.md                     # 本说明（专区说明 + 技能索引）
└── link-to-fieldnote/            # 技能：链接 → Field Note
    ├── SKILL.md
    └── references/
        ├── task-types.md
        ├── content-fetching.md
        ├── transcription.md
        ├── output-format-rules.md
        ├── writing-standards.md
        ├── templates.md
        └── quality-assurance.md
```

## 安装与使用

1. 将目标技能的整个文件夹（如 `link-to-fieldnote/`）复制到 Agent 的技能目录：
   - 豆包 / Codex 类环境：`workspace/.user_skills/`（或当前环境对应的 skills 根目录）；
   - 其他 Agent：参照其文档指定的技能加载目录。
2. 重启或刷新会话，Agent 会根据 `SKILL.md` 中的 `description` 自动识别触发场景。
3. 直接给出链接或文件并说明需求即可，例如"帮我做个 field note""转成逐字稿"。

## 编写与维护约定

- 一个技能一个文件夹，入口固定为 `SKILL.md`，frontmatter 只保留 `name` 与 `description`；
- 详细规范、模板、检查清单等长内容放入 `references/`，并在 `SKILL.md` 中写明"何时读取"，避免执行时模块混淆；
- 技能文件夹内不放 README / CHANGELOG 等辅助文档（本文件仅承担专区级的说明与索引）；
- 音频、视频、模型、转写底稿等中间产物不纳入版本库。

## 许可证

本专区内容遵循仓库根目录的 [MIT License](../LICENSE)。

---

维护者：[@felix-young-A](https://github.com/felix-young-A)

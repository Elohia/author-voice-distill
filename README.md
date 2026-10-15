# author-voice-distill · 作者风格蒸馏

> Agent Skill：把「像谁」这件事，从玄学变成可复现的流程。
> 通过**分轮访谈 + 真实语料实测 + 对抗性复现测试**，蒸馏一个作者的写作风格、世界观与创意母题，产出可反复注入写作的 `voice-profile.md`。

## 解决什么问题

规则库（humanizer / humanizer-zh / dbs-ai-check 一类）能做的是**减法**：去掉通用 AI 指纹。
但减法有天花板——**去掉第一种 AI 味，会得到第二种 AI 味（千篇一律）**。

真正的解法是**加法**：让文字像某个具体的人。本 skill 就是那个加法器。

## 三条硬前提（违反任何一条，产出都不可信）

1. **语料 > 自述** —— 作者「以为自己怎么写的」和「实际怎么写的」通常不一样；冲突时以语料为准并记进档案。
2. **访谈必须从上一轮的回答里长出来** —— 念题库得到的是问卷答案，不是人。
3. **验收只能靠盲测** —— 「我觉得像」无效，作者挑不出哪段是自己写的才算过。

## 流程（五阶段）

| 阶段 | 做什么 | 产出 |
|---|---|---|
| 0 · 语料优先 | 收真实文字（随笔 / 正式文本 / 愤怒现场），跑 `voice_stats.py` 实测 | 机器口径风格骨架 |
| 1 · 分轮访谈 | 4 轮 × 4–6 问，逐轮追问到具体事件 | 自我认知 / 世界观 / 审美 / 创意母题 |
| 2 · 对话采样 | ≥20 轮，覆盖放松 / 被激怒 / 解释复杂概念 / 讲具体故事 | 情绪峰值下的真实句式 |
| 3 · 落盘 | 产出 `voice-profile.md`，每个字段都是可执行约束，不是形容词 | 风格档案 |
| 4 · 应用与验收 | 盲测 + 对抗性复现，逐条回填档案 | 迭代后的档案 |

## 安装

放进任意 Agent 的 skills 目录即可（Claude Code / dsh / Codex 等均适用）：

```bash
# Claude Code
git clone https://github.com/Elohia/author-voice-distill ~/.claude/skills/author-voice-distill

# dsh
git clone https://github.com/Elohia/author-voice-distill <工作区>/.dsh/skills/author-voice-distill
```

## 使用

对 agent 说任意一句即可触发：

- 「学我的风格」「模仿 XX 写作」「让 AI 像我一样写」
- 「去 AI 味但保留我的声音」「以后按我的风格写」

语料实测脚本：

```bash
python scripts/voice_stats.py <语料文件或目录> [--json out.json]
python scripts/voice_stats.py 作者A/ --compare 作者B/ [--json diff.json]
```

退出码：`0` 成功 / `1` 语料为空 / `2` 参数错误。人读摘要走 stdout，机器口径写 `--json` 路径。

## 目录

```
author-voice-distill/
├── SKILL.md                 # 主流程：五阶段 + 铁律 + 验收判据
├── references/
│   └── 访谈与追问.md         # 访谈题库与追问范例（按需加载）
└── scripts/
    └── voice_stats.py       # 语料风格实测器（句长/标点/节奏，纯统计不改写）
```

## 与其他 skill 的分工

| 想要什么 | 用哪个 |
|---|---|
| 去掉通用 AI 指纹（减法） | humanizer / humanizer-zh / dbs-ai-check |
| **让文字像某个具体的人（加法）** | **本 skill** |
| 诊断某段文字有没有 AI 味 | dbs-ai-check |

**推荐顺序**：先本 skill 建 voice-profile → 写作时注入 → 再做减法 → 最后盲测验收。
反过来（先减法后加法）会失败：减法阶段删掉的，可能正是作者的个人特征。

## License

MIT

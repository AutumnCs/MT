# 架构文档

本目录保存当前架构、能力治理和前端结构说明。

## 当前文档

- [AGENT_HARNESS_SPEC.md](AGENT_HARNESS_SPEC.md)：能力编排和 agent harness 治理思路。
- [SKILL_SPEC.md](SKILL_SPEC.md)：能力/技能边界和回归治理。
- [FLUTTER_STRUCTURE.md](FLUTTER_STRUCTURE.md)：当前 Flutter 前端结构。

## 当前架构口径

- 前端：Flutter 路线输入页、澄清页、路线工作台、解释页、地图预览组件。
- 后端：FastAPI，按 core/services/policy/lexicon/eval/tools 分层。
- 智能链路：LLM-first 意图解析 + 本地规则归一化 + POI 召回 + 多因子排序 + Beam Search 路线组合。
- 地图链路：天地图优先，本地经纬度估算兜底。
- 上下文：会话、路线版本和轻量画像，画像只作为软偏置。

## 使用建议

如果是比赛报告或答辩，优先读 `docs/TECHNICAL_REPORT.md` 和 `docs/TECHNICAL_REPORT_DETAILED.md`。如果是代码修改，再读本目录文档。


# Muse - 现在就出发 文档索引

这是项目文档的当前入口。比赛提交、答辩准备、二次润色和开发调试都优先从这里进入。

## 当前权威文档

- [技术报告](TECHNICAL_REPORT.md)：比赛提交版，结构较收敛。
- [详细技术报告底稿](TECHNICAL_REPORT_DETAILED.md)：适合喂给 GPT 继续润色、压缩或生成 PPT。
- [项目介绍](specs/PROJECT_INTRODUCTION.md)：当前项目口径和能力说明。
- [项目要求整理](specs/PROJECT_REQUIREMENTS.md)：比赛需求与当前实现的对应关系。
- [后端说明](../backend/README.md)：后端模块与当前执行链路。
- [后端调试指南](../backend/BACKEND_GUIDE.md)：问题定位入口。

## 推荐阅读顺序

1. [../README.md](../README.md)
2. [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md)
3. [TECHNICAL_REPORT_DETAILED.md](TECHNICAL_REPORT_DETAILED.md)
4. [specs/PROJECT_INTRODUCTION.md](specs/PROJECT_INTRODUCTION.md)
5. [../backend/README.md](../backend/README.md)
6. [../backend/BACKEND_GUIDE.md](../backend/BACKEND_GUIDE.md)
7. [setup/QUICKSTART.md](setup/QUICKSTART.md)

## 文档分组

- `setup/`：启动命令、运行方式、评测命令。
- `specs/`：当前产品、上下文、多轮、记忆和优化规格。
- `architecture/`：架构、能力治理和前端结构说明。
- `legacy/`：历史方案和旧阶段记录，仅用于追溯，不作为当前实现依据。

## 当前口径

- 前端：Flutter。
- 后端：FastAPI。
- 城市：广州、上海。
- 数据：本地 POI 数据，当前 `pois.json` 为 125 个 POI。
- 意图解析：LLM-first，结合本地词典和 schema 归一化。
- 推荐链路：POI 召回、多因子排序、Beam Search 路线组合。
- 输出体验：路线工作台、多方案、时间线、解释、风险提示、地图预览。
- 多轮能力：基于当前路线和会话上下文做增量修改。
- 地图：天地图优先，本地经纬度估算兜底。

## 旧文档处理规则

如果 `docs/legacy/` 或旧计划文档中的内容与当前代码、README、技术报告冲突，以当前代码和本索引列出的权威文档为准。

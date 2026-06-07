# MeituanAgent

MeituanAgent 是一个面向本地生活场景的智能路线规划原型。用户用自然语言描述出行想法，系统将需求解析为结构化意图，再结合本地 POI 数据、多因子排序和路线组合算法，生成可执行、可解释、可修改的城市路线。

当前项目由 Flutter 客户端和 FastAPI 后端组成，支持广州、上海两个城市，核心演示链路包括：

- 自然语言路线生成
- 一轮轻量澄清
- 多策略路线方案
- 路线时间线与站点解释
- 路线继续修改
- 会话上下文与轻量画像
- 天地图预览与本地地图兜底
- 离线回归评测

## 当前主链路

1. 用户在 Flutter 首页输入自然语言需求，并可选择城市和偏好标签。
2. 后端采用 LLM-first 方式解析意图，并通过本地词典和 schema 做归一化。
3. 系统根据城市、类别、偏好、避让项、起点和必去点召回本地 POI。
4. POI 进入可解释多因子排序，综合偏好、评分、预算、时间、排队和拥挤风险。
5. 路线规划器通过 Beam Search 与启发式补全生成主路线和备选方案。
6. 前端展示路线工作台，包括摘要、方案切换、时间线、风险提示、地图预览和诊断信息。
7. 用户可以继续输入“太贵了”“不要排队”“更轻松一点”等修改要求，系统基于当前路线增量重排。

## 目录结构

- `lib/`：Flutter 客户端。
- `backend/`：FastAPI 后端与路线规划引擎。
- `backend/core/`：接口契约、意图解析、schema、能力注册、上下文模型。
- `backend/services/`：POI 召回、排序、路线规划、响应生成、地图服务、上下文存储。
- `backend/policy/`：排序和策略权重配置。
- `backend/lexicon/`：语义词典和展示标签。
- `backend/eval/`：离线评测和质量检查。
- `docs/`：当前文档入口、技术报告、规格和架构说明。

## 推荐阅读

1. `docs/TECHNICAL_REPORT.md`：比赛提交版技术报告。
2. `docs/TECHNICAL_REPORT_DETAILED.md`：详细技术报告底稿。
3. `backend/README.md`：后端当前执行路径。
4. `backend/BACKEND_GUIDE.md`：后端调试入口。
5. `docs/specs/PROJECT_INTRODUCTION.md`：项目介绍和当前口径。
6. `docs/specs/PROJECT_REQUIREMENTS.md`：比赛需求与实现对齐。

## 后端启动

```powershell
cd G:\MeituanAgent\backend
python -m pip install -r requirements.txt
python main.py
```

默认服务地址：

```text
http://127.0.0.1:8000
```

## 前端启动

```powershell
cd G:\MeituanAgent
flutter pub get
.\flutter.ps1 run -d windows
```

也可以使用本机 Flutter：

```powershell
flutter run -d windows
```

## 地图配置

后端地图服务优先使用天地图。配置服务端 key 后，后端可进行地理编码、POI 搜索、路线预览和地图诊断：

```powershell
$env:TDT_SERVER_KEY="你的天地图服务端Key"
cd G:\MeituanAgent\backend
python main.py
```

前端如需 WebView 地图 token，可通过 `--dart-define` 传入：

```powershell
.\flutter.ps1 run -d windows --dart-define=TDT_WEB_KEY=你的天地图浏览器端Token
```

没有配置地图 key 时，系统会自动使用本地经纬度估算和 Canvas/本地预览兜底，不影响路线生成、方案切换和路线修改演示。

## 离线评测

```powershell
cd G:\MeituanAgent\backend
python -m eval.eval_runner
```

当前本地评测口径：

- 数据集：`backend/eval_cases.json`
- 用例数：25
- 最近一次运行结果：25/25 通过

评测脚本会设置 `LLM_INTENT_DISABLE_LLM=1`，用于验证本地规则解析和后续规划链路稳定性。

## 常用调试入口

- 意图解析：`backend/core/intent_parser.py`
- LLM 解析：`backend/core/llm_intent_client.py`
- POI 召回：`backend/services/poi_retriever.py`
- POI 排序：`backend/services/ranker_engine.py`
- 路线规划：`backend/services/route_planner.py`
- 响应解释：`backend/services/response_generator.py`
- 上下文画像：`backend/services/context_service.py`
- 地图预览：`backend/services/map_service.py`
- 前端首页：`lib/main.dart`
- 路线结果页：`lib/pages/route_result_page.dart`

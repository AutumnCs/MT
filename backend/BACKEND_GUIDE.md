# Backend Guide

这份文档用于快速定位后端问题。

## 文件分组

| Area | What it owns |
|---|---|
| `backend/main.py` | FastAPI 路由入口 |
| `backend/core/` | schema、契约、意图解析、LLM 客户端、能力注册、上下文模型 |
| `backend/services/` | 召回、排序、路线规划、响应生成、地图、上下文存储 |
| `backend/policy/` | 可调策略权重 |
| `backend/lexicon/` | 语义词典和别名 |
| `backend/eval/` | 离线评测和回归 |
| `backend/tools/` | 数据维护脚本 |

## 常见问题入口

| Problem | First file to check |
|---|---|
| 意图解析不对 | `backend/core/intent_parser.py` |
| LLM JSON 异常或不可用 | `backend/core/llm_intent_client.py` |
| 澄清逻辑不符合预期 | `backend/services/route_service.py` |
| session/profile 记忆不对 | `backend/services/context_service.py` |
| POI 召回太少或太散 | `backend/services/poi_retriever.py` |
| POI 排序不合理 | `backend/services/ranker_engine.py` |
| 路线太绕、太短或顺序不对 | `backend/services/route_planner.py` |
| 站点解释或 trace 不完整 | `backend/services/response_generator.py` |
| 地图预览不对 | `backend/services/map_service.py` |
| 权重需要调整 | `backend/policy/poi_ranker_weights.json` |
| 词典需要扩充 | `backend/intent_lexicon.json` 或 `backend/lexicon/` |

## 当前设计规则

- LLM 负责自然语言结构化理解。
- 本地规则负责归一化、校验、回归和兜底。
- POI 排序必须保留可解释分项。
- 路线规划必须优先满足硬约束和必去点。
- 多轮修改应继承当前路线意图，并叠加本轮修改约束。
- 画像和上下文只能做软偏置。
- 地图服务可失败，路线生成不能因此中断。

## 常用命令

```powershell
cd G:\MeituanAgent\backend
python main.py
```

```powershell
cd G:\MeituanAgent\backend
python -m eval.eval_runner
```

```powershell
cd G:\MeituanAgent
python -m py_compile backend\main.py
```


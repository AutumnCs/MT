# Backend Overview

`backend/` 是 MeituanAgent 的路线规划引擎，负责自然语言意图解析、POI 召回、POI 排序、路线组合、响应解释、上下文记录和地图预览。

## 当前执行路径

1. `route_service.py` 接收路线生成或修改请求。
2. `llm_intent_client.py` 优先调用 LLM 解析意图。
3. `intent_parser.py` 对 LLM 结果做本地归一化，并合并词典/规则信号。
4. `route_service.py` 判断是否需要一轮澄清。
5. `constraint_checker.py` 校验意图和候选 POI。
6. `poi_retriever.py` 从 `pois.json` 召回候选。
7. `ranker_engine.py` 计算多因子排序分和推荐理由。
8. `route_planner.py` 通过 Beam Search 与启发式补全生成主路线和备选方案。
9. `response_generator.py` 生成前端可展示的路线、解释、风险提示和 trace。
10. `context_service.py` 记录会话事件、路线版本和轻量画像。
11. `map_service.py` 生成天地图/本地兜底路线预览。

## 目录说明

- `core/`：请求/响应契约、意图解析、schema、能力注册、上下文模型、提示模板。
- `services/`：路线生成主逻辑，包括召回、排序、规划、解释、地图、上下文。
- `policy/`：排序权重和策略配置。
- `lexicon/`：结构化语义词典和展示标签。
- `eval/`：离线回归和质量检查。
- `tools/`：POI 同步、扩充、维护脚本。

## 当前口径

- 主路径是 LLM-first。
- 本地规则用于归一化、兜底、评测和稳定约束。
- POI 排序真实实现是 `services/ranker_engine.py`，`services/poi_ranker.py` 是兼容入口。
- 地图主路径是天地图封装，本地经纬度估算兜底。
- 高德相关代码作为 POI 数据维护辅助，不是当前主地图服务路径。
- 画像只作为软偏置，不覆盖本轮明确需求。
- `context_service.py` 不应阻塞路线生成。

## 运行

```powershell
cd G:\MeituanAgent\backend
python -m pip install -r requirements.txt
python main.py
```

## 评测

```powershell
cd G:\MeituanAgent\backend
python -m eval.eval_runner
```

当前离线评测集为 `eval_cases.json`，最近一次本地运行 25/25 通过。


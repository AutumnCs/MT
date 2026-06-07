# backend/services

`services/` 负责实际路线规划工作。

## 文件说明

| File | Purpose |
|---|---|
| `route_service.py` | 路线生成/修改总编排，连接解析、澄清、召回、排序、规划和响应 |
| `context_service.py` | 会话存储、画像投影、路线版本记录 |
| `constraint_checker.py` | 意图和 POI 约束校验 |
| `poi_retriever.py` | 从本地 POI 数据召回候选 |
| `ranker_engine.py` | POI 多因子排序真实实现 |
| `poi_ranker.py` | 排序兼容入口，转发到 `ranker_engine.py` |
| `poi_ranker_policy.py` | 排序权重加载 |
| `review_analyzer.py` | 评论/描述信号分析 |
| `route_planner.py` | Beam Search 与启发式路线组合 |
| `response_generator.py` | 路线/澄清响应生成，包含解释、风险和 trace |
| `map_service.py` | 天地图封装和本地地图兜底 |
| `tianditu_client.py` | 天地图 HTTP 客户端 |
| `amap_client.py` | 高德数据维护辅助客户端 |

## 当前职责

- 从结构化意图召回候选 POI。
- 对 POI 做可解释多因子排序。
- 生成推荐方案、偏好优先版和紧凑少走版。
- 将路线转换成前端可展示、可修改、可解释的响应。
- 持久化轻量上下文和画像。
- 提供地图预览和本地兜底。

## 调试建议

- 路线形状不对：先看 `route_planner.py`。
- POI 选择不对：先看 `poi_retriever.py` 和 `ranker_engine.py`。
- 修改不生效：先看 `route_service.py` 的修改意图继承和 `ranker_engine.py` 的 `modification_penalty`。
- 地图不显示：先看 `map_service.py` 的 `get_status()` 和 trace 中的 `map_enabled`。

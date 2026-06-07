# 地图与 POI 集成口径

当前主口径：后端路线规划先基于本地 POI 和语义策略完成“懂用户、会选点、能成线”的规划；地图服务用于坐标校验、路线预览、距离/时间补充和演示增强。当前运行链路以天地图封装为主，本地经纬度估算作为兜底。高德相关工具保留为 POI 数据同步和维护辅助，不作为当前主地图服务口径。

## 1. 分工原则

- MeituanAgent 负责意图理解、POI 召回、POI 排序、路线组合、解释和修改。
- 天地图负责地理编码、POI 搜索、路线预览和坐标/路径辅助。
- 本地兜底负责在未配置地图 key 或外部接口异常时继续提供路线距离、时间估算和预览折线。
- 地图服务不替代用户偏好理解，也不直接决定路线主题。
- POI 语义标签、评论信号、偏好适配和路线解释保留在本地业务数据中。

## 2. 当前流程

1. 用户输入自然语言需求。
2. 后端解析结构化意图。
3. 本地 POI 根据城市、类别、偏好、避让项、起点和必去点召回。
4. 多因子排序计算 POI 推荐分和推荐理由。
5. 路线规划器生成主方案和备选方案。
6. `map_service.py` 根据路线站点生成 marker、polyline、bounds、center 和 segments。
7. 如果配置天地图 key，则优先尝试天地图搜索、地理编码和路线数据。
8. 如果未配置 key 或接口不可用，则使用本地经纬度和 Haversine 估算兜底。
9. 前端展示地图预览、站点编号、路线折线和地图来源诊断。

## 3. POI 字段要求

当前 POI 数据应尽量包含以下字段：

- `id`
- `name`
- `category`
- `sub_category`
- `city`
- `district`
- `address`
- `business_area`
- `area_cluster`
- `area_label`
- `latitude`
- `longitude`
- `provider`
- `provider_poi_id`
- `adcode`
- `source_updated_at`
- `geocoded_confidence`
- `tags`
- `suitable_for`
- `review_keywords`
- `positive_reviews`
- `negative_reviews`
- `review_signals`
- `rating`
- `price`
- `visit_duration`
- `business_hours`
- `indoor_outdoor`
- `queue_level`

其中，`area_cluster` 和 `area_label` 是路线规划的重要字段，用于控制路线紧凑性和减少跨城/跨区跳跃。

## 4. 天地图适合做什么

- 地址转坐标。
- 坐标反查地址。
- POI 搜索和候选校验。
- 路线预览 polyline。
- 路线距离和时间补充。
- 地图来源诊断。

## 5. 本地算法保留什么

- 自然语言意图解析。
- 偏好、避让项、节奏和交通方式归一化。
- POI 业务语义标签。
- 评论信号和体验分。
- POI 多因子排序。
- 多站路线组合。
- 路线修改策略。
- 站点解释和风险提示。

## 6. 高德相关工具说明

仓库中保留 `amap_client.py` 和 `tools/amap_poi_sync.py`，用于 POI 数据同步、校验或维护。它们不是当前主地图服务路径。当前 API 层和路线预览层以 `map_service.py` 的天地图封装和本地兜底为准。

## 7. 一句话总结

路线规划由 MeituanAgent 本地语义和算法链路负责，地图服务用于补充真实地理能力；当前主地图口径是“天地图优先，本地兜底，高德工具辅助维护”。

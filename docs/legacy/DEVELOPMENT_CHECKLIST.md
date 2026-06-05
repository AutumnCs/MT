# 开发改造清单

这份文档把题目要求拆成“要改什么、改哪里、怎么验收”。

## 1. 先改什么

优先级建议：

1. 结果解释和可读性
2. 路线修改体验
3. 路线稳定性和可执行性
4. 数据和评分配置化
5. 地图 API 接入

## 2. 按模块拆改

### 2.1 意图解析

目标：让用户一句自然语言能稳定变成结构化需求。

改动点：

- [backend/llm_intent_client.py](/g:/MeituanAgent/backend/llm_intent_client.py)
- [backend/intent_parser.py](/g:/MeituanAgent/backend/intent_parser.py)
- [backend/main.py](/g:/MeituanAgent/backend/main.py)

建议改法：

- 先尝试 LLM，失败就回退规则解析
- 统一 `ParsedIntent` 字段，不要让前后端各说各话
- 把系统解析出的城市、预算、时间、偏好返回给前端展示

验收标准：

- 用户一句话输入后，能得到稳定的结构化意图
- 没有 key 也能跑通
- 用户能看到系统理解到的内容

### 2.2 数据层

目标：让 POI 数据足够支撑路线生成。

改动点：

- [backend/pois.json](/g:/MeituanAgent/backend/pois.json)
- [backend/poi_retriever.py](/g:/MeituanAgent/backend/poi_retriever.py)
- [backend/schemas.py](/g:/MeituanAgent/backend/schemas.py)

建议改法：

- 事实数据和可调参数分层
- POI 至少补齐城市、经纬度、类别、价格、营业时间、标签、适合人群
- 评分类字段尽量统一含义，不要混着写

验收标准：

- 广州、上海都能召回足够多候选点
- 数据字段统一，不会因为缺字段导致流程断裂

### 2.3 评分和排序

目标：让推荐结果更像“合理路线”，而不是随机拼接。

改动点：

- [backend/poi_ranker.py](/g:/MeituanAgent/backend/poi_ranker.py)
- [backend/review_analyzer.py](/g:/MeituanAgent/backend/review_analyzer.py)

建议改法：

- 把权重配置化，不要硬写死
- 保留每个 POI 的 `score_breakdown`
- 推荐理由要能说明“为什么选中它”

验收标准：

- 同一输入不会出现明显随机结果
- 能解释推荐原因
- 能根据偏好、预算、排队、时间产生差异

### 2.4 路线规划

目标：把多个 POI 串成能走的路线。

改动点：

- [backend/route_planner.py](/g:/MeituanAgent/backend/route_planner.py)
- [backend/response_generator.py](/g:/MeituanAgent/backend/response_generator.py)

建议改法：

- 默认生成多候选路线，不只给单一路线
- 保证至少 3 个 POI 的可执行路线尽量优先
- 超时、绕路、排队等风险要显式提示

验收标准：

- 能生成有顺序、有时间、有总时长的路线
- 能给出多个方案供选择
- 用户能看懂为什么这么排

### 2.5 前端体验

目标：让用户“更容易开口、等得明白、改得动、看得懂”。

改动点：

- [lib/main.dart](/g:/MeituanAgent/lib/main.dart)
- [lib/pages/route_result_page.dart](/g:/MeituanAgent/lib/pages/route_result_page.dart)
- [lib/services/route_api_service.dart](/g:/MeituanAgent/lib/services/route_api_service.dart)

建议改法：

- 首页增加清晰的示例和快速偏好入口
- loading 按阶段展示：理解需求 / 筛选站点 / 生成路线 / 整理结果
- 结果页展示：系统理解、路线理由、风险提醒、候选方案
- 修改入口改成快捷按钮 + 文本输入

验收标准：

- 用户不看文档也能知道怎么用
- 用户知道系统在做什么
- 用户能快速修改路线

## 3. 从用户体验出发的必须改项

### 3.1 让结果可信

必须展示：

- 系统理解到的城市、预算、时间、偏好
- 路线为什么这么排
- 每个站点为什么被选中
- 有哪些风险

### 3.2 让修改简单

必须支持：

- 太远了
- 不想排队
- 预算低一点
- 再轻松一点
- 多一点拍照点

### 3.3 让错误可恢复

必须把错误说清楚：

- 条件太严格
- 当前城市没有结果
- 时间窗口不合理
- 后端切到回退模式

## 4. 以后再做什么

在当前版本跑稳以后，再做：

- 地图 API 接入
- 更真实的距离和时间
- 更大的 POI 数据集
- 离线评估集
- 权重配置面板

## 5. 最小可行改造顺序

如果你现在就要动手，推荐顺序是：

1. 先把 `ParsedIntent` 和响应解释补全
2. 再把 POI 数据分层
3. 再把评分权重抽到配置
4. 再把前端修改入口和 loading 做顺
5. 最后再接地图 API

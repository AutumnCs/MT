# 记忆与画像代码落地任务表

这份表只做一件事：把 `MEMORY_SPEC.md` 变成可以直接开工的代码任务。

目标是：
- 泛化能力更强
- 画像更准
- 路线修改更稳
- 系统不变重

---

## 第一阶段：先把数据结构定住

### 1. 新增会话状态对象

建议文件：
- `backend/core/session_state.py`
- `backend/core/contracts.py`

建议字段：
- `session_id`
- `current_city`
- `current_route_id`
- `turn_mode`
- `last_user_intent`
- `last_patch`
- `clarification_question`
- `clarification_answer`
- `confirmed_constraints`
- `confirmed_preferences`

目的：
- 让多轮对话有稳定上下文
- 支持“刚才那个”“再轻松一点”这种修改

---

### 2. 新增画像对象

建议文件：
- `backend/core/profile.py`
- `backend/core/contracts.py`

建议字段：
- `home_city`
- `frequent_cities`
- `preferred_budget_band`
- `preferred_duration_band`
- `preferred_pace`
- `preferred_transport`
- `preferred_companions`
- `scene_preferences`
- `style_preferences`
- `avoid_preferences`

目的：
- 给生成路线提供长期默认偏好
- 让系统越用越懂用户

---

### 3. 新增行为事件对象

建议文件：
- `backend/core/behavior_events.py`
- `backend/core/contracts.py`

建议字段：
- `event_type`
- `route_id`
- `choice`
- `patch`
- `timestamp`
- `source`

目的：
- 用行为反哺画像
- 让收藏、修改、复制都能成为偏好证据

---

## 第二阶段：把读写入口统一

### 4. 新增记忆服务层

建议文件：
- `backend/services/memory_service.py`

职责：
- 读取当前会话状态
- 更新画像
- 记录行为事件
- 维护路线版本
- 处理记忆衰减和冲突

目的：
- 不让记忆逻辑散落在 `route_service.py`
- 所有记忆更新都走统一入口

---

### 5. 新增画像更新规则

建议文件：
- `backend/policy/profile_rules.json`
- `backend/services/memory_service.py`

建议规则：
- `explicit` > `behavior` > `session` > `weak_inference`
- 最近一次明确表达优先
- 行为重复优先于单次表达
- 长期未命中的标签自动降权

目的：
- 让画像可控、可衰减、可回放

---

## 第三阶段：把多轮补丁化

### 6. 新增 patch 结构

建议文件：
- `backend/core/patches.py`
- `backend/core/contracts.py`

建议 patch 类型：
- `budget_delta`
- `pace_change`
- `avoid_queue`
- `prefer_indoor`
- `add_categories`
- `remove_categories`
- `time_window_change`
- `transport_change`

目的：
- 让修改路线不再是“重新猜一次”
- 而是明确地对现有方案做结构化更新

---

### 7. 统一修改流程

建议改动：
- `backend/services/route_service.py`
- `backend/services/route_planner.py`
- `backend/core/intent_parser.py`

目标：
- 用户输入先识别成 patch
- patch 合并到当前路线
- 再重新打分和规划

---

## 第四阶段：让画像反哺路线

### 8. 在意图解析里加入画像默认值

建议改动：
- `backend/core/intent_parser.py`
- `backend/core/llm_intent_client.py`
- `backend/services/route_service.py`

用途：
- 用户没说全时，用画像补默认值
- 让首用体验更像“懂你”

---

### 9. 在打分里引入画像偏置

建议改动：
- `backend/services/ranker_engine.py`
- `backend/services/poi_ranker.py`
- `backend/policy/poi_ranker_weights.json`

用途：
- 用户长期偏好的场景、节奏、交通方式，能直接影响 POI 排序

---

### 10. 在路线生成里支持版本演进

建议改动：
- `backend/services/route_planner.py`
- `backend/services/response_generator.py`

用途：
- 路线 v1 / v2 / v3 可追踪
- 用户可以看懂修改前后差异

---

## 第五阶段：把事件写回画像

### 11. 让收藏、复制、修改都能写回画像

建议改动：
- `lib/pages/route_result_page.dart`
- `backend/services/route_service.py`
- `backend/services/memory_service.py`

建议事件：
- `route_favorited`
- `route_copied`
- `route_modified`
- `route_rejected`
- `clarification_answered`

用途：
- 用真实行为修正口头表达
- 避免画像只靠用户自述

---

## 第六阶段：补前端可见状态

### 12. 在前端展示当前记忆信号

建议页面：
- 首页
- 路线结果页
- 澄清页

建议显示：
- 当前城市
- 当前偏好摘要
- 当前方案类型
- 当前修改方向

用途：
- 让用户知道系统为什么这么推荐
- 增强信任感

---

## 最小可用版本

如果先做一个最小版本，建议顺序是：

1. `session_state`
2. `profile`
3. `behavior_events`
4. `memory_service`
5. `patch` 结构
6. `route versioning`

这样就已经能支撑：
- 多轮修改
- 路线个性化
- 画像沉淀
- 泛化增强

---

## 暂时不要做重的

- 不要先做大而全的 memory hub
- 不要先把所有聊天历史全量入库
- 不要先把画像字段扩到几十个
- 不要先做重型 agent 编排来替代记忆系统

---

## 结论

记忆和画像要真正提升泛化能力，关键不是“记更多”，而是：

- 记得准
- 记得稳
- 记得可衰减
- 记得能回放
- 记得能反哺路线


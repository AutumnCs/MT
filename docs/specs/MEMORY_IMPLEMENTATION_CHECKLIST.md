# 记忆与画像实现清单

这份清单的目标是：在不把系统做重的前提下，把记忆和画像做成真正能提升泛化能力的功能。

## 原则

- 记忆只存能影响结果的东西。
- 画像只收高置信、可验证、可衰减的信息。
- 修改行为比单次表达更值得写入画像。
- 长尾信息先保留，不要硬塞进稳定画像。
- 一切记忆都要有来源、有时间、有权重。

## 1. 会话记忆要存什么

会话记忆只放当前轮最有用的信息，不放长篇自由文本。

建议字段：
- `session_id`
- `current_city`
- `current_route_id`
- `turn_mode`
  - `generate`
  - `clarify`
  - `modify`
  - `confirm`
- `last_user_intent`
- `last_patch`
- `clarification_question`
- `clarification_answer`
- `confirmed_constraints`
- `confirmed_preferences`

用途：
- 支持连续修改
- 支持一轮澄清后继续生成
- 支持“刚才那个”“再轻松一点”这种短链路跟进

## 2. 画像记忆要存什么

画像记忆只存稳定偏好，不存临时情绪。

建议字段：
- `home_city`
- `frequent_cities`
- `preferred_budget_band`
- `preferred_duration_band`
- `preferred_pace`
- `preferred_transport`
- `preferred_companions`
- `scene_preferences`
  - `date`
  - `friends`
  - `family`
  - `solo`
  - `citywalk`
  - `shopping`
  - `food_first`
  - `photo_first`
  - `culture_first`
  - `night_view`
- `style_preferences`
  - `relaxed`
  - `efficient`
  - `compact`
  - `quiet`
  - `popular`
  - `local_feature`
  - `indoor_pref`
  - `outdoor_pref`
- `avoid_preferences`
  - `avoid_queue`
  - `avoid_crowded`
  - `avoid_far`
  - `avoid_high_price`
  - `avoid_tiring`

用途：
- 首次输入时给默认偏好
- 生成路线时自动带入
- 让系统逐步“懂用户”

## 3. 行为记忆要存什么

行为比口头描述更能反映真实偏好。

建议记录：
- 收藏了什么路线
- 复制了什么摘要
- 修改了几次
- 每次修改朝什么方向
- 选中了哪个方案
- 哪些推荐被忽略

建议统计：
- `favorite_count`
- `copy_count`
- `modify_count`
- `route_choice_pattern`
- `change_direction_pattern`

用途：
- 补充显式画像的不足
- 判断真实偏好是否和口头表达一致
- 提高长期推荐质量

## 4. 知识记忆要存什么

这是系统侧的稳定知识，不是用户画像。

建议字段：
- `intent_lexicon_version`
- `capability_version`
- `policy_version`
- `route_strategy_version`
- `poi_source_version`
- `city_aliases`
- `display_labels`

用途：
- 让模型更容易理解用户
- 让路由更稳定
- 让调参和改词不影响整体结构

## 5. 写入规则

### 可以写入长期画像的信号
- 用户明确说“我喜欢轻松路线”
- 用户连续 3 次把路线改成轻松 / 少排队 / 更近
- 用户收藏的路线稳定集中在某类场景
- 用户经常选择同一交通方式

### 不写入长期画像的信号
- 一次性临时需求
- 低置信度猜测
- 还没确认的澄清答案
- 单次草稿输入

## 6. 权重建议

建议给每条画像打一个稳定权重。

可以用下面的来源分级：

- `explicit`：用户明确表达，权重最高
- `behavior`：行为推断，中高权重
- `session`：当前会话，短期有效
- `weak_inference`：弱推断，权重最低

建议初始化：
- `explicit = 0.9`
- `behavior = 0.7`
- `session = 0.5`
- `weak_inference = 0.2`

## 7. 衰减规则

画像要随着时间慢慢衰减。

建议保留：
- `first_seen_at`
- `last_seen_at`
- `hit_count`
- `confidence`
- `decay_score`

衰减方式建议：
- 时间越久，权重越低
- 命中越频繁，权重越高
- 最近一次命中优先

## 8. 冲突规则

当新旧画像冲突时，优先级建议如下：

1. 当前 session 明确表达
2. 最近修改行为
3. 长期稳定行为
4. 旧画像

如果冲突长期存在，就保留两个维度，但降低其中一个的权重，而不是直接删掉。

## 9. 路线如何反哺画像

每次路线生成或修改，都可以反哺画像。

例如：
- 用户一开始选 `photo`
- 但多次改成 `relaxed`
- 最后收藏的也是轻松路线

那么画像要慢慢偏向：
- `photo`
- `relaxed`
- `avoid_queue`

建议重点监听这些事件：
- `route_created`
- `route_modified`
- `route_favorited`
- `route_copied`
- `route_rejected`
- `clarification_answered`

## 10. 轻量实现建议

为了不把系统做重，建议先做这 4 个对象：

- `session_context`
- `route_versions`
- `profile_store`
- `behavior_events`

先有这 4 个，再慢慢扩展，不要一开始就做成重型 memory hub。

## 11. 泛化能力怎么保证

泛化能力不是靠记更多词，而是靠：

- 稳定画像字段
- 高置信 alias
- 行为补强
- 路线 patch
- 回归样例
- 画像衰减

也就是说，**记忆不是越多越好，而是越能稳住“用户真实偏好”越好**。

## 12. 最终目标

这套记忆和画像系统最终要做到：

- 首次使用能快速给出合理默认值
- 多轮修改不会丢上下文
- 用户越用越像“被理解”
- 画像不会被一次性临时需求污染
- 后续优化时能看见证据，而不是凭感觉改


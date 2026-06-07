# Agent Harness Spec

这份文档定义的是 `Muse - 现在就出发` 的**工程化运行骨架**，不是模型提示词规范。

如果说 `SKILL_SPEC.md` 解决的是“我们有哪些能力、怎么收口”，那这份文档解决的是：

- 能力怎么被注册
- 工具怎么被调用
- 结果怎么被追踪
- 改动怎么被回归
- 失败怎么被兜底
- 版本怎么被管理

一句话：**skill 负责收口，harness 负责跑起来。**

## 1. Harness 的目标

1. 降低 ReAct 这种纯 agent 循环的 token 和调用成本
2. 把“意图理解、路线规划、地图查询、结果解释”分层
3. 让每次请求都有 trace，可以回放、排障、回归
4. 让新能力能按统一标准接入，而不是靠临时 patch
5. 让 fallback 可预测，而不是随机胡猜

## 2. Harness 组成

### 2.1 Capability Registry

能力注册表，记录系统支持什么、输入输出是什么、依赖什么、怎么测试。

建议字段：

- `name`
- `canonical_tags`
- `aliases`
- `inputs`
- `outputs`
- `constraints`
- `fallbacks`
- `tests`
- `version`
- `owner`

用途：

- 自动知道某个请求该走哪个 skill
- 自动生成文档索引
- 自动检查新改动影响哪些回归样例

### 2.2 Tool Contracts

所有工具都要有稳定输入输出，不要靠上下文猜字段。

当前建议固定的工具契约：

- `intent.parse`
- `route.generate`
- `route.modify`
- `map.status`
- `map.geocode`
- `map.reverse_geocode`
- `map.poi_search`
- `map.route`
- `map.preview`
- `eval.run`

每个工具都应该明确：

- 必填字段
- 可选字段
- 失败返回格式
- fallback 行为
- 版本号

### 2.3 Policy Layer

策略层负责决定“怎么做”，而不是“做什么”。

建议放这里的内容：

- 权重
- 阈值
- 标签归一规则
- 路线偏好优先级
- 路线重规划策略
- token / tool budget

### 2.4 Trace Layer

每次请求都要保留 trace，方便回放。

建议记录：

- 原始 query
- city / budget / time 等关键字段
- 解析后的 intent
- 命中的 alias
- `unclassified_clues`
- 候选 POI 数量
- 打分结果
- 路线选择结果
- 是否触发 fallback
- 是否触发地图服务

### 2.5 Eval Layer

离线回归是 harness 的门禁。

建议每次改动前后都要跑：

- intent 回归
- modify 回归
- unknown clue 回归
- map fallback 回归

## 3. 推荐的调用链

### 3.1 首次生成

1. 用户输入自然语言
2. `intent.parse` 先归一成结构化意图
3. `route.generate` 做 POI 检索、打分、规划
4. `map.preview` 生成地图预览数据
5. `route.explanation` 生成用户可见解释
6. `eval` 记录是否命中预期

### 3.2 修改路线

1. 用户输入修改要求
2. `intent.parse` 识别修改意图
3. `route.modify` 尽量继承原路线上下文
4. `route.generate` 重算
5. `map.preview` 更新预览

### 3.3 地图能力

1. 先查 `map.status`
2. 有天地图 key 就走天地图 Web 服务
3. 没 key 就走 local fallback
4. 前端只消费统一的预览结构

## 4. 预算控制

为了省 token，也为了稳定，要有预算限制。

建议限制：

- 每次请求最多 1 次主 LLM 解析
- 修改请求最多 1 次补全
- 不允许无限 retry
- 不允许无限 tool loop
- 超预算时直接回到保守 fallback

## 5. 失败策略

推荐 fallback 顺序：

1. 词典命中
2. 规则归一
3. LLM 补全
4. 未知表达保留
5. 本地路线估算
6. 空结果提示

原则：

- 可以保守，不要胡编
- 可以少推荐，不要乱推荐
- 可以解释不完整，不要假装很确定

## 6. 版本化

以下内容都应该版本化：

- prompt
- lexicon
- skill registry
- routing policy
- ranking config
- eval cases
- map adapter

建议每次改动都记录：

- `version`
- `changed_by`
- `changed_at`
- `change_reason`
- `impacted_cases`

这样后面才能回答：

- 这次结果为什么变了
- 是词典变了，还是策略变了
- 是模型变了，还是地图变了

## 7. 与 skill 的关系

`SKILL_SPEC.md` 定义“能力边界”和“治理标准”。

`AGENT_HARNESS_SPEC.md` 定义“这些能力如何被工程化运行”。

对应关系可以理解成：

- skill = 能力目录
- harness = 执行框架
- policy = 行为规则
- eval = 质量门禁

## 8. 当前项目最该先补的 5 件事

1. Capability Registry
2. Request Trace
3. Tool Contracts
4. Policy Versioning
5. Eval Gate

这五件事做完，后面的泛化和扩展会轻松很多。

## 9. 一句话总结

这套 harness 的目的不是让 agent 更“会想”，而是让它：

- 更省 token
- 更稳定
- 更容易排障
- 更容易扩展
- 更容易回归

这才是可持续的 agent 工程化。

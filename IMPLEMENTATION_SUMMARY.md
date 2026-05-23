# "取其精华" 实施总结

## 核心理念

**不搬项目，只抽能力。**

保留现有 Flutter + FastAPI 主骨架，从 poi(1) 中提炼：
- 字段设计
- 排序思路
- 调度逻辑
- 路线优化方法

---

## 已完成的四层改进

### 一、POI 字段设计（优先级1）✅

#### 改进内容

从 poi(1) 提炼了以下字段设计思路，扩充了 `backend/pois.json`：

**新增核心字段：**
- `district` - 区域（黄浦区、静安区等）
- `sub_category` - 子类别
- `business_hours` - 营业时间
- `suitable_for` - 适合人群
- `visit_duration` - 建议游览时长
- `queue_level` - 排队等级（1-5）
- `photo_score` - 拍照指数（1-5）
- `date_score` - 约会指数（1-5）
- `food_score` - 美食指数（1-5）
- `culture_score` - 文化指数（1-5）
- `local_feature_score` - 本地特色指数（1-5）
- `rainy_day_score` - 雨天适配指数（1-5）
- `indoor_outdoor` - 室内/室外/both

#### 数据城市切换

根据需求，将 POI 数据体系从广州改为**上海**，包含：
- 20个精选上海 POI
- 覆盖：黄浦区、静安区、徐汇区、浦东新区
- 涵盖：咖啡、餐饮、博物馆、展览、景点、街道、购物、公园、夜景等类型

#### 改进文件
- `backend/pois.json` - 扩充字段 + 上海数据

---

### 二、POI 评分模块（优先级2）✅

#### 改进内容

新建 `backend/poi_ranker.py`，实现可解释的评分框架：

```python
final_score = (
    0.25 × preference_match_score   # 偏好匹配
    + 0.20 × semantic_score         # 语义评分
    + 0.15 × rating_score          # 评分质量
    + 0.15 × category_match_score  # 类别匹配
    + 0.10 × budget_score          # 预算适配
    + 0.10 × time_suitability_score # 时段适配
    - 0.15 × queue_penalty         # 排队惩罚
    - 0.10 × crowd_penalty         # 拥挤惩罚
)
```

#### 评分维度

1. **类别匹配分** - 是否匹配用户想要的类型
2. **偏好匹配分** - 匹配用户意图标签、适合人群
3. **语义评分** - photo_score、date_score、food_score 等多维评分
4. **预算适配分** - 与用户预算的匹配程度
5. **时段适配分** - 夜景、节奏快慢等时间相关
6. **评分质量分** - 基于原始评分的质量衡量
7. **排队惩罚** - 排队等级高则扣分
8. **拥挤惩罚** - 人多场所则扣分

#### 推荐理由生成

每个 POI 自动生成可解释的推荐理由：
- "匹配用户的美食需求，food_score 较高"
- "适合文化历史偏好，culture_score 较高"
- "但存在一定排队风险，建议错峰前往"

#### 改进文件
- `backend/poi_ranker.py` - 新建评分模块

---

### 三、偏好解析增强（优先级2）✅

#### 改进内容

升级 `backend/intent_parser.py`，从 poi(1) 的 `preference_parser.py` 中提炼：

#### 新增解析能力

1. **预算解析**
   - 显式：`预算 200`
   - 隐式：`低预算` → 100元, `中等预算` → 200元

2. **节奏解析**
   - `轻松`、`慢慢逛` → slow
   - `紧凑`、`高效` → fast
   - 其他 → normal

3. **时间解析**
   - 增强时间格式识别
   - 支持：`上午10点`、`下午2点半`、`14:00`

4. **偏好关键词**
   - 新增：local_feature（本地特色）
   - 新增：quiet（安静）
   - 新增：rainy_day（雨天适配）
   - 增强：couple、photo、food、culture、night_view

5. **规避关键词**
   - 新增：crowded（人少需求）
   - 增强：queue（不想排队）

#### 改进文件
- `backend/intent_parser.py` - 增强偏好解析

---

### 四、时间调度逻辑（优先级3）✅

#### 改进内容

升级 `backend/route_planner.py`，从 poi(1) 的 `time_scheduler.py` 中提炼：

#### 新增调度能力

1. **智能停留时长**
   - 根据类别限定范围：
     - 餐饮：50-120分钟
     - 咖啡：30-70分钟
     - 博物馆：70-150分钟
   - 根据节奏调整：
     - slow：×1.15
     - normal：×1.0
     - fast：×0.80

2. **交通时间估算**
   - 步行：`距离 × 12 分钟/km`
   - 打车：`距离 × 2 + 5 分钟`
   - 地铁：`距离 × 4 + 10 分钟`

3. **到达/离开时间计算**
   ```
   到达时间 = 前一站离开 + 交通时间
   离开时间 = 到达时间 + 停留时长
   ```

4. **超时裁剪**
   - 根据结束时间自动裁剪路线
   - 优先保留高优先级 POI

5. **风险提醒**
   - 排队等级≥4 且未规避排队 → "可能在高峰期排队"
   - 室外场所且偏好雨天 → "天气不好时可能影响体验"

#### 路线说明生成

自动生成自然语言路线说明：
- 包含类型多样性说明
- 包含偏好满足说明
- 包含预算控制说明
- 包含节奏安排说明

#### 改进文件
- `backend/route_planner.py` - 增强时间调度

---

## 数据模型同步

### 后端 Schema 升级 (`backend/schemas.py`)

```python
class POI(BaseModel):
    # ... 原有字段
    # 新增字段
    sub_category: Optional[str]
    district: Optional[str]
    visit_duration: int = 90
    business_hours: Optional[str]
    suitable_for: List[str]
    queue_level: int = Field(default=2, ge=1, le=5)
    photo_score: int = Field(default=3, ge=1, le=5)
    date_score: int = Field(default=3, ge=1, le=5)
    food_score: int = Field(default=3, ge=1, le=5)
    culture_score: int = Field(default=3, ge=1, le=5)
    local_feature_score: int = Field(default=3, ge=1, le=5)
    rainy_day_score: int = Field(default=3, ge=1, le=5)
    indoor_outdoor: str = "indoor"

class ParsedIntent(BaseModel):
    # ... 原有字段
    # 新增偏好字段
    prefer_couple: bool = False
    prefer_photo: bool = False
    prefer_food: bool = False
    prefer_culture: bool = False
    prefer_local_feature: bool = False
    prefer_night_view: bool = False
    prefer_quiet: bool = False
    prefer_rainy_day: bool = False
    avoid_queue: bool = False
    avoid_crowded: bool = False
    pace: str = "normal"
    transport_mode: str = "unknown"

class RouteStop(BaseModel):
    # ... 原有字段
    # 新增字段
    stay_minutes: int
    travel_from_previous: Optional[dict[str, Any]]

class RouteResponse(BaseModel):
    # ... 原有字段
    # 新增字段
    poi_count: int
    covered_types: List[str]
    route_explanation: str
    strategy_type: Optional[str]
    generated_at: Optional[str]
```

### 前端模型同步 (`lib/models/route_models.dart`)

同步所有新增字段到 Flutter 前端，包括：
- Poi 类的完整字段
- RouteStop 的停留时长和交通信息
- RouteResponse 的统计信息和路线说明

---

## 改进效果

### 路线质量提升

**从：**
- "条件过滤后随便排"

**到：**
- "按用户需求偏好做可解释排序"
- "智能时间调度确保路线可行"
- "自动生成推荐理由和风险提醒"

### 字段粒度提升

**从：**
```json
{
  "id": "gz-coffee-001",
  "name": "星巴克",
  "rating": 4.5
}
```

**到：**
```json
{
  "id": "sh-coffee-001",
  "name": "% Arabica 上海烘焙坊",
  "district": "黄浦区",
  "rating": 4.7,
  "queue_level": 2,
  "photo_score": 5,
  "date_score": 4,
  "food_score": 3,
  "business_hours": "08:00-20:00",
  "suitable_for": ["情侣", "闺蜜", "独自旅行"]
}
```

### 路线解释性提升

现在每条路线都会生成：
1. **路线说明** - 为什么这样安排
2. **推荐理由** - 为什么选这个点
3. **风险提醒** - 有什么需要注意的
4. **策略类型** - 是什么类型的路线（浪漫约会/性价比优先/拍照打卡/轻松路线）

---

## 未采用的内容

根据"去其糟粕"原则，以下内容未采纳：

1. ❌ 不搬整套项目架构
2. ❌ 不直接使用 poi(1) 的城市数据
3. ❌ 不直接抄复杂中文文案（自行编写干净、可控的表达）
4. ❌ 不一上来使用复杂 TSP/整数规划算法
5. ❌ 不使用有乱码的数据

---

## 下一步建议

1. **测试新功能**
   - 启动后端服务：`python backend/main.py`
   - 测试不同偏好组合
   - 验证时间调度准确性

2. **补充 POI 数据**
   - 可以继续补充更多上海 POI
   - 确保每个类别有足够的候选点

3. **优化评分权重**
   - 根据实际使用反馈调整权重
   - 可以做成可配置的参数

4. **扩展偏好维度**
   - 儿童友好
   - 无障碍设施
   - 宠物友好等

---

## 文件变更清单

### 新建文件
- `backend/poi_ranker.py` - POI 评分模块

### 修改文件
- `backend/pois.json` - 扩充字段 + 上海数据
- `backend/schemas.py` - 适配新字段
- `backend/intent_parser.py` - 增强偏好解析
- `backend/route_planner.py` - 增强时间调度
- `lib/models/route_models.dart` - 同步前端模型

---

## 总结

通过这次"取其精华"改进：

✅ **POI 字段更丰富** - 从 10+ 个字段扩展到 20+ 个字段
✅ **评分逻辑更智能** - 8 维度可解释评分
✅ **偏好解析更精准** - 10+ 种偏好识别
✅ **时间调度更合理** - 智能停留时长 + 交通估算
✅ **数据体系已切换** - 广州 → 上海

整体实现了从"推荐列表"到"可执行路线方案"的升级！

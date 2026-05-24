# Flutter 项目结构说明

## 1. 项目定位

这是一个基于 Flutter 的 AI 本地路线规划应用，核心目标是：

- 接收用户自然语言需求
- 生成可执行路线
- 支持二次修改
- 支持广州 / 上海双城样例

---

## 2. 目录结构

```text
lib/
├── main.dart                 # 应用入口，首页（需求输入页）
├── models/
│   └── route_models.dart     # 数据模型层
├── services/
│   └── route_api_service.dart # API 服务层
└── pages/
    └── route_result_page.dart # 路线结果页
```

---

## 3. 核心模块

### 3.1 数据模型层 `models/route_models.dart`

主要模型：

- `Poi`
  - 地点信息
  - 城市、区域、类别、评分、停留时长、排队、拍照、约会、本地特色等字段

- `RouteStop`
  - 路线中的单个站点
  - 包含到达时间、离开时间、停留时长、交通信息、推荐理由、风险提醒

- `RouteResponse`
  - 路线结果
  - 包含标题、摘要、总花费、总时长、总距离、站点数、覆盖类型、路线说明、策略类型

- `RouteRequest`
  - 首页请求
  - 包含 query、preferences、city

- `ModifyRequest`
  - 二次修改请求
  - 包含 query、originalQuery、currentRoute

---

### 3.2 API 服务层 `services/route_api_service.dart`

主要职责：

- `generateRoute(RouteRequest request)`
  - 调用后端 `/api/route/generate`
  - 后端不可用时自动 fallback 到 mock 数据

- `modifyRoute(ModifyRequest request)`
  - 调用后端 `/api/route/modify`
  - 后端不可用时自动 fallback 到 mock 数据

Android 模拟器默认访问：

```text
http://10.0.2.2:8000/api
```

桌面调试默认访问：

```text
http://127.0.0.1:8000/api
```

---

### 3.3 首页 `main.dart`

首页是“需求输入页”，核心组件包括：

1. 城市切换
   - 广州 / 上海

2. 快速偏好 chips
   - 约会
   - 拍照
   - 不想排队
   - 性价比
   - 轻松路线
   - 美食
   - 文艺
   - 夜生活

3. 多行输入框
   - 用户输入自然语言需求

4. 示例需求卡片
   - 一键填入测试样例

5. 主按钮
   - 生成路线

6. Loading 态
   - 正在分析需求
   - 正在生成路线

---

### 3.4 路线结果页 `pages/route_result_page.dart`

路线结果页主要展示：

1. 路线摘要
   - 标题
   - 总结
   - 总预算
   - 总时长
   - 总距离
   - 站点数

2. 方案标签
   - 当前策略类型

3. 路线时间轴 / 站点列表
   - POI 名称
   - 到达/离开时间
   - 停留时长
   - 价格/评分
   - 推荐理由
   - 风险提醒

4. 路线说明
   - 自然语言解释路线设计逻辑

5. 二次修改输入
   - 用户输入修改意见
   - 触发重新规划

6. 操作按钮
   - 返回
   - 重新规划

---

## 4. 页面流程

### 首次生成

```text
输入页 -> 点击生成路线 -> Loading -> 结果页
```

### 二次修改

```text
结果页输入修改意见 -> 应用修改 -> Loading -> 刷新结果页
```

### 重新开始

```text
结果页返回 -> 回到输入页
```

---

## 5. 技术栈

- Flutter 3.x
- Dart 3.x
- http 1.2.0
- StatefulWidget
- Material Design 3

---

## 6. 当前状态

当前版本已经能做到：

- 自然语言输入路线需求
- 生成路线结果页
- 展示站点顺序、时间、预算、推荐理由、风险提醒
- 支持结果页二次修改
- 支持广州 / 上海双城测试
- 后端不可用时自动降级为 mock 数据

---

## 7. 后续可继续补强的方向

- 增加错误边界与空状态
- 完善视觉规范和过渡动画
- 集成真实地图 SDK
- 引入更完善的状态管理方案
- 提升修改路线的智能程度


# Flutter 项目结构说明

## 项目概述

这是一个基于 Flutter 的 AI 路线规划应用，名为"现在就出发"（Meituan Agent）。

## 目录结构

```
lib/
├── main.dart                 # 应用入口，包含首页（需求输入页）
├── models/
│   └── route_models.dart    # 数据模型层
├── services/
│   └── route_api_service.dart # API服务层
└── pages/
    └── route_result_page.dart  # 路线结果页
```

## 核心功能模块

### 1. 数据模型层 (models/route_models.dart)

包含以下核心类：

- **Poi**: 地点/兴趣点模型
  - 属性：id, name, category, latitude, longitude, address, rating, priceRange等
  
- **RouteStop**: 路线站点模型
  - 属性：order, poi, arrivalTime, departureTime, stayDuration, estimatedCost, reason, riskAlert
  
- **RouteResponse**: 路线响应模型
  - 属性：routeId, title, summary, totalBudget, totalDuration, totalDistance, poiCount, coveredTypes, stops, routeExplanation, strategyType, generatedAt
  
- **RouteRequest**: 路线请求模型
  - 属性：query, preferences
  
- **ModifyRequest**: 修改请求模型
  - 属性：query, originalQuery, currentRoute

### 2. API服务层 (services/route_api_service.dart)

**RouteApiService** 类提供以下方法：

- `generateRoute(RouteRequest request)`: 生成新路线
  - 调用后端 `/api/route/generate` 接口
  - 如果后端不可用，使用mock数据作为fallback
  
- `modifyRoute(ModifyRequest request)`: 修改现有路线
  - 调用后端 `/api/route/modify` 接口
  - 如果后端不可用，使用mock数据作为fallback

**API配置**：
- Base URL: `http://localhost:8000/api`
- 超时时间: 30秒

### 3. 首页 - 需求输入页 (main.dart)

**PlannerInputPage** 组件包含：

1. **HeroCard（品牌区）**
   - 项目名："现在就出发"
   - 副标题："AI 本地路线规划"
   - 提示文案："描述你的行程，我来帮你规划"

2. **快速偏好选择区**
   - 支持的偏好标签：约会、拍照、不想排队、性价比、轻松路线、美食、文艺、夜生活
   - 点击标签会自动拼接到输入框中

3. **输入区**
   - 大号多行输入框
   - 占位文案贴合赛题场景
   - "生成路线"主按钮

4. **示例需求卡片**
   - 3个可点选的示例需求
   - 点击自动填入输入框

5. **加载态**
   - 显示"正在分析需求..."和"正在生成路线..."
   - 遮罩层防止重复提交

### 4. 路线结果页 (pages/route_result_page.dart)

**RouteResultPage** 组件包含：

1. **顶部结果摘要卡**
   - 路线标题
   - 路线总结
   - 统计信息：总预算、总时长、总距离、站点数

2. **方案标签区**
   - 显示当前方案类型（如：性价比优先、轻松路线等）

3. **路线时间轴/站点列表**
   - 每个站点卡片显示：
     - POI名称和类别
     - 到达/离开时间
     - 停留时长
     - 价格和评分
     - 推荐理由
     - 风险提醒（如果有）

4. **路线说明区**
   - 自然语言解释路线设计逻辑

5. **二次修改输入区**
   - 简洁的修改意见输入框
   - "应用修改"按钮

6. **操作按钮**
   - "重新规划"按钮
   - "返回修改需求"按钮

## 页面流程

### 首次生成流程
```
首页输入需求 -> 点击"生成路线" -> Loading态 -> 跳转到结果页
```

### 二次修改流程
```
结果页输入修改意见 -> 点击"应用修改" -> Loading态 -> 刷新结果页
```

### 重新开始流程
```
结果页点击"重新规划"或"返回修改需求" -> 返回首页
```

## 技术栈

- **Flutter**: 3.12.0+
- **Dart**: SDK 3.12.0
- **HTTP Client**: http 1.2.0
- **State Management**: StatefulWidget (当前阶段)
- **UI Framework**: Material Design 3

## 运行项目

### 1. 安装依赖
```bash
flutter pub get
```

### 2. 运行开发版本
```bash
flutter run
```

### 3. 构建调试 APK
```bash
flutter build apk --debug
```

### 4. 构建发布 APK
```bash
flutter build apk --release
```

## 注意事项

1. **Mock数据**: 当前版本在无法连接后端时会自动使用mock数据，确保页面流程可以完整演示。

2. **API端点**: 
   - 后端地址配置在 `route_api_service.dart` 中
   - 当前默认: `http://localhost:8000/api`
   - 需要根据实际部署环境修改

3. **地图集成**: 第一阶段先不做地图功能，在结果页预留"地图预览卡占位"。

4. **状态管理**: 当前使用简单的StatefulWidget，第二阶段可以考虑引入Provider或Riverpod。

## 待优化项

- [ ] 添加错误边界和空状态处理
- [ ] 完善颜色体系和视觉规范
- [ ] 添加页面切换动画
- [ ] 集成真实地图SDK
- [ ] 优化加载态文案和体验
- [ ] 添加更多交互反馈
- [ ] 考虑状态管理方案（Provider/Riverpod/Bloc）

## 后端接口对接

### 生成路线接口
- **端点**: `POST /api/route/generate`
- **请求体**:
```json
{
  "query": "周六下午从广州塔出发，预算200，想喝咖啡、看展、吃饭",
  "preferences": ["约会", "性价比"]
}
```

### 修改路线接口
- **端点**: `POST /api/route/modify`
- **请求体**:
```json
{
  "query": "太远了，换近一点的",
  "original_query": "周六下午从广州塔出发...",
  "current_route": { /* RouteResponse 对象 */ }
}
```

## 开发者提示

1. 所有UI组件都使用了圆角设计（borderRadius: 16-24）
2. 颜色方案以黄色为主色（Color(0xFFF2C230)）
3. 使用了渐变背景增强视觉效果
4. 响应式布局，适配不同屏幕尺寸
5. 代码遵循Material Design 3规范

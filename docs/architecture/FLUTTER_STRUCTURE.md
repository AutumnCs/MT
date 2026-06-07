# Flutter 前端结构

当前前端是 Flutter 路线工作台，不是早期纯聊天界面。主要目标是让用户自然输入需求，并以结构化方式查看、比较和修改路线。

## 主要文件

- `lib/main.dart`：应用入口和首页。包含城市选择、自然语言输入、偏好标签、推荐灵感、加载状态和路线生成跳转。
- `lib/models/route_models.dart`：前端路线、POI、方案、站点和响应模型。
- `lib/services/route_api_service.dart`：后端 API 调用封装。
- `lib/pages/route_result_page.dart`：路线结果工作台。包含摘要、系统理解、方案切换、时间线、诊断信息、路线修改和分享收藏。
- `lib/pages/clarification_page.dart`：澄清问题和选项。
- `lib/pages/knowledge_explanation_page.dart`：系统理解和推荐逻辑解释。
- `lib/widgets/route_map_view.dart`：地图预览统一入口。
- `lib/widgets/tianditu_route_map.dart`：天地图相关展示。
- `lib/widgets/virtual_route_map.dart`：本地/虚拟地图兜底展示。

## 当前页面流

1. 首页输入自然语言需求。
2. 前端调用后端解析和路线生成接口。
3. 如果后端返回澄清，进入澄清页。
4. 如果生成成功，进入路线结果页。
5. 用户可在路线结果页切换方案、查看解释、复制摘要、收藏和继续修改。
6. 修改路线时，前端把当前路线和修改文本传给后端。

## 当前交互重点

- 首页降低输入成本。
- 路线页强调路线可读、可比、可修改。
- 解释页增强信任。
- 地图预览增强路线空间感。
- 诊断信息用于开发和比赛答辩，不应喧宾夺主。

## 后续前端优化方向

- 多方案对比视图。
- 站点手动锁定、删除、替换。
- 修改前后差异展示。
- 分享卡片。
- 演示模式。
- 地图段落和转场信息更细化。

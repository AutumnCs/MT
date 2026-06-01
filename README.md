# MeituanAgent

这是一个面向比赛演示的 **AI 本地智能路线规划** 项目。

当前主技术栈：

- **Flutter**：移动端前端
- **FastAPI**：后端接口
- **本地双城样例数据**：当前支持 **广州 / 上海**
- **LLM 意图解析**：支持 DashScope / OpenAI，失败自动回退规则解析
- **UGC 信号模拟**：基于标签、描述、模拟评论推导偏好和风险信号

## 当前目录结构

- `lib/`
  Flutter 前端
- `android/`
  Flutter Android 工程
- `backend/`
  FastAPI 后端
- `backend/llm_intent_client.py`
  大模型意图解析客户端
- `backend/review_analyzer.py`
  本地 UGC / 评论信号分析层
- `COMMANDS.md`
  常用命令清单

---

## 当前已经能做什么

- 自然语言输入路线需求
- 有 API key 时使用大模型解析意图，无 key 时自动使用规则解析
- 生成路线结果页
- 展示站点顺序、时间、预算、推荐理由、风险提醒
- 展示路线评分、转场占比、候选方案
- 支持结果页二次修改输入
- 支持广州 / 上海双城市切换
- 基于经纬度 Haversine 距离 + 绕行系数估算交通时间
- 根据餐饮、咖啡、展览、夜景等类别做基础分时段适配
- 后端不可用时会自动降级为 mock 数据，保证演示流程不中断

---

## 快速开始

### 1. 启动后端

首次安装依赖：

```powershell
cd E:\Competition\meituan_ti5\v1\MT\backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

启动后端：

```powershell
cd E:\Competition\meituan_ti5\v1\MT\backend
..\.venv\Scripts\python.exe main.py
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

---

### 2. 启动 Flutter

先检查设备：

```powershell
cd E:\Competition\meituan_ti5\v1\MT
.\adb.ps1 devices
.\flutter.ps1 devices
```

运行到模拟器：

```powershell
cd E:\Competition\meituan_ti5\v1\MT
.\flutter.ps1 run -d emulator-5554
```

> 当前 `flutter.ps1` 里仍可能指向旧的 `G:` 盘 Flutter SDK。如果本机没有 `G:` 盘，需要先修正 `flutter.ps1` 里的 Flutter 路径。

---

## 大模型配置

后端会自动读取：

```text
backend/.env
v1/MT/.env
E:/Competition/meituan_ti5/poi/config/.env
```

可参考：

```text
backend/.env.example
```

DashScope 示例：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key
DASHSCOPE_MODEL=qwen-plus
LLM_TIMEOUT_SECONDS=20
```

OpenAI 示例：

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
LLM_TIMEOUT_SECONDS=20
```

如需强制关闭大模型：

```env
LLM_INTENT_DISABLE_LLM=1
```

---

## 推荐测试输入

### 广州样例

```text
周六下午两点从广州塔出发，预算 200，想约会，想喝咖啡、看展、吃饭，不想太累，晚上9点前结束
```

### 上海样例

```text
周末从外滩出发，预算 200，想拍照、喝咖啡、吃本帮菜，不想太累，晚上9点前结束
```

---

## 开发建议

日常优先看：

- [COMMANDS.md](E:/Competition/meituan_ti5/v1/MT/COMMANDS.md:1)

因为里面已经整理好了：

- 后端启动
- Flutter 运行
- 模拟器联调
- 热重载
- 端口占用排查
- Gradle / NDK 排障

---

## 当前项目状态

这一版已经从“原型壳子”进入“可联调、可演示”的阶段，并补上了题目要求里的关键路线规划能力：

1. LLM 意图解析接入
2. 本地 UGC / 评论信号分析
3. POI 多维排序
4. 多候选路线生成
5. 分时段适配
6. 路线评分、转场占比、风险提醒

后续最值得继续增强：

1. 扩充模拟 POI 与评论数据规模
2. 让 `modify` 支持更细粒度的局部替换
3. 增加地图式可视化展示
4. 用真实地图 API 替代当前经纬度估算

---

## 注意

如果后端已经在跑，再次启动时出现：

```text
WinError 10048
```

通常表示 `8000` 端口已经被占用，先检查端口占用，再决定是否重启服务。


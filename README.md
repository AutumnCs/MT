# MeituanAgent

一个面向比赛演示的 **AI 本地路线规划** 项目。

当前主技术栈：

- **Flutter**：移动端前端
- **FastAPI**：后端接口
- **本地双城样例数据**：当前支持 **广州 / 上海**

旧的 React / uni-app / HBuilderX 尝试已经归档到：

```text
G:\MeituanAgent\legacy
```

---

## 当前目录结构

- `lib/`
  Flutter 前端
- `android/`
  Flutter Android 工程
- `backend/`
  FastAPI 后端
- `legacy/`
  旧前端和历史尝试归档
- `COMMANDS.md`
  常用命令清单

---

## 当前已经能做什么

- 自然语言输入路线需求
- 生成路线结果页
- 展示站点顺序、时间、预算、推荐理由、风险提醒
- 支持结果页二次修改入口
- 支持广州 / 上海双城样例输入
- 后端不可用时前端会自动降级为 mock 数据，保证演示流程不断

---

## 快速开始

### 1. 启动后端

首次安装依赖：

```powershell
cd G:\MeituanAgent\backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

启动后端：

```powershell
cd G:\MeituanAgent\backend
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
cd G:\MeituanAgent
.\adb.ps1 devices
.\flutter.ps1 devices
```

运行到当前常用模拟器：

```powershell
cd G:\MeituanAgent
.\flutter.ps1 run -d emulator-5554
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

- [COMMANDS.md](G:/MeituanAgent/COMMANDS.md:1)

因为里面已经整理好了：

- 后端启动
- Flutter 运行
- 模拟器联调
- 热重载
- 端口占用排查
- Gradle / NDK 排障

---

## 当前项目状态

这版已经从“原型壳子”进入了“可联调、可演示”的阶段，但还有几块值得继续增强：

1. 结果页继续打磨成更像路线规划产品
2. `modify` 逻辑继续做强
3. 增加多方案输出
4. 接入大模型做更强的意图解析和结果解释
5. 视情况补地图展示

---

## 注意

如果后端已经在跑，再次启动时出现：

```text
WinError 10048
```

说明 `8000` 端口已被占用，不一定是坏了，通常是你已经有一个后端实例在运行。

这时优先先检查端口占用，再决定是否重启服务。具体命令见 [COMMANDS.md](G:/MeituanAgent/COMMANDS.md:1)。

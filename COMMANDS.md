# MeituanAgent 常用命令

这份文档只放两类内容：

1. 日常高频会用到的命令
2. 出问题时再查的排障命令

项目根目录：

```powershell
cd E:\Competition\meituan_ti5\v1\MT
```

---

## 一、日常开发

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

接口地址：

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

---

### 2. 查看设备

优先使用项目里封装好的脚本：

```powershell
cd E:\Competition\meituan_ti5\v1\MT
.\adb.ps1 devices
.\flutter.ps1 devices
```

---

### 3. 运行 Flutter 到模拟器

常用模拟器：

```powershell
cd E:\Competition\meituan_ti5\v1\MT
.\flutter.ps1 run -d emulator-5554
```

如果只想看当前可用设备：

```powershell
cd E:\Competition\meituan_ti5\v1\MT
.\flutter.ps1 run
```

---

### 4. 热重载

`flutter run` 启动后，在同一个终端里：

```text
r   热重载
R   热重启
q   退出
```

---

### 5. VS Code 直接跑

1. 打开 `E:\Competition\meituan_ti5\v1\MT`
2. 左下角选设备 `NovaTestPhone`
3. 按 `F5`

---

## 二、双城测试样例

### 广州样例

```text
周六下午两点从广州塔出发，预算 200，想约会，想喝咖啡、看展、吃饭，不想太累，晚上9点前结束
```

### 上海样例

```text
周末从外滩出发，预算 200，想拍照、喝咖啡、吃本帮菜，不想太累，晚上9点前结束
```

### 夜景样例

```text
晚上六点从外滩出发，预算200，想拍照、看夜景、吃本帮菜，不想绕远路
```

---

## 三、大模型配置

复制示例配置：

```powershell
cd E:\Competition\meituan_ti5\v1\MT\backend
Copy-Item .env.example .env
```

DashScope：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key
DASHSCOPE_MODEL=qwen-plus
LLM_TIMEOUT_SECONDS=20
```

OpenAI：

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
LLM_TIMEOUT_SECONDS=20
```

关闭大模型、强制使用规则解析：

```env
LLM_INTENT_DISABLE_LLM=1
```

---

## 四、后端检查

### 1. 检查 Python 语法

```powershell
cd E:\Competition\meituan_ti5
python -B -m py_compile .\v1\MT\backend\schemas.py .\v1\MT\backend\review_analyzer.py .\v1\MT\backend\poi_ranker.py .\v1\MT\backend\route_planner.py .\v1\MT\backend\main.py
```

### 2. 跑一条路线链路

```powershell
cd E:\Competition\meituan_ti5
python -B -c "import sys, json; sys.path.insert(0, r'E:\Competition\meituan_ti5\v1\MT\backend'); import intent_parser, poi_retriever, constraint_checker, route_planner; intent=intent_parser.parse_intent('下午两点从广州塔出发，预算200，想约会，喝咖啡、看展、吃饭，不想排队，晚上九点前结束','广州'); pois=constraint_checker.filter_by_constraints(poi_retriever.retrieve_pois(intent), intent); route=route_planner.generate_route(pois, intent); print(json.dumps({'score': route.route_score, 'ratio': route.travel_time_ratio, 'warnings': route.warnings, 'options': route.route_options}, ensure_ascii=False))"
```

---

## 五、常用检查

### 1. 检查 Flutter 环境

```powershell
cd E:\Competition\meituan_ti5\v1\MT
.\flutter.ps1 doctor
```

详细版：

```powershell
cd E:\Competition\meituan_ti5\v1\MT
cmd /c G:\dev\flutter\bin\flutter.bat doctor -v
```

### 2. 检查 Flutter 代码

```powershell
cd E:\Competition\meituan_ti5\v1\MT
cmd /c G:\dev\flutter\bin\flutter.bat analyze
```

### 3. 跑 Flutter 测试

```powershell
cd E:\Competition\meituan_ti5\v1\MT
cmd /c G:\dev\flutter\bin\flutter.bat test
```

### 4. 检查后端是否占用 8000 端口

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess
```

如果需要杀掉旧进程：

```powershell
Stop-Process -Id <PID> -Force
```

---

## 六、出问题时再用

### 1. 检查 Gradle

```powershell
cd E:\Competition\meituan_ti5\v1\MT\android
cmd /c gradlew.bat -v
```

### 2. 重装指定 NDK

```powershell
C:\Users\Charles\AppData\Local\Android\Sdk\cmdline-tools\latest\bin\sdkmanager.bat --install "ndk;28.2.13676358"
```

### 3. 直接调用系统 adb

```powershell
C:\Users\Charles\AppData\Local\Android\Sdk\platform-tools\adb.exe devices
```

### 4. 直接调用 Flutter

```powershell
G:\dev\flutter\bin\flutter.bat analyze
```

---

## 七、环境路径

Flutter SDK：

```text
G:\dev\flutter
```

Android SDK：

```text
C:\Users\Charles\AppData\Local\Android\Sdk
```

当前 NDK：

```text
C:\Users\Charles\AppData\Local\Android\Sdk\ndk\28.2.13676358
```

VS Code 项目设置：

```text
E:\Competition\meituan_ti5\v1\MT\.vscode\settings.json
```

---

## 八、为什么优先用脚本

### flutter.ps1

这个脚本已经帮你做了两件事：

1. 指向 `G:\dev\flutter\bin\flutter.bat`
2. 把 Gradle 缓存和临时目录尽量放到 `G:` 盘

所以平时优先用。注意：当前脚本仍可能指向旧的 `G:` 盘 Flutter SDK，如果本机没有 `G:` 盘，需要先修正脚本里的 Flutter 路径。

```powershell
.\flutter.ps1 ...
```

### adb.ps1

PowerShell 不一定总能直接认出系统 adb，所以优先用：

```powershell
.\adb.ps1 devices
```

---

## 九、Git 常用流程

查看改动：

```powershell
cd E:\Competition\meituan_ti5\v1\MT
git status --short
git diff --stat
```

分文件查看：

```powershell
git diff -- backend\route_planner.py backend\poi_ranker.py backend\schemas.py
git diff -- lib\models\route_models.dart lib\pages\route_result_page.dart
```

暂存本次相关文件：

```powershell
git add backend\main.py backend\llm_intent_client.py backend\review_analyzer.py backend\poi_ranker.py backend\route_planner.py backend\schemas.py backend\.env.example lib\models\route_models.dart lib\pages\route_result_page.dart README.md IMPLEMENTATION_SUMMARY.md SOLUTION_PLAN.md COMMANDS.md
```

提交：

```powershell
git commit -m "feat: enhance local smart route planning"
```

如需撤销某个误暂存文件：

```powershell
git restore --staged <file>
```


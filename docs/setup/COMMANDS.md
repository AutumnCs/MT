# Commands

下面命令都按当前仓库根目录 `G:\MeituanAgent` 编写，适用于 Windows PowerShell。

## 1. 激活环境

```powershell
cd G:\MeituanAgent
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

## 2. 启动后端

```powershell
cd G:\MeituanAgent\backend
python -m pip install -r requirements.txt
python main.py
```

等价写法：

```powershell
cd G:\MeituanAgent\backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## 3. 启动前端 Windows

先更新依赖：

```powershell
cd G:\MeituanAgent
.\flutter.ps1 pub get
```

再运行：

```powershell
cd G:\MeituanAgent
.\flutter.ps1 run -d windows
```

## 4. 开启地图面板

如果要显示路线地图面板：

```powershell
cd G:\MeituanAgent
.\flutter.ps1 run -d windows --dart-define=SHOW_ROUTE_MAP_PANEL=true
```

如果你还有天地图浏览器端 token：

```powershell
cd G:\MeituanAgent
.\flutter.ps1 run -d windows --dart-define=SHOW_ROUTE_MAP_PANEL=true --dart-define=TDT_WEB_KEY=你的Token
```

## 5. 清理 Flutter 构建缓存

如果出现旧路径的 `CMakeCache.txt`，先清理再跑：

```powershell
cd G:\MeituanAgent
Remove-Item -Recurse -Force .\build, .\.dart_tool -ErrorAction SilentlyContinue
.\flutter.ps1 pub get
```

## 6. 跑离线评测

```powershell
cd G:\MeituanAgent\backend
python -m eval.eval_runner
```

## 7. 常用调试变量

```powershell
$env:DASHSCOPE_API_KEY="你的DashScope Key"
$env:DASHSCOPE_MODEL="qwen-turbo"
$env:LLM_INTENT_FORCE="1"
$env:LLM_INTENT_FAST_GATE="0"
$env:LLM_INTENT_DISABLE_LLM="1"
$env:LLM_INTENT_TIMEOUT="6"
```

外部语义模型开关：

```powershell
$env:ROUTE_DENSE_MODEL_BACKEND="sentence_transformers"
$env:ROUTE_DENSE_MODEL="BAAI/bge-m3"
$env:ROUTE_RERANK_MODEL_BACKEND="sentence_transformers"
$env:ROUTE_RERANK_MODEL="BAAI/bge-reranker-v2-m3"
$env:ROUTE_RERANK_MAX_ITEMS="64"
```

如需安装可选依赖：

```powershell
cd G:\MeituanAgent\backend
python -m pip install sentence-transformers
python -m pip install faiss-cpu
```

## 8. 后端语法检查

```powershell
cd G:\MeituanAgent
python -m py_compile backend\main.py backend\services\route_service.py backend\core\intent_parser.py
```

# Quickstart

这是当前项目的最短启动流程。

## 1. 启动后端

```powershell
cd G:\MeituanAgent\backend
python -m pip install -r requirements.txt
python main.py
```

默认地址：

```text
http://127.0.0.1:8000
```

## 2. 启动前端

```powershell
cd G:\MeituanAgent
.\flutter.ps1 pub get
.\flutter.ps1 run -d windows
```

如果遇到旧的 `build` 路径缓存：

```powershell
cd G:\MeituanAgent
Remove-Item -Recurse -Force .\build, .\.dart_tool -ErrorAction SilentlyContinue
.\flutter.ps1 pub get
```

## 3. 可选地图配置

需要地图面板时：

```powershell
cd G:\MeituanAgent
.\flutter.ps1 run -d windows --dart-define=SHOW_ROUTE_MAP_PANEL=true
```

如需传入天地图浏览器端 token：

```powershell
cd G:\MeituanAgent
.\flutter.ps1 run -d windows --dart-define=SHOW_ROUTE_MAP_PANEL=true --dart-define=TDT_WEB_KEY=你的Token
```

## 4. 可选 LLM 配置

```powershell
$env:DASHSCOPE_API_KEY="你的DashScope Key"
$env:DASHSCOPE_MODEL="qwen-turbo"
```

如果你想强制走 LLM：

```powershell
$env:LLM_INTENT_FORCE="1"
```

## 5. 离线评测

```powershell
cd G:\MeituanAgent\backend
python -m eval.eval_runner
```

## 6. 可选外部语义模型

默认检索和精排会使用本地轻量后端。

如果你想切到真实 embedding / rerank 模型：

```powershell
cd G:\MeituanAgent\backend
python -m pip install sentence-transformers
python -m pip install faiss-cpu
$env:ROUTE_DENSE_MODEL_BACKEND="sentence_transformers"
$env:ROUTE_DENSE_MODEL="BAAI/bge-m3"
$env:ROUTE_RERANK_MODEL_BACKEND="sentence_transformers"
$env:ROUTE_RERANK_MODEL="BAAI/bge-reranker-v2-m3"
python main.py
```

如果这些依赖或模型不可用，系统会自动回退到本地轻量语义后端。

# Quickstart

这是当前项目的最短启动路径。

## 1. 安装后端依赖

```powershell
cd G:\MeituanAgent\backend
python -m pip install -r requirements.txt
```

## 2. 启动后端

```powershell
cd G:\MeituanAgent\backend
python main.py
```

默认地址：

```text
http://127.0.0.1:8000
```

## 3. 启动前端

```powershell
cd G:\MeituanAgent
flutter pub get
.\flutter.ps1 run -d windows
```

## 4. 可选地图配置

后端天地图 key：

```powershell
$env:TDT_SERVER_KEY="你的天地图服务端Key"
```

前端 WebView token：

```powershell
.\flutter.ps1 run -d windows --dart-define=TDT_WEB_KEY=你的天地图浏览器端Token
```

不配置地图 key 时，系统使用本地地图预览兜底。

## 5. 跑离线评测

```powershell
cd G:\MeituanAgent\backend
python -m eval.eval_runner
```

## 6. 常见问题入口

- 意图解析：`backend/core/intent_parser.py`
- POI 召回：`backend/services/poi_retriever.py`
- POI 排序：`backend/services/ranker_engine.py`
- 路线规划：`backend/services/route_planner.py`
- 响应解释：`backend/services/response_generator.py`
- 地图预览：`backend/services/map_service.py`
- 前端首页：`lib/main.dart`
- 结果页：`lib/pages/route_result_page.dart`


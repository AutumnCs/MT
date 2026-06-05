# Quickstart

这是最短启动路径。

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

## 3. 启动前端

```powershell
cd G:\MeituanAgent
.\flutter.ps1 run -d windows
```

## 4. 跑离线回归

```powershell
cd G:\MeituanAgent\backend
python -m eval.check_quality
```

## 5. 常见问题先看哪里

- 口语识别：`backend/core/intent_parser.py`
- 同义归一：`backend/core/intent_lexicon.py`
- 路由分流：`backend/core/capability_registry.py`
- 路线生成：`backend/services/route_planner.py`
- 地图联动：`backend/services/map_service.py`


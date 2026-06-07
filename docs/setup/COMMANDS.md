# Commands

## 安装后端依赖

```powershell
cd G:\MeituanAgent\backend
python -m pip install -r requirements.txt
```

## 启动后端

```powershell
cd G:\MeituanAgent\backend
python main.py
```

## 启动前端

```powershell
cd G:\MeituanAgent
flutter pub get
.\flutter.ps1 run -d windows
```

## 启动前端并传入天地图 Web Token

```powershell
cd G:\MeituanAgent
.\flutter.ps1 run -d windows --dart-define=TDT_WEB_KEY=你的天地图浏览器端Token
```

## 运行离线评测

```powershell
cd G:\MeituanAgent\backend
python -m eval.eval_runner
```

## 观察回归

```powershell
cd G:\MeituanAgent\backend
python -m eval.watch_quality
```

## 后端语法检查

```powershell
cd G:\MeituanAgent
python -m py_compile backend\main.py
```

## Flutter 测试

```powershell
cd G:\MeituanAgent
flutter test
```

注意：如果测试仍查找旧 UI 文案，需要先更新 `test/widget_test.dart` 与当前首页文案一致。

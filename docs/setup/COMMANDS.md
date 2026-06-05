# Commands

## 安装依赖

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
.\flutter.ps1 run -d windows
```

## 运行回归

```powershell
cd G:\MeituanAgent\backend
python -m eval.check_quality
```

## 观察回归

```powershell
cd G:\MeituanAgent\backend
python -m eval.watch_quality
```

## 常用检查

```powershell
flutter analyze
python -m py_compile backend\\main.py
```


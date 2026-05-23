# MeituanAgent 常用指令

这份文档只放两类内容：
1. 日常开发真正高频会用到的命令
2. 出问题时再查的排障命令

默认项目根目录：

```powershell
cd G:\MeituanAgent
```

## 日常开发

### 1. 启动后端

首次安装依赖：

```powershell
cd G:\MeituanAgent\backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

平时启动后端：

```powershell
cd G:\MeituanAgent\backend
..\.venv\Scripts\python.exe main.py
```

后端地址：

```text
http://127.0.0.1:8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

---

### 2. 查看模拟器 / 设备

优先用项目里的脚本：

```powershell
cd G:\MeituanAgent
.\adb.ps1 devices
.\flutter.ps1 devices
```

---

### 3. 运行 Flutter 到模拟器

指定当前常用模拟器：

```powershell
cd G:\MeituanAgent
.\flutter.ps1 run -d emulator-5554
```

不指定设备：

```powershell
cd G:\MeituanAgent
.\flutter.ps1 run
```

---

### 4. 热更新

`flutter run` 跑起来后，在同一个终端里：

```text
r   热重载
R   热重启
q   退出运行
```

---

### 5. VS Code 里直接跑

1. 打开 `G:\MeituanAgent`
2. 左下角选择设备 `NovaTestPhone`
3. 按 `F5`

---

## 真正常用顺序

每天最常见的完整流程就是这几步：

先开后端：

```powershell
cd G:\MeituanAgent\backend
..\.venv\Scripts\python.exe main.py
```

新开一个终端跑前端：

```powershell
cd G:\MeituanAgent
.\adb.ps1 devices
.\flutter.ps1 devices
.\flutter.ps1 run -d emulator-5554
```

---

## 双城联调测试样例

### 广州样例

```text
周六下午两点从广州塔出发，预算 200，想约会，想喝咖啡、看展、吃饭，不想太累，晚上9点前结束
```

### 上海样例

```text
周末从外滩出发，预算 200，想拍照、喝咖啡、吃本帮菜，不想太累，晚上9点前结束
```

---

## 常用检查

### 1. 检查 Flutter 环境

```powershell
cd G:\MeituanAgent
.\flutter.ps1 doctor
```

详细版：

```powershell
cd G:\MeituanAgent
cmd /c G:\dev\flutter\bin\flutter.bat doctor -v
```

### 2. 检查 Flutter 代码

```powershell
cd G:\MeituanAgent
cmd /c G:\dev\flutter\bin\flutter.bat analyze
```

### 3. 跑 Flutter 测试

```powershell
cd G:\MeituanAgent
cmd /c G:\dev\flutter\bin\flutter.bat test
```

### 4. 检查后端是否占用 8000 端口

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess
```

如果要杀掉旧进程：

```powershell
Stop-Process -Id <PID> -Force
```

---

## 出问题时再用

### 1. 检查 Gradle

```powershell
cd G:\MeituanAgent\android
cmd /c gradlew.bat -v
```

### 2. 重新安装指定 NDK

```powershell
C:\Users\Charles\AppData\Local\Android\Sdk\cmdline-tools\latest\bin\sdkmanager.bat --install "ndk;28.2.13676358"
```

### 3. 直接用系统 adb

```powershell
C:\Users\Charles\AppData\Local\Android\Sdk\platform-tools\adb.exe devices
```

### 4. 直接跑 flutter analyze

```powershell
G:\dev\flutter\bin\flutter.bat analyze
```

---

## 环境路径

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
G:\MeituanAgent\.vscode\settings.json
```

---

## 补充说明

### 1. 为什么优先用 `flutter.ps1`

因为这个脚本已经帮你做了两件事：

1. 调用 `G:\dev\flutter\bin\flutter.bat`
2. 把 `Gradle` 缓存和临时目录放到 `G:`，避免继续把 `C:` 盘写满

所以平时优先用：

```powershell
.\flutter.ps1 ...
```

### 2. 为什么优先用 `adb.ps1`

因为当前 PowerShell 不一定总能直接认出系统 `adb`，脚本更稳：

```powershell
.\adb.ps1 devices
```

### 3. legacy 在哪

旧的 React / uni-app / HBuilderX 尝试已经归档到：

```text
G:\MeituanAgent\legacy
```

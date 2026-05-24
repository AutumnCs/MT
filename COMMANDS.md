# MeituanAgent 常用命令

这份文档只放两类内容：

1. 日常高频会用到的命令
2. 出问题时再查的排障命令

项目根目录：

```powershell
cd G:\MeituanAgent
```

---

## 一、日常开发

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

接口地址：

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

---

### 2. 查看设备

优先使用项目里封装好的脚本：

```powershell
cd G:\MeituanAgent
.\adb.ps1 devices
.\flutter.ps1 devices
```

---

### 3. 运行 Flutter 到模拟器

常用模拟器：

```powershell
cd G:\MeituanAgent
.\flutter.ps1 run -d emulator-5554
```

如果只想看当前可用设备：

```powershell
cd G:\MeituanAgent
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

1. 打开 `G:\MeituanAgent`
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

---

## 三、常用检查

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

如果需要杀掉旧进程：

```powershell
Stop-Process -Id <PID> -Force
```

---

## 四、出问题时再用

### 1. 检查 Gradle

```powershell
cd G:\MeituanAgent\android
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

## 五、环境路径

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

## 六、为什么优先用脚本

### flutter.ps1

这个脚本已经帮你做了两件事：

1. 指向 `G:\dev\flutter\bin\flutter.bat`
2. 把 Gradle 缓存和临时目录尽量放到 `G:` 盘

所以平时优先用：

```powershell
.\flutter.ps1 ...
```

### adb.ps1

PowerShell 不一定总能直接认出系统 adb，所以优先用：

```powershell
.\adb.ps1 devices
```

---

## 七、legacy 位置

旧的 React / uni-app / HBuilderX 尝试都已经归档到：

```text
G:\MeituanAgent\legacy
```


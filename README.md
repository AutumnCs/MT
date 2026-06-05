# MeituanAgent

这是一个“路线规划 + 多轮修改 + 轻量澄清 + 地图联动”的原型项目。

## 当前主链路

- 用户用自然语言说需求。
- LLM 先把需求整理成结构化意图。
- 后端根据意图筛选 POI、打分、规划路线。
- 需求太模糊时，系统先做一次轻量澄清。
- 用户可以继续修改路线。
- 地图服务负责真实地理信息和路径预览。

## 推荐阅读顺序

1. `docs/README.md`
2. `backend/README.md`
3. `backend/BACKEND_GUIDE.md`
4. `docs/specs/README.md`
5. `docs/specs/CONTEXT_SPEC.md`
6. `docs/specs/MULTI_TURN_SPEC.md`
7. `docs/specs/MEMORY_SPEC.md`
8. `docs/specs/MEMORY_CODE_TASKS.md`

## 运行方式

先安装后端依赖：

```powershell
cd G:\MeituanAgent\backend
python -m pip install -r requirements.txt
```

启动后端：

```powershell
cd G:\MeituanAgent\backend
python main.py
```

启动前端：

```powershell
cd G:\MeituanAgent
.\flutter.ps1 run -d windows
```

离线回归：

```powershell
cd G:\MeituanAgent\backend
python -m eval.check_quality
```


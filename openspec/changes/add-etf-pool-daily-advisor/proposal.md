# Change: 新增 ETF 池每日自动分析与风格参数建议

## Why

用户需要持续跟踪一组国内 ETF 的网格交易机会：目前只能逐个手动分析，且风格参数（低频/均衡/高频、调节系数）全靠人工判断，缺少数据支撑的调整依据。需要一个 ETF 池 + 每日批量分析 + 风格参数自动建议的监控能力。

## What Changes

- 新增 **ETF 池管理**：添加/删除/查询关注的 ETF（SQLite 持久化）
- 新增 **每日批量分析**（定时 + 手动触发）：对池中每只 ETF 执行 ATR 分析 + 风格参数评估
- 新增 **风格参数建议引擎**：规则初筛（ADX/ATR 趋势/波动率 → 候选风格与观望信号）+ 回测验证（候选风格用最近 35 天 5 分钟数据回测对比），输出推荐风格、调节系数建议及理由
- 新增 **日线 SQLite 入库**（懒增量更新），作为每日任务的数据底座，降低对免费接口的依赖
- 新增 **报告查询 API** 与 **前端 ETF 池页面**（池管理 + 每日建议 + 历史）
- 前端 **AppHeader 增加全局导航栏**（首页 / 策略分析 / ETF 池），当前路由高亮，响应式适配
- 新增独立调度进程，规避 Gunicorn 多 worker 下定时任务重复执行

## Impact

- Affected specs: `backend-api`（新增池/报告端点）、`data-models`（新增池/报告/日线表）、`frontend-routing`（新增 /pool 路由）、`etf-pool`（新 capability）
- Affected code:
  - 新增（全部为独立新模块，不侵入既有逻辑）: `backend/app/utils/db.py`、`backend/app/repositories/kline_repository.py`、`backend/app/repositories/pool_repository.py`、`backend/app/services/pool_service.py`、`backend/app/services/style_advisor.py`、`backend/app/services/pool_runner.py`、`backend/app/scheduler.py`、前端 `src/pages/PoolPage/`、`src/features/pool/`、`src/shared/services/poolApi.js`
  - 修改（仅挂钩点，各一处）: `backend/app/routes/__init__.py`（注册新 blueprint）、`backend/app/services/data_service.py`（`get_daily_data` 入口接 kline_store 单点集成）、`deploy/entrypoint.sh`（追加启动 scheduler）、`docker-compose.yml`（挂载 ./data）、`frontend/src/app/AppHeader.jsx`（导航栏）、`frontend/src/app/AppRouter.jsx`（注册 /pool 路由）
  - 新依赖: 无（SQLite 使用 Python 标准库 sqlite3，调度用标准库实现）

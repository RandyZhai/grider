## 1. SQLite 基础设施

- [ ] 1.1 新增 `backend/app/utils/db.py`：连接管理（WAL、busy_timeout=5000）、建表（etf_pool / pool_runs / daily_reports / kline_daily，`CREATE TABLE IF NOT EXISTS`）、短事务助手
- [ ] 1.2 新增 `backend/app/repositories/pool_repository.py` 与 `kline_repository.py`（业务层不手写 SQL）
- [ ] 1.3 `docker-compose.yml` 挂载 `./data:/app/backend/data`，库文件路径 `data/grider.db`

## 2. 日线数据本地化（单点集成，可回退）

- [ ] 2.1 `kline_repository.ensure_range`：缺口检测 → 仅补拉缺失区间 → 写库
- [ ] 2.2 `data_service.get_daily_data` 入口接入（约 3 行，库覆盖完整直接返回，否则走原链路）

## 3. ETF 池 API

- [ ] 3.1 新增 `backend/app/routes/pool_routes.py`（Blueprint）+ `services/pool_service.py`：GET / POST / DELETE `/api/pool`（复用 validation 校验 + 搜索接口补全名称/交易所、重复校验）
- [ ] 3.2 `routes/__init__.py` 注册新 blueprint（一行）

## 4. 风格建议引擎（独立可测试，只读复用现有算法）

- [ ] 4.1 新增 `backend/app/services/style_advisor.py`：规则初筛（ADX/atr_trend/atr_volatility → 候选风格 + 观望信号）
- [ ] 4.2 回测验证：候选前 2 风格 × 最近 35 天 5 分钟回测（调用 BacktestService 自定义参数链路，不修改其内部）
- [ ] 4.3 综合评分（0.6 回测绩效 + 0.4 规则契合）、调节系数 [0.8, 1.2] 计算、reasons 生成

## 5. 批量运行与调度（状态机 + 守护）

- [ ] 5.1 新增 `backend/app/services/pool_runner.py`：逐标的执行（间隔 ≥0.5s）、单只失败不阻断、结果写 daily_reports、run 状态流转 pending→running→done/failed、running 超 30 分钟重置
- [ ] 5.2 POST `/api/pool/run`：写入 pending 请求（当日已有报告时按状态表去重）；GET `/api/pool/runs/current` 运行进度查询
- [ ] 5.3 新增 `backend/app/scheduler.py` 独立进程：交易日 16:30 自动触发 + 每 10s 轮询 pending 手动请求 + SIGTERM 优雅退出 + 全程幂等
- [ ] 5.4 `deploy/entrypoint.sh` 以守护循环启动 scheduler（崩溃自动拉起）

## 6. 报告 API

- [ ] 6.1 GET `/api/pool/report/latest` 与 `/api/pool/report/history?ticker=`

## 7. 前端

- [ ] 7.1 `AppHeader` 导航栏改造：导航项常量 `shared/constants/nav.js`（首页/策略分析/ETF 池）、NavLink 高亮、移动端收纳、GitHub 链接保留
- [ ] 7.2 `AppRouter` 注册 `/pool` 路由 + `pages/PoolPage/` 页面壳（Tab：池管理 / 每日建议）
- [ ] 7.3 `shared/services/poolApi.js`：池 CRUD、触发运行、进度查询、报告查询（与既有 api.js 同风格错误处理）
- [ ] 7.4 `features/pool/components/PoolManager.jsx`：列表/搜索添加/删除确认
- [ ] 7.5 `features/pool/components/DailyReportList.jsx`：风格徽章、action 标签、评分、理由、回测指标摘要、跳转分析链接、立即运行 + 进度轮询（运行中显示 n/total）
- [ ] 7.6 `features/pool/components/ReportHistory.jsx`：按标的查看历次推荐与评分变化

## 8. 验证

- [ ] 8.1 本地全流程验证：添加 2-3 只 ETF → 手动运行 → 报告生成与展示、单只失败隔离、导航高亮
- [ ] 8.2 Docker 重建验证：挂载持久化、scheduler 守护进程、定时/手动触发、历史报告跨重启保留、回退路径演练（移除集成点后原功能不受影响）

# Design: ETF 池每日自动分析与风格参数建议

## Context

- 现有数据链路：AKShare 新浪免费源（日线全历史 / 5 分钟约 40 个交易日）+ 文件缓存（`cache/akshare`）
- 现有风格参数机制（[optimizer.py](file:///d:/github/grider/backend/app/algorithms/grid/optimizer.py)）：
  - `risk_preference`（低频/均衡/高频）→ ATR 步长系数 1.2 / 0.7 / 0.3
  - `adjustment_coefficient` 调节系数放大/缩小风格间差异
  - 底仓比例随风格 + ADX + 波动率联动
- 部署形态：Docker 单容器，Gunicorn 4 worker，缓存挂载宿主机 `./cache`
- 前端：React + react-router-dom + Tailwind，分层为 `app/`（壳）、`pages/`（页面）、`features/`（业务模块）、`shared/`（通用）；AppHeader 当前无应用内导航
- 后端：Flask Blueprint 按域注册（`routes/__init__.py`），服务层 + 算法层 + 外部数据层分离

## Goals / Non-Goals

- Goals: 池管理、每日自动批量分析、数据驱动的风格参数建议、结果可视化、全局导航栏
- Non-Goals: 自动下单/实盘对接、多用户/权限体系、分钟线入库、全市场扫描（仅池内标的）

## 架构原则：模块化与零侵入

### D0: 分层与模块边界（可插拔，前后演进互不影响）

```
后端新增模块（纵向自洽，横向只依赖稳定接口）
routes/pool_routes.py          # Blueprint，仅做参数校验与响应包装
  └─ services/pool_service.py     # 池 CRUD + 报告查询
  └─ services/pool_runner.py      # 批量运行编排（状态机）
       ├─ services/style_advisor.py   # 风格建议引擎（独立可测试）
       │    └─ 复用 algorithms/*（只读调用，不修改）
       │    └─ 复用 services/backtest_service.py（只读调用，不修改）
       └─ repositories/               # 持久化层（sqlite3 封装）
            ├─ pool_repository.py
            └─ kline_repository.py
utils/db.py                    # 连接/建表/事务助手（全局唯一 SQLite 入口）
scheduler.py                   # 独立进程：定时 + 手动请求轮询（不 import Flask app 主逻辑之外的东西）
```

- **零侵入既有代码**：`etf_analysis_service`、`backtest_service`、`algorithms/*` 一行不改；`data_service.get_daily_data` 仅在函数入口加一个单点集成（先查 kline_repository，命中即返回）——日线库下线时删除该 3 行即可完全还原
- **新 capability 独立成域**：池功能有自己的 routes/services/repositories 命名空间，后续若加"股票池""扫描器"按同构模式平行扩展，互不影响
- **前端同构**：新增 `features/pool/` 业务模块（组件 + api 封装自包含）+ `pages/PoolPage/` 页面壳；`shared/` 只新增 `poolApi.js`，既有 shared 模块不改

### D0b: 健壮性设计

1. **错误隔离**：批量运行逐标的 try/except，单只失败写入报告 `status=failed + error`，不阻断其余标的；运行结束输出成功/失败统计
2. **运行状态机**：`pending → running → done / failed`；running 超过 30 分钟由 scheduler 判定为僵死并重置为 failed（进程崩溃后可重跑，不留永久锁）
3. **SQLite 并发安全**：WAL 模式 + `busy_timeout=5000ms` + 全部写操作短事务（repo 层统一封装，业务层不手写 SQL）
4. **调度进程守护**：entrypoint 以 `while true; do python -m app.scheduler; sleep 5; done` 子进程方式启动，崩溃自动拉起；scheduler 全部逻辑幂等（当日已 done 则跳过）
5. **输入校验**：池添加复用 `utils/validation.py` 的代码格式校验 + 调用现有搜索接口验证标的存在性
6. **外部接口降级**：日线读取顺序 SQLite > 文件缓存 > 新浪接口；全部失败时该标的标记失败并在报告中注明数据截止日，不影响其他标的
7. **优雅关闭**：scheduler 捕获 SIGTERM 完成当前标的后退出，避免报告写一半

## Decisions

### D1: 存储 —— SQLite 单文件（`data/grider.db`，挂载 `./data`）

- 表：
  - `etf_pool(id, ticker, exchange_code, name, type, note, active, created_at)`，ticker 唯一
  - `pool_runs(id, run_date, trigger, status, total, done, failed, started_at, finished_at)`，run_date 唯一约束当日单次
  - `daily_reports(id, run_id, ticker, status, current_style, recommended_style, recommended_adjustment, action(维持/调整/观望), score, reasons_json, atr_metrics_json, backtest_metrics_json, error, created_at)`
  - `kline_daily(ticker, exchange_code, date, open, high, low, close, volume, amount, fetched_at)`，主键 `(ticker, date)`
- 备选 JSON 文件：被否——每日报告需按日期/标的查询与趋势对比，且日线入库已是共识方向

### D2: 调度 —— 独立进程，规避 Gunicorn 多 worker 重复执行

- `deploy/entrypoint.sh` 以守护循环启动 `python -m app.scheduler` + Gunicorn
- scheduler 职责：
  1. 每个交易日 16:30（`tool_trade_date_hist_sina` 日历判断）自动触发当日运行
  2. 每 10 秒轮询 `pool_runs` 中的 `pending` 手动请求并执行
- API 触发只写入一条 `pending` 记录，由 scheduler 执行 → 单实例写入，无锁竞争
- 备选 APScheduler 每 worker 内嵌：被否——4 worker 重复执行需额外选主逻辑

### D3: 风格建议 —— 规则初筛 + 回测验证（混合）

1. **规则初筛**（`style_advisor.py`）：
   - ADX < 20 且 atr_trend 平缓 → 候选 [高频, 均衡]
   - ADX 20-40 → 候选 [均衡, 低频]
   - ADX > 40 或 atr_trend 强单边 → 候选 [低频]，若价格贴近区间边界叠加 `action=观望`
   - 波动率收缩（atr_volatility 下降）上调高频优先级；扩张上调低频优先级
2. **回测验证**：候选前 2 个风格，用最近 35 天 5 分钟数据（复用 `BacktestService` 自定义参数链路）各回测一次
3. **综合评分** = 0.6 × 回测绩效归一化（夏普/收益/回撤）+ 0.4 × 规则契合度 → 推荐风格
4. **调节系数**：按回测收益稳定性在 [0.8, 1.2] 内取值（稳定 → >1 放大步长差异；反复 → <1 收敛均衡）
5. 输出 `reasons`：规则理由 + 回测指标证据，供前端展示

### D4: 日线入库 —— 懒增量更新，单点集成

- `kline_repository` 提供 `ensure_range(ticker, start, end)`：检测库内缺口 → 仅补拉缺失区间 → 写库
- `data_service.get_daily_data` 入口单点调用（约 3 行）：库内覆盖完整则直接返回；否则走原链路（文件缓存/接口），非侵入可回退
- 存不复权原始价（避免前复权基准漂移失真）

### D5: 前端 —— 导航栏 + `/pool` 页面

- **导航栏（AppHeader 改造，唯一壳层改动）**：
  - 增加应用内导航：首页 `/`、策略分析 `/analysis`（引导到选择页）、ETF 池 `/pool`
  - `NavLink` 当前路由高亮；移动端收纳为汉堡菜单（Tailwind 响应式，复用现有断点风格）；GitHub 版本链接保留右移
- **PoolPage（`pages/PoolPage/`）**：页面壳 + Tab 切换（池管理 / 每日建议）
- **features/pool 模块（自包含）**：
  - `components/PoolManager.jsx`：列表 + 搜索添加（复用现有代码搜索接口）+ 删除确认
  - `components/DailyReportList.jsx`：推荐风格徽章、action 标签、评分、理由、回测指标摘要、跳转 `/analysis/:ticker` 链接、"立即运行"按钮 + 运行进度轮询（复用 `usePersistedState` 模式）
  - `components/ReportHistory.jsx`：按标的查看历次推荐变化
  - `services` 封装于 `shared/services/poolApi.js`（与既有 `api.js` 同风格，统一错误处理）

## Risks / Trade-offs

- 新浪分钟源仅 40 个交易日 → 回测窗口固定 35 天（高于 30 天下限），建议结论标注窗口范围
- 批量运行接口频率 → 每只 ETF 间隔 ≥0.5s，日线库命中后实际外部请求集中在增量部分
- 调度进程与 API 进程并发写 SQLite → WAL + busy_timeout + 短事务（D0b-3）
- 50 只标的运行约 60-90 秒 → 异步执行（pending → running → done），前端轮询报告状态
- AppHeader 改动是唯一触碰既有前端的部分 → 导航项抽取为常量数组（`shared/constants/nav.js`），后续新增页面只加一行配置

## Migration Plan

- 全部为新增表/新增端点/新增模块，无既有数据迁移；`docker compose up -d --build` 后自动建表（启动时 `CREATE TABLE IF NOT EXISTS`）
- 回滚：删除新代码、移除 entrypoint 中 scheduler 启动行与 data_service 集成点、删除新挂载目录即可，既有功能不受影响

## Open Questions

- 无

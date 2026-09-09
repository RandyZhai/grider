## Design: ETF 池每日模块化分析、多算法建议与持仓感知

### 1. Context
现有系统具备 ETF 数据获取、ATR/ADX 分析、网格参数优化和回测能力，部署为 Docker + Flask/Gunicorn + React。新增方案不得把每日运行写成只能由 scheduler 调用的封闭流程，因为历史模拟、手工单标的分析和未来 Paper Trading 都需要复用相同的数据、算法、回测和风险约束模块。

### 2. 核心设计原则
1. **分析与编排分离**：scheduler/API 只负责创建和领取任务，业务能力由可直接调用的 AnalysisPipeline 提供。
2. **算法、过滤器、资金管理分离**：避免为每种组合复制算法类。
3. **市场判断与账户行动分离**：先客观评价策略，再结合持仓形成可执行建议。
4. **回测与模拟共用执行语义**：统一订单、成交、费用、持仓和网格状态模型。
5. **配置与快照分离**：模板可变，历史运行必须保留算法版本、参数及数据窗口快照。
6. **数据质量显式化**：禁止在分钟数据不足时静默生成高置信度建议。
7. **模块可插拔**：增加算法不修改运行器、报告 API 和主调度逻辑。

### 3. 模块边界
```text
routes/
  pool_routes.py
  strategy_routes.py
  portfolio_routes.py
  analysis_routes.py
  report_routes.py

services/
  pool_service.py
  strategy_service.py
  portfolio_service.py
  analysis_pipeline.py
  recommendation_service.py
  run_service.py
  report_service.py

algorithms/grid/
  base.py
  registry.py
  adapters/
  fixed_arithmetic.py
  fixed_geometric.py
  atr_adaptive.py
  bollinger_adaptive.py

algorithms/filters/
  base.py
  adx_filter.py
  ma_direction_filter.py
  volatility_filter.py
  breakout_filter.py

algorithms/capital/
  base.py
  equal_amount.py
  position_limit.py

simulation/
  engine.py
  order_model.py
  fill_model.py
  fee_model.py
  portfolio_ledger.py
  grid_state.py

market_data/
  daily_provider.py
  minute_provider.py
  trade_calendar.py
  quality.py

repositories/
  pool_repository.py
  strategy_repository.py
  run_repository.py
  report_repository.py
  kline_repository.py
  portfolio_repository.py
  simulation_repository.py

scheduler.py
```

### 4. 可复用 AnalysisPipeline
AnalysisPipeline 不依赖 Flask request、Blueprint 或 scheduler，可由任何调用方传入 AnalysisRequest。

```python
@dataclass
class AnalysisRequest:
    instruments: list[str]
    strategy_profile_ids: list[int] | None
    mode: str                 # fixed | compare | auto
    as_of: datetime
    data_policy: dict
    execution_assumptions: dict
    account_id: int | None
    persist: bool = True

@dataclass
class AnalysisResult:
    market_evaluations: list
    portfolio_advice: list
    data_quality: dict
    warnings: list[str]
    lineage: dict
```

流水线步骤：
1. 标准化 instrument_id。
2. 根据算法 required_data 聚合日线/5分钟数据需求。
3. 从本地库/缓存读取并补齐缺口，执行数据质量校验。
4. 计算可共享特征，避免每个算法重复计算 ATR/ADX/均线。
5. 根据 ETF 绑定和运行模式生成候选策略。
6. 使用统一 SimulationEngine 在相同条件下评估候选。
7. 使用固定、版本化评分函数计算 strategy score。
8. 通过 RecommendationService 应用显著性阈值和切换滞回。
9. 若提供 account_id，读取现金、持仓和活动网格，通过 PortfolioConstraintEngine 生成账户层建议。
10. 按需持久化评估、最终报告及数据血缘。

调用方：
- scheduler：每日池全部标的。
- API：单标的或指定策略即时分析。
- 历史模拟：传入历史 as_of 和数据窗口。
- Paper Trading：复用算法、过滤器、资金管理和 SimulationEngine，不直接调用每日 scheduler。

### 5. 算法插件接口
```python
class GridAlgorithm(Protocol):
    key: str
    version: str
    def parameter_schema(self) -> dict: ...
    def validate_parameters(self, params: dict) -> dict: ...
    def required_data(self, params: dict) -> dict: ...
    def initialize(self, context, params) -> dict: ...
    def on_bar(self, state, bar, context) -> list: ...
    def explain(self, evaluation) -> list[str]: ...
```

算法注册表仅管理可用算法和版本。算法不得直接访问数据库、HTTP 或 Flask；数据和执行上下文由调用方注入。

首批算法：
- fixed_arithmetic
- fixed_geometric
- atr_adaptive
- bollinger_adaptive

过滤器和资金管理器使用独立接口，在算法信号进入执行引擎前组合应用。

### 6. 前台配置模型
- 策略模板包含：algorithm_key/version、parameters、filters、capital_config、risk_config。
- ETF 绑定支持 role=primary/candidate/benchmark、priority、enabled。
- 运行模式：
  - fixed：仅评价主策略；
  - compare：比较所有启用绑定，不自动改变当前策略；
  - auto：规则缩小候选后统一评价，仍只输出建议。
- 参数表单由后端 schema 动态渲染；复杂算法可选专用前端组件。
- 用户修改模板不改变历史结果，运行时保存完整快照。

### 7. 持仓感知
账户层至少包含：
- paper_accounts / manual_accounts：现金和状态；
- positions：数量、可用数量、平均成本、已实现盈亏；
- strategy_instances：当前实际采用的策略快照和状态；
- grid_state：锚点、边界、当前格、下一买卖价、预留资金/份额。

每日结果分两层：
- market_recommendation：不考虑用户持仓的算法评价；
- portfolio_advice：结合现金、成本、仓位上限、活动网格后给出的维持/调整/暂停买入/只卖不买/补底仓/启动/观望/数据不足。

持仓来源：manual、paper、future_broker。第一阶段支持人工录入和模拟账户，不接券商。

### 8. 统一 SimulationEngine
历史回测和未来 Paper Trading 共用：
- Order、Trade、Position、CashLedger、GridState；
- 手续费、滑点、最小交易单位；
- 限价单触达和同 bar 多事件规则；
- 仓位、现金及风险限制。

每日16:30任务只负责收盘分析、建议和账户快照。未来5分钟向前模拟应由独立 market-data runner 驱动，不能依赖每日任务完成盘中撮合。

### 9. 数据闭环
- 日线：SQLite `kline_daily`，读取顺序 SQLite -> 文件缓存 -> 外部源，后两者命中后回写 SQLite。
- 5分钟：按 `instrument_id/trade_date` 保存 Parquet；记录 source、fetched_at、bar_count、checksum、quality。
- 缺口根据交易日历和算法 required_data 判断，不使用自然日。
- 分钟数据不足时：对应策略 evaluation.status=insufficient；若所有候选不足，最终 action=data_insufficient/观望，不给确定性切换建议。
- 容器时区显式使用 Asia/Shanghai；数据库时间戳统一存 UTC。

### 10. 数据模型
核心新增表：
- algorithm_catalog(key, version, name, enabled, parameter_schema_json)
- strategy_profiles(id, name, algorithm_key, algorithm_version, parameters_json, filters_json, capital_json, risk_json, version, active)
- pool_strategy_bindings(pool_id, strategy_profile_id, role, priority, enabled)
- analysis_runs(id, run_date, attempt, trigger, mode, status, heartbeat_at, lease_expires_at, worker_id, totals..., timestamps)
- strategy_evaluations(run_id, instrument_id, profile_id, algorithm_key/version, status, score, metrics_json, parameter_snapshot_json, data_window_json, data_quality, reasons_json)
- daily_reports(run_id, instrument_id, current_strategy_id, recommended_strategy_id, market_action, portfolio_action, confidence, reasons_json, lineage_json)
- accounts(id, name, type, initial_cash, available_cash, status)
- positions(account_id, instrument_id, quantity, available_quantity, average_cost, realized_pnl, source)
- strategy_instances(id, account_id, instrument_id, profile_id, parameter_snapshot_json, status, timestamps)
- grid_states(strategy_instance_id, common fields..., state_json)
- paper_orders / paper_trades / account_snapshots（为模拟模块预留并逐阶段实现）

关键约束：
- `UNIQUE(run_date, attempt)`，不得只对 run_date 唯一。
- `UNIQUE(run_id, instrument_id, strategy_profile_id)`。
- 任务级状态：pending/running/done/partial/failed/cancelled/stale。
- ETF 删除为软删除，保留历史。
- 内部统一 `instrument_id=510300.SH` 格式。

### 11. 调度与并发
Docker Compose 拆分 web 和 scheduler 两个 service，共用镜像及数据卷。
- API 只创建 pending。
- scheduler 使用短事务原子 claim；rowcount=1 才开始执行。
- 每完成一个标的更新 heartbeat。
- lease 超时而非 started_at 超时才标记 stale。
- 失败重跑创建 attempt+1；可仅重跑失败标的。
- SIGTERM 后停止领取新标的，完成当前原子步骤后退出。

### 12. 评分与切换
评分函数必须版本化并采用固定边界，不在两个候选之间简单 min-max。所有策略使用相同数据窗口、初始资金、费用、滑点、最小单位和网格初始化规则。

推荐切换需同时满足：
- 数据质量达标；
- 新策略评分优势超过配置阈值；
- 至少满足配置的连续确认次数或稳定窗口要求；
- 账户约束允许执行。

否则 market_action 或 portfolio_action 为“维持”。

### 13. API
- GET /api/algorithms
- GET /api/algorithms/{key}/schema
- CRUD /api/strategies
- CRUD /api/pool
- PUT /api/pool/{id}/strategies
- CRUD /api/accounts/{id}/positions
- POST /api/analysis/runs
- GET /api/analysis/runs/{id}
- GET /api/reports/latest
- GET /api/reports/history
- POST /api/simulations/backtest（阶段二）

### 14. 前端
- 全局导航：首页、策略分析、ETF池、策略中心、持仓/模拟。
- ETF池：绑定主策略/候选/基准及运行模式。
- 策略中心：动态参数表单、过滤器、资金和风险配置。
- 持仓：人工录入现金、数量、成本，查看活动网格。
- 每日报告：分栏展示市场推荐和账户行动，显示数据窗口、质量、算法版本和参数快照。

### 15. 迁移与回滚
新增 schema_version 和显式 migration，不依赖仅 `CREATE TABLE IF NOT EXISTS` 完成未来升级。新能力通过 feature flags 控制。既有分析入口继续可用，逐步适配到 AnalysisPipeline；关闭新功能时不影响原分析页面。

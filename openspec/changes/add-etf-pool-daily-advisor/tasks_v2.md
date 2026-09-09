## Tasks: ETF 每日模块化分析、多算法与持仓感知

### 0. 技术验证门槛
- [ ] 0.1 在目标 Docker 环境验证日线和5分钟数据获取，记录可用区间、失败类型和限频行为。
- [ ] 0.2 验证35个交易日5分钟数据的本地持久化与离线读取。
- [ ] 0.3 审计现有 optimizer.py 中 adjustment_coefficient 的真实公式和单调性。
- [ ] 0.4 测量各算法单ETF一次回放的耗时和内存。
- [ ] 0.5 明确统一手续费、滑点、最小交易单位、同bar成交顺序和跳空规则。

### 1. 数据与数据库基础设施
- [ ] 1.1 新增 schema_version 和 migration runner。
- [ ] 1.2 db.py 统一 WAL、busy_timeout、foreign_keys、synchronous 和短事务。
- [ ] 1.3 建立标准 instrument_id 转换及测试。
- [ ] 1.4 建表：pool、algorithm_catalog、strategy_profiles、bindings、analysis_runs、strategy_evaluations、daily_reports、accounts、positions、strategy_instances、grid_states。
- [ ] 1.5 增加必要唯一约束、CHECK 和索引。
- [ ] 1.6 ETF 删除采用软删除并支持恢复。

### 2. 市场数据层
- [ ] 2.1 DailyDataProvider：SQLite -> 文件缓存 -> 外部源，成功后统一回写。
- [ ] 2.2 MinuteDataProvider：按 instrument/date 保存 Parquet，支持增量、质量元数据和离线读取。
- [ ] 2.3 TradeCalendarProvider：本地缓存，按交易日判断缺口。
- [ ] 2.4 数据质量校验：重复、缺bar、非交易时间、OHLC异常、未来时间、未收盘数据。
- [ ] 2.5 required_data 聚合器：按候选算法一次准备共享数据。

### 3. 算法插件体系
- [ ] 3.1 定义 GridAlgorithm、SignalFilter、CapitalManager 接口。
- [ ] 3.2 实现 registry 和算法元数据/schema API。
- [ ] 3.3 为现有ATR算法编写 adapter，不直接侵入成熟实现。
- [ ] 3.4 实现固定等差网格。
- [ ] 3.5 实现固定等比网格。
- [ ] 3.6 实现ATR自适应网格。
- [ ] 3.7 实现布林带自适应网格。
- [ ] 3.8 实现ADX、均线方向、波动率和突破保护过滤器。
- [ ] 3.9 实现等金额和仓位上限资金管理器。
- [ ] 3.10 参数schema校验及算法版本启停机制。

### 4. 统一模拟执行内核
- [ ] 4.1 定义 Order、Trade、Position、CashLedger、GridState。
- [ ] 4.2 实现费用、滑点、最小单位及现金/仓位校验。
- [ ] 4.3 实现5分钟bar限价撮合及同bar多事件确定性规则。
- [ ] 4.4 将历史回测接入统一 SimulationEngine。
- [ ] 4.5 输出收益、夏普、回撤、成交数、资金利用率及网格状态。
- [ ] 4.6 保存参数、算法版本、执行假设和数据窗口快照。

### 5. 策略中心与绑定
- [ ] 5.1 策略模板 CRUD。
- [ ] 5.2 ETF绑定 primary/candidate/benchmark 策略。
- [ ] 5.3 支持 fixed/compare/auto 运行模式。
- [ ] 5.4 模板修改采用版本递增，历史快照不回写。
- [ ] 5.5 前端动态schema表单、过滤器及资金风控配置。

### 6. 持仓感知
- [ ] 6.1 账户 CRUD，第一阶段支持 manual/paper 类型。
- [ ] 6.2 人工录入可用现金、持仓数量、可用数量、平均成本和仓位上限。
- [ ] 6.3 活动 strategy_instance 和 grid_state 管理。
- [ ] 6.4 PortfolioConstraintEngine：将市场推荐转换为账户行动。
- [ ] 6.5 行动枚举：维持、调整、暂停买入、只卖不买、补底仓、启动、观望、数据不足。
- [ ] 6.6 所有人工校准保存审计记录。

### 7. 模块化 AnalysisPipeline
- [ ] 7.1 定义 AnalysisRequest/AnalysisResult，不依赖 Flask 或 scheduler。
- [ ] 7.2 实现数据准备、共享特征、候选生成、统一评价、评分、滞回、持仓约束和解释步骤。
- [ ] 7.3 支持 persist=false，供历史模拟或即时预览复用。
- [ ] 7.4 固定版本化评分函数，禁止候选间简单min-max。
- [ ] 7.5 实现数据不足、单算法失败和全部失败的降级语义。
- [ ] 7.6 每日报告分别保存 market_recommendation 和 portfolio_advice。

### 8. 运行与调度
- [ ] 8.1 analysis_runs 使用 run_date+attempt，状态含 partial/stale。
- [ ] 8.2 pending 原子领取、worker_id、heartbeat 和 lease。
- [ ] 8.3 单标的/单策略错误隔离；支持仅重跑失败项。
- [ ] 8.4 scheduler 16:30 Asia/Shanghai 创建每日任务，并轮询手工请求。
- [ ] 8.5 Docker Compose 拆分 web 与 scheduler service。
- [ ] 8.6 SIGTERM、安全退出、重启恢复和日志结构化。

### 9. API 与前端
- [ ] 9.1 ETF池 CRUD、策略绑定和运行模式。
- [ ] 9.2 手工/每日分析触发和进度查询。
- [ ] 9.3 最新/历史报告及单策略evaluation明细。
- [ ] 9.4 策略中心页面。
- [ ] 9.5 持仓录入与活动网格页面。
- [ ] 9.6 每日报告同时展示市场推荐、账户行动、数据质量、窗口和版本。
- [ ] 9.7 全局导航和移动端适配。

### 10. Paper Trading 后续阶段
- [ ] 10.1 建立 paper_orders、paper_trades、account_snapshots。
- [ ] 10.2 历史回放页面直接调用 SimulationEngine。
- [ ] 10.3 向前模拟由独立 bar runner 驱动，不塞入每日 scheduler。
- [ ] 10.4 每日分析读取模拟账户持仓，并输出账户层建议。

### 11. 自动化验证
- [ ] 11.1 单元测试：参数schema、代码标准化、评分、滞回、持仓约束、状态机、adjustment单调性。
- [ ] 11.2 集成测试：API -> pending -> claim -> pipeline -> report。
- [ ] 11.3 并发测试：两个scheduler只能claim一次。
- [ ] 11.4 恢复测试：SIGTERM、lease超时、attempt重跑、partial仅重跑失败项。
- [ ] 11.5 数据测试：缺bar、重复、过期、本地fallback、全部不足。
- [ ] 11.6 公平性测试：所有策略使用相同窗口、资金、费用和撮合规则。
- [ ] 11.7 Docker测试：卷权限、WAL文件、时区、web/scheduler独立重启、跨重建保留。

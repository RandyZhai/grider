## ADDED Requirements

### Requirement: 模块化分析流水线
系统 SHALL 将每日分析实现为不依赖 Flask request 或 scheduler 的可复用 AnalysisPipeline，并允许定时任务、手工分析、历史回放及模拟交易相关功能调用相同的数据准备、特征计算、算法评价、评分和解释能力。

#### Scenario: scheduler 调用
- **WHEN** 每日任务领取一条 pending run
- **THEN** scheduler 构造 AnalysisRequest 调用 AnalysisPipeline，并持久化运行及报告

#### Scenario: 其它模块复用
- **WHEN** 历史模拟或即时分析以 persist=false 调用流水线
- **THEN** 系统返回相同结构的 AnalysisResult，且不创建每日运行记录

#### Scenario: 调用隔离
- **WHEN** AnalysisPipeline 被非 HTTP 调用方使用
- **THEN** 不要求 Flask application/request context，且算法不直接访问数据库或网络

### Requirement: 多网格算法与插件注册
系统 SHALL 支持通过注册表调用多个版本化网格算法。第一阶段至少包括固定等差、固定等比、ATR自适应和布林带自适应；趋势过滤器和资金管理器 SHALL 与基础算法解耦组合。

#### Scenario: 查询算法参数
- **WHEN** 前端请求某算法 schema
- **THEN** 返回算法版本、参数类型、默认值、范围、选项和说明

#### Scenario: 新增插件
- **WHEN** 新算法实现统一接口并注册
- **THEN** 运行器、调度器和报告主流程无需修改即可调用

#### Scenario: 插件禁用
- **WHEN** 某算法版本被禁用
- **THEN** 新任务不再调用它，但历史评估仍可查看和复现

### Requirement: 前台策略配置
系统 SHALL 提供策略模板 CRUD，并允许用户配置算法、参数、过滤器、资金管理和风险限制。ETF SHALL 可绑定一个主策略及多个候选或基准策略。

#### Scenario: 动态表单
- **WHEN** 用户选择算法
- **THEN** 前端按参数 schema 渲染并校验配置

#### Scenario: 参数无效
- **WHEN** 参数超出 schema 范围或类型错误
- **THEN** API 拒绝保存并返回具体字段错误

#### Scenario: 历史快照
- **WHEN** 用户修改策略模板
- **THEN** 新运行使用新版本，历史运行继续保留原算法版本和参数快照

### Requirement: 多策略运行模式
系统 SHALL 支持 fixed、compare 和 auto 三种模式。

#### Scenario: fixed
- **WHEN** ETF 处于 fixed 模式
- **THEN** 仅运行其主策略

#### Scenario: compare
- **WHEN** ETF 处于 compare 模式
- **THEN** 在相同数据窗口、资金、费用、滑点、最小单位和撮合规则下评价全部启用绑定

#### Scenario: auto
- **WHEN** ETF 处于 auto 模式
- **THEN** 系统可先按市场状态缩小候选，再统一评价并输出建议，但不得自动修改当前策略

### Requirement: 本地数据闭环与质量
系统 SHALL 将日线写入 SQLite，并将5分钟K按标的和交易日持久缓存。缺口 SHALL 依据交易日历和算法 required_data 判断。

#### Scenario: fallback 回写
- **WHEN** SQLite 缺少日线且文件缓存或外部源成功返回
- **THEN** 数据经标准化和校验后写回 SQLite，再从统一存储返回

#### Scenario: 分钟缓存离线运行
- **WHEN** 外部分钟源失败且本地缓存满足算法最低窗口
- **THEN** 使用本地数据完成评价并标注数据来源及截止时间

#### Scenario: 分钟数据不足
- **WHEN** 某候选策略所需分钟数据不足
- **THEN** 仅该 evaluation 标记 insufficient，不影响其它候选

#### Scenario: 全部候选不足
- **WHEN** 所有候选均数据不足
- **THEN** 不输出确定性切换建议，行动标记为数据不足或观望

### Requirement: 统一模拟执行语义
系统 SHALL 使用统一 SimulationEngine 执行历史回测，并为未来 Paper Trading 复用订单、成交、费用、持仓和网格状态语义。

#### Scenario: 公平比较
- **WHEN** 多策略参加同一运行
- **THEN** 所有策略使用相同初始资金、时间窗口、手续费、滑点、最小交易单位和成交规则

#### Scenario: 结果可复现
- **WHEN** 查看历史 evaluation
- **THEN** 可获得算法版本、参数快照、执行假设、数据窗口、bar数量及数据质量

#### Scenario: 同bar歧义
- **WHEN** 同一5分钟bar可能同时触发多个买卖条件
- **THEN** SimulationEngine 按版本化的确定性规则处理，并将规则版本写入结果

### Requirement: 持仓感知
系统 SHALL 支持账户现金、人工或模拟持仓、平均成本、仓位限制、活动策略和网格状态，并在每日运行中区分市场推荐与账户行动建议。

#### Scenario: 空仓
- **WHEN** 市场层推荐某策略且账户为空仓
- **THEN** 账户层评估是否启动、初始底仓和预留现金，而非假定已持仓

#### Scenario: 仓位过高
- **WHEN** 市场层偏好高频但当前仓位达到或超过配置上限
- **THEN** 账户层不得建议继续加仓，可输出暂停买入或只卖不买

#### Scenario: 已有活动网格
- **WHEN** ETF 已绑定 active strategy_instance
- **THEN** 每日分析读取其参数快照、当前格、下一买卖价及预留资金，评价维持或调整，而非从空仓重建

#### Scenario: 无账户信息
- **WHEN** 分析请求未提供 account_id
- **THEN** 系统仍输出市场推荐，但明确不生成账户层可执行建议

### Requirement: 推荐评分与切换滞回
系统 SHALL 使用固定边界、版本化评分函数，不得仅在两个候选间简单 min-max。策略切换 SHALL 同时满足数据质量、评分优势、稳定确认和账户约束。

#### Scenario: 优势不足
- **WHEN** 推荐策略与当前策略的评分差小于切换阈值
- **THEN** 行动为维持

#### Scenario: 推荐被持仓约束否决
- **WHEN** 市场推荐满足切换阈值但账户现金或仓位不允许执行
- **THEN** 保留市场推荐，同时账户行动显示维持、观望或风险限制原因

### Requirement: ETF池与历史保留
系统 SHALL 支持 ETF 池增删查及策略绑定，删除采用软删除并保留历史报告、持仓和评估引用。

#### Scenario: 添加重复ETF
- **WHEN** 相同标准 instrument_id 已存在
- **THEN** 返回重复错误或恢复已软删除记录，不创建第二条记录

#### Scenario: 移除ETF
- **WHEN** 用户从池中移除ETF
- **THEN** active 置为 false，历史运行与报告仍可查询

### Requirement: 可靠运行状态机
系统 SHALL 使用 run_date+attempt 标识运行，支持 pending、running、done、partial、failed、cancelled、stale，并通过原子领取、heartbeat 和 lease 避免重复执行。

#### Scenario: 原子领取
- **WHEN** 两个 scheduler 同时尝试领取同一 pending run
- **THEN** 只有一个更新成功并执行

#### Scenario: 部分失败
- **WHEN** 部分标的或策略失败而其余成功
- **THEN** run 状态为 partial，并保存成功与失败明细

#### Scenario: stale恢复
- **WHEN** running 的 heartbeat 超过 lease
- **THEN** 该 attempt 标记 stale，并允许新 attempt 重跑失败或未完成项

#### Scenario: 当日重跑
- **WHEN** 当日已有 failed/partial/stale 且用户重试
- **THEN** 创建 attempt+1，不覆盖旧运行及报告

### Requirement: 定时与部署
系统 SHALL 以 Asia/Shanghai 判定交易日和16:30触发时间，数据库时间戳统一保存为 UTC。web 与 scheduler SHALL 作为独立服务运行并共享持久化卷。

#### Scenario: 服务独立重启
- **WHEN** web 或 scheduler 单独重启
- **THEN** 另一服务不受影响，运行及缓存数据跨容器重建保留

#### Scenario: 优雅退出
- **WHEN** scheduler 收到 SIGTERM
- **THEN** 停止领取新任务，完成当前安全写入后退出

### Requirement: 前端展示
系统 SHALL 提供 ETF池、策略中心、持仓/模拟和每日报告入口。

#### Scenario: 每日报告
- **WHEN** 用户查看某ETF今日结果
- **THEN** 同时显示市场推荐、账户行动、当前/推荐策略、评分差、数据质量、数据窗口、算法版本和解释

#### Scenario: 运行进度
- **WHEN** 批量分析正在执行
- **THEN** 显示标的及策略级完成、失败和总数，结束后自动刷新

### Requirement: Paper Trading 扩展边界
系统 SHALL 为未来 Paper Trading 复用算法插件、SimulationEngine、账户、持仓和网格状态，但盘中模拟不得由每日16:30任务承担。

#### Scenario: 历史回放
- **WHEN** 用户运行历史模拟
- **THEN** 使用统一 SimulationEngine 产生订单、成交、持仓及净值结果

#### Scenario: 向前模拟
- **WHEN** 后续启用5分钟 Paper Trading
- **THEN** 由独立 bar runner 推进并更新模拟账户；每日分析只读取其最新状态并生成收盘建议

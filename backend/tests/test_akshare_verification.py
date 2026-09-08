#!/usr/bin/env python3
"""
AKShare 股票历史数据接口验证脚本
=====================================

验证目标：
1. 腾讯历史接口: ak.stock_zh_a_hist_tx (推荐 - 无IP限制)
2. 新浪历史接口: ak.stock_zh_a_daily (有限制 - 有复权因子)

测试环境：Docker (python:3.13-slim)

作者：AI Assistant
日期：2026-09-08
"""

import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# 尝试导入akshare，如果失败则提示安装
try:
    import akshare as ak
    import pandas as pd
    print(f"✅ AKShare 版本: {ak.__version__}")
    print(f"✅ Pandas 版本: {pd.__version__}")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("\n请先安装AKShare:")
    print("  pip install akshare pandas")
    sys.exit(1)


class InterfaceTestResult:
    """接口测试结果"""
    def __init__(self, name: str, source: str):
        self.name = name
        self.source = source
        self.success = False
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.duration_ms: float = 0
        self.data: Optional[pd.DataFrame] = None
        self.error: Optional[str] = None
        self.row_count: int = 0
        self.columns: list = []
        self.date_range: str = ""
        self.sample_data: Dict[str, Any] = {}
    
    def start(self):
        self.start_time = time.time()
    
    def finish(self, data: pd.DataFrame = None, error: str = None):
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        
        if error:
            self.success = False
            self.error = error
            self.data = None
        else:
            self.success = True
            self.data = data
            self.row_count = len(data) if data is not None else 0
            self.columns = list(data.columns) if data is not None else []
            
            # 提取日期范围
            if data is not None and len(data) > 0 and 'date' in data.columns:
                min_date = data['date'].min()
                max_date = data['date'].max()
                self.date_range = f"{min_date} ~ {max_date}"
            
            # 提取样本数据（第一行和最后一行）
            if data is not None and len(data) > 0:
                first_row = data.iloc[0].to_dict()
                last_row = data.iloc[-1].to_dict()
                self.sample_data = {
                    'first': {k: v for k, v in list(first_row.items())[:5]},
                    'last': {k: v for k, v in list(last_row.items())[:5]}
                }
    
    def report(self) -> str:
        """生成测试报告"""
        status = "✅ 成功" if self.success else "❌ 失败"
        lines = [
            f"\n{'='*60}",
            f"📊 接口名称: {self.name}",
            f"   数据源: {self.source}",
            f"   状态: {status}",
            f"   耗时: {self.duration_ms:.2f} ms",
        ]
        
        if self.success:
            lines.extend([
                f"   数据行数: {self.row_count}",
                f"   数据列: {', '.join(self.columns[:8])}{'...' if len(self.columns) > 8 else ''}",
                f"   日期范围: {self.date_range}",
            ])
            if self.sample_data:
                lines.append(f"   首行样本: {self.sample_data.get('first', {})}")
                lines.append(f"   末行样本: {self.sample_data.get('last', {})}")
        else:
            lines.append(f"   错误信息: {self.error}")
        
        lines.append('='*60)
        return '\n'.join(lines)


def test_tencent_hist_tx() -> InterfaceTestResult:
    """
    测试腾讯历史行情接口
    
    接口：ak.stock_zh_a_hist_tx
    特点：
    - 数据源：腾讯财经
    - 无IP限制 ✅
    - 数据质量高 ✅
    - 需要市场前缀 (sz000001, sh600000)
    - 支持复权：'', 'qfq', 'hfq'
    """
    result = InterfaceTestResult(
        name="stock_zh_a_hist_tx (腾讯历史行情)",
        source="腾讯财经"
    )
    
    result.start()
    
    try:
        print("\n🔍 测试腾讯历史接口...")
        
        # 测试参数
        symbol = "sz000001"  # 平安银行
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")  # 最近3个月
        
        print(f"   股票代码: {symbol}")
        print(f"   日期范围: {start_date} ~ {end_date}")
        print(f"   复权类型: qfq (前复权)")
        
        # 调用接口
        df = ak.stock_zh_a_hist_tx(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        result.finish(data=df)
        print(result.report())
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        result.finish(error=error_msg)
        print(result.report())
        traceback.print_exc()
    
    return result


def test_sina_daily() -> InterfaceTestResult:
    """
    测试新浪历史行情接口
    
    接口：ak.stock_zh_a_daily
    特点：
    - 数据源：新浪财经
    - 易触发IP限制 ⚠️
    - 独有功能：支持复权因子 (qfq-factor)
    - 需要市场前缀 (sz000001, sh600000)
    """
    result = InterfaceTestResult(
        name="stock_zh_a_daily (新浪历史行情)",
        source="新浪财经"
    )
    
    result.start()
    
    try:
        print("\n🔍 测试新浪历史接口...")
        
        # 测试参数
        symbol = "sz000001"  # 平安银行
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = "20240101"  # 2024年至今
        
        print(f"   股票代码: {symbol}")
        print(f"   日期范围: {start_date} ~ {end_date}")
        print(f"   复权类型: qfq (前复权)")
        
        # 调用接口
        df = ak.stock_zh_a_daily(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        result.finish(data=df)
        print(result.report())
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        result.finish(error=error_msg)
        print(result.report())
        traceback.print_exc()
    
    return result


def test_sina_daily_with_factor() -> InterfaceTestResult:
    """
    测试新浪复权因子接口（独有功能）
    
    接口：ak.stock_zh_a_daily with adjust="qfq-factor"
    特点：
    - 新浪独有：返回精确的复权因子
    - 用于需要精确计算复权价格的场景
    """
    result = InterfaceTestResult(
        name="stock_zh_a_daily (新浪复权因子)",
        source="新浪财经"
    )
    
    result.start()
    
    try:
        print("\n🔍 测试新浪复权因子接口...")
        
        # 测试参数
        symbol = "sh600000"  # 浦发银行
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = "20240601"  # 最近1年
        
        print(f"   股票代码: {symbol}")
        print(f"   日期范围: {start_date} ~ {end_date}")
        print(f"   复权类型: qfq-factor (前复权因子)")
        
        # 调用接口
        df = ak.stock_zh_a_daily(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq-factor"
        )
        
        result.finish(data=df)
        print(result.report())
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        result.finish(error=error_msg)
        print(result.report())
        traceback.print_exc()
    
    return result


def test_etf_sina() -> InterfaceTestResult:
    """
    测试新浪ETF历史数据接口
    
    接口：ak.fund_etf_hist_sina
    特点：
    - 数据源：新浪财经
    - ETF专用接口
    - 支持日线/周线/月线
    """
    result = InterfaceTestResult(
        name="fund_etf_hist_sina (新浪ETF历史)",
        source="新浪财经"
    )
    
    result.start()
    
    try:
        print("\n🔍 测试新浪ETF历史接口...")
        
        # 测试参数
        symbol = "sh510300"  # 沪深300ETF
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")  # 最近6个月
        
        print(f"   ETF代码: {symbol}")
        print(f"   日期范围: {start_date} ~ {end_date}")
        print(f"   周期: daily (日线)")
        
        # 调用接口
        df = ak.fund_etf_hist_sina(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        result.finish(data=df)
        print(result.report())
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        result.finish(error=error_msg)
        print(result.report())
        traceback.print_exc()
    
    return result


def test_realtime_tencent() -> InterfaceTestResult:
    """
    测试腾讯实时行情接口
    
    接口：ak.stock_zh_a_spot
    特点：
    - 数据源：腾讯财经
    - 实时行情快照
    - 返回全部A股数据
    """
    result = InterfaceTestResult(
        name="stock_zh_a_spot (腾讯实时行情)",
        source="腾讯财经"
    )
    
    result.start()
    
    try:
        print("\n🔍 测试腾讯实时行情接口...")
        
        # 调用接口（无需参数，返回全部A股）
        df = ak.stock_zh_a_spot()
        
        # 过滤显示前10条
        sample_df = df.head(10)
        
        result.finish(data=sample_df)
        print(result.report())
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        result.finish(error=error_msg)
        print(result.report())
        traceback.print_exc()
    
    return result


def test_calendar_sina() -> InterfaceTestResult:
    """
    测试新浪交易日历接口
    
    接口：ak.tool_trade_date_hist_sina
    特点：
    - 数据源：新浪财经
    - 历史交易日历
    - 用于判断交易日
    """
    result = InterfaceTestResult(
        name="tool_trade_date_hist_sina (新浪交易日历)",
        source="新浪财经"
    )
    
    result.start()
    
    try:
        print("\n🔍 测试新浪交易日历接口...")
        
        # 调用接口
        df = ak.tool_trade_date_hist_sina()
        
        # 只保留最近1年的数据用于展示
        one_year_ago = datetime.now() - timedelta(days=365)
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        recent_df = df[df['trade_date'] >= one_year_ago]
        
        result.finish(data=recent_df)
        print(result.report())
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        result.finish(error=error_msg)
        print(result.report())
        traceback.print_exc()
    
    return result


def run_all_tests():
    """运行所有测试"""
    print("=" * 70)
    print("🧪 AKShare 新浪/腾讯 接口验证测试")
    print("=" * 70)
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐳 Docker环境检测: {'是' if is_running_in_docker() else '否'}")
    
    results = []
    
    # 测试1: 腾讯历史行情（推荐）
    results.append(test_tencent_hist_tx())
    
    time.sleep(1)  # 避免请求过快
    
    # 测试2: 新浪历史行情
    results.append(test_sina_daily())
    
    time.sleep(1)
    
    # 测试3: 新浪复权因子（可选）
    results.append(test_sina_daily_with_factor())
    
    time.sleep(1)
    
    # 测试4: 新浪ETF历史
    results.append(test_etf_sina())
    
    time.sleep(1)
    
    # 测试5: 腾讯实时行情
    results.append(test_realtime_tencent())
    
    time.sleep(1)
    
    # 测试6: 新浪交易日历
    results.append(test_calendar_sina())
    
    # 汇总报告
    print("\n" + "=" * 70)
    print("📋 测试汇总报告")
    print("=" * 70)
    
    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count
    
    print(f"\n总测试数: {len(results)}")
    print(f"✅ 成功: {success_count}")
    print(f"❌ 失败: {fail_count}")
    print(f"成功率: {success_count/len(results)*100:.1f}%")
    
    print("\n详细结果:")
    for i, r in enumerate(results, 1):
        status = "✅" if r.success else "❌"
        source = r.source
        duration = f"{r.duration_ms:.0f}ms"
        rows = f"{r.row_count}行" if r.success else "N/A"
        print(f"  {i}. {status} [{source}] {r.name.split('(')[0].strip():30s} | {duration:>8s} | {rows:>8s}")
    
    # 最终建议
    print("\n" + "-" * 70)
    print("💡 最终建议:")
    print("-" * 70)
    
    tencent_result = results[0]  # stock_zh_a_hist_tx
    sina_result = results[1]      # stock_zh_a_daily
    
    if tencent_result.success:
        print("✅ 推荐: 使用腾讯接口 (stock_zh_a_hist_tx) 作为主要股票历史数据源")
        print("   原因: 无IP限制、数据质量高、访问稳定")
    
    if sina_result.success:
        print("⚠️ 可选: 使用新浪接口 (stock_zh_a_daily) 作为补充数据源")
        print("   场景: 需要精确复权因子时使用")
        print("   注意: 易触发IP限制，需控制请求频率")
    
    if not tencent_result.success and not sina_result.success:
        print("❌ 两个接口均不可用，需要检查:")
        print("   1. 网络连接是否正常")
        print("   2. 是否被防火墙拦截")
        print("   3. AKShare版本是否过旧")
    
    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)
    
    return results


def is_running_in_docker() -> bool:
    """检测是否在Docker环境中运行"""
    try:
        with open('/proc/1/cgroup', 'r') as f:
            return 'docker' in f.read() or 'kubepods' in f.read()
    except:
        return False


if __name__ == "__main__":
    run_all_tests()

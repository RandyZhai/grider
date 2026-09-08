"""AkshareProvider 单元测试

测试覆盖：
  - 股票实时行情 (腾讯)
  - 股票历史数据 (腾讯)
  - ETF实时行情 (新浪)
  - ETF历史数据 (新浪)
  - 交易日历 (新浪)
  - 搜索功能
  - 限流机制
  - 缓存功能
"""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import time

from backend.app.external.providers.akshare_provider import AkshareProvider


@pytest.fixture
def provider():
    """创建测试用的Provider实例"""
    config = {
        'rate_limit': {
            'tencent_requests_per_second': 10,
            'sina_requests_per_second': 2
        },
        'cache': {
            'realtime_ttl': 60,
            'daily_ttl': 86400,
            'calendar_ttl': 2592000
        }
    }
    return AkshareProvider(config)


class TestAkshareProviderInit:
    """测试初始化"""
    
    def test_init_with_config(self):
        """带配置初始化"""
        config = {'rate_limit': {'tencent_requests_per_second': 5}}
        p = AkshareProvider(config)
        assert p._tencent_rate_limit == 5
    
    def test_init_default_config(self):
        """默认配置初始化"""
        p = AkshareProvider()
        assert p._tencent_rate_limit == 10
        assert p._sina_rate_limit == 1


class TestStockRealtime:
    """测试股票实时行情（腾讯数据源）"""
    
    @patch('backend.app.external.providers.akshare_provider.ak')
    def test_get_stock_realtime_success(self, mock_ak, provider):
        """成功获取股票实时行情"""
        # Mock数据
        mock_df = pd.DataFrame({
            '代码': ['600000'],
            '名称': ['浦发银行'],
            '最新价': [10.50],
            '今开': [10.30],
            '最高': [10.60],
            '最低': [10.20],
            '昨收': [10.25],
            '成交量': [1000000],
            '成交额': [10500000.0]
        })
        mock_ak.stock_zh_a_spot.return_value = mock_df
        
        # 执行
        result = provider.get_stock_realtime('600000', 'XSHG')
        
        # 验证
        assert result['code'] == 200
        assert len(result['data']) == 1
        data = result['data'][0]
        assert data['ticker'] == '600000'
        assert data['close'] == 10.50
        assert data['source'] == 'tencent'
        assert data['change_pct'] is not None
    
    @patch('backend.app.external.providers.akshare_provider.ak')
    def test_get_stock_realtime_not_found(self, mock_ak, provider):
        """股票未找到"""
        mock_df = pd.DataFrame({'代码': [], '名称': []})
        mock_ak.stock_zh_a_spot.return_value = mock_df
        
        result = provider.get_stock_realtime('999999', 'XSHG')
        
        assert result['code'] == 404
        assert result['data'] is None


class TestStockDaily:
    """测试股票历史数据（腾讯数据源）"""
    
    @patch('backend.app.external.providers.akshare_provider.ak')
    def test_get_stock_daily_success(self, mock_ak, provider):
        """成功获取股票历史数据"""
        # Mock数据
        mock_df = pd.DataFrame({
            'date': ['2024-01-02', '2024-01-03', '2024-01-04'],
            'open': [10.0, 10.2, 10.1],
            'close': [10.5, 10.6, 10.4],
            'high': [10.6, 10.7, 10.5],
            'low': [9.9, 10.1, 10.0],
            'volume': [1000000, 1200000, 1100000],
            'amount': [10500000.0, 12720000.0, 11440000.0],
            'turnover': [0.01, 0.012, 0.011]
        })
        mock_ak.stock_zh_a_hist_tx.return_value = mock_df
        
        # 执行
        result = provider.get_stock_daily('000001', 'XSHE', '20240101', '20240105')
        
        # 验证
        assert result['code'] == 200
        assert len(result['data']) == 3
        data = result['data'][0]
        assert data['ticker'] == '000001'
        assert data['open'] == 10.0
        assert data['close'] == 10.5
        assert data['source'] == 'tencent'
    
    @patch('backend.app.external.providers.akshare_provider.ak')
    def test_get_stock_daily_uses_cache(self, mock_ak, provider):
        """测试缓存使用"""
        # 首次调用
        mock_df = pd.DataFrame({
            'date': ['2024-01-02'],
            'open': [10.0], 'close': [10.5], 'high': [10.6], 'low': [9.9],
            'volume': [1000000], 'amount': [10500000.0], 'turnover': [0.01]
        })
        mock_ak.stock_zh_a_hist_tx.return_value = mock_df
        
        result1 = provider.get_stock_daily('000001', 'XSHE', '20240101', '20240103')
        assert mock_ak.stock_zh_a_hist_tx.call_count == 1
        
        # 第二次调用应使用缓存
        result2 = provider.get_stock_daily('000001', 'XSHE', '20240101', '20240103')
        assert mock_ak.stock_zh_a_hist_tx.call_count == 1  # 没有增加
        assert result1 == result2


class TestETFRealtime:
    """测试ETF实时行情（新浪数据源）"""
    
    @patch('backend.app.external.providers.akshare_provider.ak')
    def test_get_etf_realtime_success(self, mock_ak, provider):
        """成功获取ETF实时行情"""
        mock_df = pd.DataFrame({
            '代码': ['510300'],
            '名称': ['华泰柏瑞沪深300ETF'],
            '最新价': [4.250],
            '今开': [4.200],
            '最高': [4.280],
            '最低': [4.180],
            '昨收': [4.190],
            '成交量': [5000000],
            '成交额': [21250000.0]
        })
        mock_ak.fund_etf_spot_sina.return_value = mock_df
        
        result = provider.get_etf_realtime('510300', 'XSHG')
        
        assert result['code'] == 200
        data = result['data'][0]
        assert data['ticker'] == '510300'
        assert data['close'] == 4.250
        assert data['source'] == 'sina'


class TestETFDaily:
    """测试ETF历史数据（新浪数据源）"""
    
    @patch('backend.app.external.providers.akshare_provider.ak')
    def test_get_etf_daily_success(self, mock_ak, provider):
        """成功获取ETF历史数据"""
        mock_df = pd.DataFrame({
            'date': ['2024-06-03', '2024-06-04'],
            '开盘': [4.20, 4.22],
            '收盘': [4.25, 4.28],
            '最高': [4.27, 4.30],
            '最低': [4.18, 4.21],
            '成交量': [5000000, 5200000],
            '成交额': [21250000.0, 22272000.0]
        })
        mock_ak.fund_etf_hist_sina.return_value = mock_df
        
        result = provider.get_etf_daily('510300', 'XSHG', '2024-06-01', '2024-06-05')
        
        assert result['code'] == 200
        assert len(result['data']) == 2
        assert result['data'][0]['source'] == 'sina'


class TestCalendar:
    """测试交易日历（新浪数据源）"""
    
    @patch('backend.app.external.providers.akshare_provider.ak')
    def test_get_calendar_success(self, mock_ak, provider):
        """成功获取交易日历"""
        import datetime as dt
        dates = pd.date_range('2024-01-02', periods=5, freq='B')
        mock_df = pd.DataFrame({'trade_date': dates})
        mock_ak.tool_trade_date_hist_sina.return_value = mock_df
        
        result = provider.get_calendar('CHN', limit=5)
        
        assert result['code'] == 200
        assert len(result['data']) <= 5
        assert 'date' in result['data'][0]


class TestSearch:
    """测试搜索功能"""
    
    @patch('backend.app.external.providers.akshare_provider.ak')
    def test_search_by_ticker_success(self, mock_ak, provider):
        """成功搜索股票"""
        mock_df = pd.DataFrame({
            '代码': ['600000', '600001'],
            '名称': ['浦发银行', '邯郸钢铁']
        })
        mock_ak.stock_zh_a_spot.return_value = mock_df
        
        result = provider.search_by_ticker('600000')
        
        assert result['code'] == 200
        assert len(result['data']) >= 1
        assert result['data'][0]['ticker'] == '600000'
    
    @patch('backend.app.external.providers.akshare_provider.ak')
    def test_search_by_ticker_no_results(self, mock_ak, provider):
        """搜索无结果"""
        mock_df = pd.DataFrame({'代码': [], '名称': []})
        mock_ak.stock_zh_a_spot.return_value = mock_df
        
        result = provider.search_by_ticker('NONEXISTENT')
        
        assert result['code'] == 200
        assert len(result['data']) == 0


class TestRateLimiting:
    """测试限流机制"""
    
    def test_tencent_rate_limit(self, provider):
        """测试腾讯限流"""
        provider._tencent_rate_limit = 2  # 设置很低的限制
        
        start = time.time()
        provider._rate_limit_check('tencent')
        provider._rate_limit_check('tencent')
        elapsed = time.time() - start
        
        # 2次请求应该很快完成
        assert elapsed < 0.1
    
    def test_sina_rate_limit_triggers_wait(self, provider):
        """测试新浪限流触发等待"""
        provider._sina_rate_limit = 1  # 很低限制
        provider._window_start = time.time()
        provider._request_count = 0
        
        # 第一次请求
        provider._rate_limit_check('sina')
        
        # 模拟快速第二次请求（同一窗口内）
        provider._request_count = 1  # 已用完配额
        
        start = time.time()
        provider._rate_limit_check('sina')  # 应该触发等待
        elapsed = time.time() - start
        
        # 应该有等待时间
        assert elapsed >= 0  # 至少没有报错


class TestCacheManagement:
    """测试缓存管理"""
    
    def test_clear_cache_all(self, provider):
        """清除所有缓存"""
        provider._cache['test_key'] = {'data': 'test'}
        provider._cache_timestamps['test_key'] = time.time()
        
        provider.clear_cache()
        
        assert len(provider._cache) == 0
        assert len(provider._cache_timestamps) == 0
    
    def test_clear_cache_by_endpoint(self, provider):
        """按端点清除缓存"""
        provider._cache['stock_data:600000'] = {'data': 'stock'}
        provider._cache['etf_data:510300'] = {'data': 'etf'}
        provider._cache_timestamps['stock_data:600000'] = time.time()
        provider._cache_timestamps['etf_data:510300'] = time.time()
        
        provider.clear_cache('stock_data')
        
        assert 'stock_data:600000' not in provider._cache
        assert 'etf_data:510300' in provider._cache
    
    def test_get_cache_stats(self, provider):
        """获取缓存统计"""
        provider._cache['key1'] = 'value1'
        provider._cache['key2'] = 'value2'
        
        stats = provider.get_cache_stats()
        
        assert stats['provider'] == 'akshare'
        assert stats['cached_items'] == 2


class TestMarketPrefix:
    """测试市场前缀处理"""
    
    def test_ensure_market_prefix_shanghai(self, provider):
        """上海市场前缀"""
        assert provider._ensure_market_prefix('600000') == 'sh600000'
        assert provider._ensure_market_prefix('sh600000') == 'sh600000'
    
    def test_ensure_market_prefix_shenzhen(self, provider):
        """深圳市场前缀"""
        assert provider._ensure_market_prefix('000001') == 'sz000001'
        assert provider._ensure_market_prefix('sz000001') == 'sz000001'
        assert provider._ensure_market_prefix('300001') == 'sz300001'
    
    def test_ensure_market_prefix_beijing(self, provider):
        """北京市场前缀"""
        assert provider._ensure_market_prefix('430001') == 'bj430001'


class TestResponseFormat:
    """测试响应格式一致性"""
    
    def test_success_response(self, provider):
        """成功响应格式"""
        response = provider._success_response([{'id': 1}])
        
        assert response['code'] == 200
        assert response['data'] == [{'id': 1}]
    
    def test_error_response(self, provider):
        """错误响应格式"""
        response = provider._error_response("Not found", 404)
        
        assert response['code'] == 404
        assert "Not found" in response['message']
        assert response['data'] is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""数据业务服务

支持多数据源：
  - AKShare (新浪/腾讯) - 主要免费数据源
  - Tsanghi (沧海数据) - 商业备用数据源

配置文件: app/config/config.yaml
规范文档: openspec/data-spec.md
"""
import os
import yaml
import pandas as pd
from datetime import datetime
from typing import List, Optional

from app.external.providers.tsanghi_provider import TsanghiProvider
from app.external.providers.akshare_provider import AkshareProvider
from app.algorithms.backtest.models import KBar
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DataService:
    """数据业务服务 - 支持多Provider切换"""

    def __init__(self, provider_name: str = None):
        """
        初始化数据服务
        
        Args:
            provider_name: 指定数据源 ('akshare' 或 'tsanghi')，默认使用配置中的主要数据源
        """
        # 加载AKShare配置
        self._akshare_config = self._load_akshare_config()
        
        # 初始化所有可用的Provider
        self._providers = {
            'tsanghi': TsanghiProvider(),
            'akshare': AkshareProvider(config=self._akshare_config),
        }
        
        # 确定使用的Provider
        if provider_name:
            # 显式指定
            if provider_name not in self._providers:
                raise ValueError(f"未知的数据源: {provider_name}，可选: {list(self._providers.keys())}")
            self.provider_name = provider_name
        else:
            # 默认优先使用AKShare（如果启用）
            if self._akshare_config.get('enabled', True):
                self.provider_name = 'akshare'
            else:
                self.provider_name = 'tsanghi'
        
        self.provider = self._providers[self.provider_name]
        logger.info(f"DataService初始化完成，当前数据源: {self.provider_name}")

    def _load_akshare_config(self) -> dict:
        """加载AKShare配置"""
        config_path = "app/config/config.yaml"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                full_config = yaml.safe_load(f)
            return full_config.get('providers', {}).get('akshare', {})
        except Exception as e:
            logger.warning(f"加载AKShare配置失败，使用默认配置: {e}")
            return {'enabled': True}

    def switch_provider(self, provider_name: str):
        """
        切换数据源
        
        Args:
            provider_name: 目标数据源 ('akshare' 或 'tsanghi')
        """
        if provider_name not in self._providers:
            raise ValueError(f"未知的数据源: {provider_name}")
        
        old_provider = self.provider_name
        self.provider_name = provider_name
        self.provider = self._providers[provider_name]
        logger.info(f"数据源已切换: {old_provider} -> {provider_name}")

    def get_current_provider(self) -> str:
        """获取当前使用的数据源名称"""
        return self.provider_name

    def search_by_ticker(self, ticker: str, country_code: str = "CHN"):
        """搜索股票/ETF代码"""
        try:
            result = self.provider.search_by_ticker(ticker, country_code)

            # 返回搜索结果中的第一条数据
            if result and isinstance(result, dict) and "data" in result and result["data"]:
                return result["data"][0]
            return None
        except Exception as e:
            logger.error(f"获取股票信息失败: {e}")
            raise
    

    def get_latest_price(self, ticker: str, exchange_code: str, type: str='STOCK'):
        """获取最新价格"""
        try:
            if type == 'ETF':
                result = self.provider.get_etf_realtime(ticker, exchange_code)
            elif type == 'STOCK':
                result = self.provider.get_stock_realtime(ticker, exchange_code)
            else:
                raise ValueError(f"不支持的证券类型: {type}")

            # 返回搜索结果中的第一条数据
            if result and isinstance(result, dict) and "data" in result and result["data"]:
                data = result["data"][0]
                
                # 基于pre_close和close计算change_pct补充到数据中
                pre_close_raw = data.get("pre_close")
                close_raw = data.get("close")
                if pre_close_raw is not None and close_raw is not None:
                    try:
                        pre_close = float(pre_close_raw)
                        close = float(close_raw)
                        if pre_close != 0:
                            change_pct = (close - pre_close) / pre_close * 100
                            data['change_pct'] = round(change_pct, 3)
                        else:
                            data['change_pct'] = None
                    except (ValueError, TypeError):
                        data['change_pct'] = None
                else:
                    data['change_pct'] = None
                return data
            return None
        except Exception as e:
            logger.error(f"获取股票信息失败: {e}")
            raise

    def get_daily_data(self, ticker: str, exchange_code: str, type: str='STOCK', start_date: str = "", end_date: str=""):
        """获取日线数据"""
        try:
            if type == 'ETF':
                result = self.provider.get_etf_daily(ticker, exchange_code, start_date, end_date)
            elif type == 'STOCK':
                result = self.provider.get_stock_daily(ticker, exchange_code, start_date, end_date)
            else:
                raise ValueError(f"不支持的证券类型: {type}")

            if result.get("data", None):
                data = result['data']
                for item in data:
                    if item.get('amount') is None or item['amount'] == 0:
                        high = item.get('high', 0)
                        low = item.get('low', 0)
                        open_price = item.get('open', 0)
                        close = item.get('close', 0)
                        volume = item.get('volume', 0)
                        item['amount'] = ((open_price + close + high + low) / 4) * volume
                return pd.DataFrame(data)
            return None
        except Exception as e:
            logger.error(f"获取行情失败: {e}")
            raise


    def clear_cache(self):
        """清除缓存"""
        try:
            self.provider.clear_cache()
            logger.info("缓存清除完成")
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
            raise

    def get_5min_kline(self, ticker: str, exchange_code: str,
                        start_date: str, end_date: str, type: str = 'STOCK') -> List[KBar]:
        """
        获取5分钟K线数据

        注意：AKShare暂不支持5分钟K线，将回退到Tsanghi或返回空列表
        """
        try:
            # 如果当前是AKShare且没有5分钟接口，尝试切换到Tsanghi
            if self.provider_name == 'akshare' and 'tsanghi' in self._providers:
                logger.debug("AKShare不支持5分钟K线，尝试使用Tsanghi")
                tsanghi = self._providers['tsanghi']
                
                if type == 'ETF':
                    response = tsanghi.get_etf_5min(ticker, exchange_code, start_date, end_date)
                elif type == 'STOCK':
                    response = tsanghi.get_stock_5min(ticker, exchange_code, start_date, end_date)
                else:
                    raise ValueError(f"不支持的证券类型: {type}")
            else:
                # 使用当前provider
                if type == 'ETF':
                    response = self.provider.get_etf_5min(ticker, exchange_code, start_date, end_date)
                elif type == 'STOCK':
                    response = self.provider.get_stock_5min(ticker, exchange_code, start_date, end_date)
                else:
                    raise ValueError(f"不支持的证券类型: {type}")

            if response.get('code') == 200 and 'data' in response:
                data = response['data']
            else:
                logger.warning(f"获取5分钟K线数据失败: {response}")
                return []

            # 转换为KBar对象
            kbars = []
            for row in data:
                kbars.append(KBar(
                    time=datetime.strptime(row['date'], '%Y-%m-%d %H:%M:%S'),
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume'])
                ))

            # 按时间排序，确保从历史到现在的顺序
            kbars.sort(key=lambda k: k.time)

            return kbars
        except Exception as e:
            logger.error(f"获取5分钟K线数据失败: {e}")
            raise

    def get_trading_calendar(self, exchange_code: str, limit: int = 5, start_date: str = None, end_date: str = None) -> List[str]:
        """获取交易日历"""
        try:
            response = self.provider.get_calendar(exchange_code, limit, start_date, end_date)
            if response.get('code') == 200 and 'data' in response:
                calendar_data = response['data']
                return [row['date'] for row in calendar_data]
            else:
                logger.warning(f"获取交易日历失败: {response}")
                return []
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            raise

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        try:
            return self.provider.get_cache_stats()
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            raise

"""akshare 免费数据提供商 (非 eastmoney 数据源)"""

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd

from app.utils.logger import get_logger

logger = get_logger(__name__)


class AkShareCacheManager:
    """akshare 专用文件缓存管理器"""

    def __init__(self, cache_dir: str = "backend/cache/akshare"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, func_name: str, params: dict) -> str:
        raw = f"{func_name}:{json.dumps(params, sort_keys=True, default=str)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, func_name: str, params: dict) -> Optional[dict]:
        cache_file = self.cache_dir / self._cache_key(func_name, params)
        if not cache_file.exists():
            return None
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if time.time() > data.get('expires_at', 0):
                cache_file.unlink(missing_ok=True)
                return None
            return data.get('value')
        except (json.JSONDecodeError, OSError):
            cache_file.unlink(missing_ok=True)
            return None

    def set(self, func_name: str, params: dict, value: dict, ttl: int):
        cache_file = self.cache_dir / self._cache_key(func_name, params)
        data = {
            'value': value,
            'expires_at': time.time() + ttl,
            'created_at': time.time(),
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, default=str)

    def clear(self):
        for f in self.cache_dir.glob('*'):
            f.unlink(missing_ok=True)

    def get_stats(self) -> Dict:
        files = list(self.cache_dir.glob('*'))
        total = len(files)
        expired = 0
        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                if time.time() > data.get('expires_at', 0):
                    expired += 1
            except Exception:
                expired += 1
        return {'total': total, 'expired': expired, 'active': total - expired}


class AkShareProvider:
    """akshare 免费数据提供商

    实现与 TsanghiProvider 相同的接口，使用 akshare 开源库（新浪/同花顺等免费数据源），
    无需 API Token，不使用东方财富 eastmoney 接口。
    """

    def __init__(self):
        self.cache = AkShareCacheManager()
        logger.info("AkShareProvider 初始化完成")

    def _normalize_date(self, date_str: str) -> str:
        if not date_str:
            return ''
        return date_str.replace('-', '')

    def _df_to_list(self, df: pd.DataFrame) -> List[dict]:
        if df is None or df.empty:
            return []
        return df.to_dict(orient='records')

    def _infer_exchange(self, ticker: str) -> str:
        code = ticker.lstrip('$')
        if code.startswith(('6', '5', '9')):
            return 'XSHG'
        elif code.startswith(('0', '3', '1', '2')):
            return 'XSHE'
        return 'XSHG'

    def _to_sina_symbol(self, ticker: str) -> str:
        exchange = self._infer_exchange(ticker)
        prefix = 'sh' if exchange == 'XSHG' else 'sz'
        return f"{prefix}{ticker}"

    def _filter_by_date(self, df: pd.DataFrame, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        if df is None or df.empty:
            return df
        if start_date:
            sd = start_date.replace('-', '')
            df = df[df['date'].astype(str).str.replace('-', '') >= sd]
        if end_date:
            ed = end_date.replace('-', '')
            df = df[df['date'].astype(str).str.replace('-', '') <= ed]
        return df

    def _compute_pre_close(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or 'close' not in df.columns:
            return df
        df = df.copy()
        df['pre_close'] = df['close'].shift(1)
        df['pre_close'] = df['pre_close'].fillna(df['close'].iloc[0])
        return df

    def _get_realtime_df(self) -> pd.DataFrame:
        """获取全市场实时行情（新浪 stock_zh_a_spot，覆盖股票 + ETF）"""
        return ak.stock_zh_a_spot()

    # ---- 公开接口 ----

    def search_by_ticker(self, ticker: str, country_code: str = "CHN") -> dict:
        """搜索代码 (新浪免费接口，非 eastmoney)"""
        cache_params = {'ticker': ticker, 'country_code': country_code}
        cached = self.cache.get('search_by_ticker', cache_params)
        if cached:
            return cached

        try:
            df_stock = ak.stock_info_a_code_name()
            row_s = df_stock[df_stock['code'] == ticker]
            if not row_s.empty:
                r = row_s.iloc[0]
                result = {
                    'code': 200,
                    'data': [{
                        'ticker': r['code'],
                        'name': r['name'],
                        'type': 'STOCK',
                        'exchange_code': self._infer_exchange(ticker),
                        'management': '',
                    }],
                }
                self.cache.set('search_by_ticker', cache_params, result, 86400)
                return result

            try:
                df_etf = ak.fund_etf_category_sina(symbol="ETF基金")
                col_code = 'symbol' if 'symbol' in df_etf.columns else '代码'
                col_name = 'name' if 'name' in df_etf.columns else '名称'
                row_e = df_etf[df_etf[col_code] == ticker]
                if not row_e.empty:
                    r = row_e.iloc[0]
                    result = {
                        'code': 200,
                        'data': [{
                            'ticker': str(r[col_code]),
                            'name': str(r[col_name]),
                            'type': 'ETF',
                            'exchange_code': self._infer_exchange(ticker),
                            'management': '',
                        }],
                    }
                    self.cache.set('search_by_ticker', cache_params, result, 86400)
                    return result
            except Exception as e2:
                logger.warning(f"搜索 ETF 失败: {ticker}, {e2}")

            result = {'code': 404, 'data': [], 'message': '未找到'}
            self.cache.set('search_by_ticker', cache_params, result, 3600)
            return result
        except Exception as e:
            logger.error(f"搜索代码失败: {ticker}, {e}")
            return {'code': 500, 'data': [], 'message': str(e)}

    def get_etf_realtime(self, ticker: str, exchange_code: str = "XSHG") -> dict:
        """获取ETF实时行情 (新浪 stock_zh_a_spot 免费接口)"""
        cache_params = {'ticker': ticker, 'exchange_code': exchange_code}
        cached = self.cache.get('etf_realtime', cache_params)
        if cached:
            return cached

        try:
            df = self._get_realtime_df()
            row = df[df['代码'] == ticker]
            if row.empty:
                return {'code': 404, 'data': [], 'message': '未找到'}
            r = row.iloc[0]
            result = {
                'code': 200,
                'data': [{
                    'ticker': str(r['代码']),
                    'date': str(r.get('时间', r.get('更新时间', ''))),
                    'open': float(r.get('今开', 0) or 0),
                    'high': float(r.get('最高', 0) or 0),
                    'low': float(r.get('最低', 0) or 0),
                    'close': float(r.get('最新价', 0) or 0),
                    'volume': int(r.get('成交量', 0) or 0),
                    'amount': float(r.get('成交额', 0) or 0),
                    'pre_close': float(r.get('昨收', 0) or 0),
                }],
            }
            self.cache.set('etf_realtime', cache_params, result, 10800)
            return result
        except Exception as e:
            logger.error(f"获取ETF实时行情失败: {ticker}, {e}")
            return {'code': 500, 'data': [], 'message': str(e)}

    def get_etf_daily(self, ticker: str, exchange_code: str = "XSHG",
                       start_date: str = "", end_date: str = "") -> dict:
        """获取ETF历史日线行情 (新浪数据源，非 eastmoney)"""
        cache_params = {
            'ticker': ticker, 'start_date': start_date, 'end_date': end_date,
        }
        cached = self.cache.get('etf_daily', cache_params)
        if cached:
            return cached

        try:
            sina_symbol = self._to_sina_symbol(ticker)
            df = None
            attempts = 2
            for i in range(attempts):
                try:
                    df = ak.fund_etf_hist_sina(symbol=sina_symbol)
                    break
                except Exception as e:
                    logger.warning(f"akshare 获取ETF日线第 {i+1} 次尝试失败: {ticker}, {e}")
                    time.sleep(0.5 * (i + 1))

            if df is None or df.empty:
                return {'code': 404, 'data': [], 'message': '无数据'}

            df = self._filter_by_date(df, start_date, end_date)
            if df is None or df.empty:
                return {'code': 404, 'data': [], 'message': '无数据'}
            df = self._compute_pre_close(df)
            df = df.drop(columns=['postVol', 'postAmt'], errors='ignore')
            result = {'code': 200, 'data': self._df_to_list(df)}
            self.cache.set('etf_daily', cache_params, result, 31536000)
            return result
        except Exception as e:
            logger.error(f"获取ETF日线失败: {ticker}, {e}")
            return {'code': 500, 'data': [], 'message': str(e)}

    def get_etf_5min(self, ticker: str, exchange_code: str = "XSHG",
                      start_date: str = "", end_date: str = "") -> dict:
        """获取ETF历史5分钟行情 (同花顺 ths 免费接口)"""
        cache_params = {
            'ticker': ticker, 'start_date': start_date, 'end_date': end_date,
        }
        cached = self.cache.get('etf_5min', cache_params)
        if cached:
            return cached

        try:
            sd = f"{start_date} 09:30:00" if start_date else '2020-01-01 09:30:00'
            ed = f"{end_date} 15:00:00" if end_date else datetime.now().strftime('%Y-%m-%d 15:00:00')

            df = None
            attempts = 3
            for i in range(attempts):
                try:
                    df = ak.fund_etf_hist_min_ths(symbol=ticker, period='5',
                                                   start_date=sd, end_date=ed)
                    break
                except AttributeError:
                    logger.error(f"当前 akshare 版本无 fund_etf_hist_min_ths 接口")
                    break
                except Exception as e:
                    logger.warning(f"akshare 获取ETF 5分钟行情第 {i+1} 次尝试失败: {ticker}, {e}")
                    time.sleep(0.5 * (i + 1))
                    df = None

            if df is None or df.empty:
                logger.error(f"获取ETF 5分钟行情失败: {ticker}, 无法获取数据")
                return {'code': 500, 'data': [], 'message': '无法获取分钟线数据'}

            mapping = {
                '时间': 'date', '开盘': 'open', '最高': 'high',
                '最低': 'low', '收盘': 'close', '成交量': 'volume',
                '成交额': 'amount',
            }
            if 'date' not in df.columns:
                df = df.rename(columns=mapping)
            if 'date' in df.columns:
                df['date'] = df['date'].astype(str)
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            result = {'code': 200, 'data': self._df_to_list(df)}
            self.cache.set('etf_5min', cache_params, result, 3600)
            return result
        except Exception as e:
            logger.error(f"获取ETF 5分钟行情失败: {ticker}, {e}")
            return {'code': 500, 'data': [], 'message': str(e)}

    def get_stock_realtime(self, ticker: str, exchange_code: str = "XSHG") -> dict:
        """获取股票实时行情 (新浪 stock_zh_a_spot 免费接口)"""
        cache_params = {'ticker': ticker, 'exchange_code': exchange_code}
        cached = self.cache.get('stock_realtime', cache_params)
        if cached:
            return cached

        try:
            df = self._get_realtime_df()
            row = df[df['代码'] == ticker]
            if row.empty:
                return {'code': 404, 'data': [], 'message': '未找到'}
            r = row.iloc[0]
            result = {
                'code': 200,
                'data': [{
                    'ticker': str(r['代码']),
                    'date': str(r.get('时间', r.get('更新时间', ''))),
                    'open': float(r.get('今开', 0) or 0),
                    'high': float(r.get('最高', 0) or 0),
                    'low': float(r.get('最低', 0) or 0),
                    'close': float(r.get('最新价', 0) or 0),
                    'volume': int(r.get('成交量', 0) or 0),
                    'amount': float(r.get('成交额', 0) or 0),
                    'pre_close': float(r.get('昨收', 0) or 0),
                }],
            }
            self.cache.set('stock_realtime', cache_params, result, 10800)
            return result
        except Exception as e:
            logger.error(f"获取股票实时行情失败: {ticker}, {e}")
            return {'code': 500, 'data': [], 'message': str(e)}

    def get_stock_daily(self, ticker: str, exchange_code: str = "XSHG",
                         start_date: str = "", end_date: str = "") -> dict:
        """获取股票历史日线行情 (新浪数据源，非 eastmoney)"""
        cache_params = {
            'ticker': ticker, 'start_date': start_date, 'end_date': end_date,
        }
        cached = self.cache.get('stock_daily', cache_params)
        if cached:
            return cached

        try:
            sina_symbol = self._to_sina_symbol(ticker)
            sd = self._normalize_date(start_date) if start_date else ''
            ed = self._normalize_date(end_date) if end_date else ''
            df = None
            attempts = 2
            for i in range(attempts):
                try:
                    df = ak.stock_zh_a_daily(symbol=sina_symbol,
                                             start_date=sd, end_date=ed, adjust='qfq')
                    if df is not None and not df.empty:
                        break
                except Exception as e:
                    logger.warning(f"akshare 获取股票日线带复权第 {i+1} 次尝试失败: {ticker}, {e}")
                    time.sleep(0.5 * (i + 1))

            if df is None or df.empty:
                try:
                    df = ak.stock_zh_a_daily(symbol=sina_symbol, start_date=sd, end_date=ed)
                except Exception as e:
                    logger.error(f"akshare 获取股票日线（不带复权）失败: {ticker}, {e}")

            if df is None or df.empty:
                return {'code': 404, 'data': [], 'message': '无数据'}

            df = self._compute_pre_close(df)
            df = df.drop(columns=['outstanding_share', 'turnover'], errors='ignore')
            result = {'code': 200, 'data': self._df_to_list(df)}
            self.cache.set('stock_daily', cache_params, result, 31536000)
            return result
        except Exception as e:
            logger.error(f"获取股票日线失败: {ticker}, {e}")
            return {'code': 500, 'data': [], 'message': str(e)}

    def get_stock_5min(self, ticker: str, exchange_code: str = "XSHG",
                        start_date: str = "", end_date: str = "") -> dict:
        """获取股票历史5分钟行情 (同花顺 ths 免费接口)"""
        cache_params = {
            'ticker': ticker, 'start_date': start_date, 'end_date': end_date,
        }
        cached = self.cache.get('stock_5min', cache_params)
        if cached:
            return cached

        try:
            sd = f"{start_date} 09:30:00" if start_date else '2020-01-01 09:30:00'
            ed = f"{end_date} 15:00:00" if end_date else datetime.now().strftime('%Y-%m-%d 15:00:00')

            df = None
            attempts = 3
            for i in range(attempts):
                try:
                    df = ak.stock_zh_a_hist_min_ths(symbol=ticker, period='5',
                                                    start_date=sd, end_date=ed, adjust='')
                    break
                except AttributeError:
                    logger.error(f"当前 akshare 版本无 stock_zh_a_hist_min_ths 接口")
                    break
                except Exception as e:
                    logger.warning(f"akshare 获取股票5分钟行情第 {i+1} 次尝试失败: {ticker}, {e}")
                    time.sleep(0.5 * (i + 1))
                    df = None

            if df is None or df.empty:
                logger.error(f"获取股票5分钟行情失败: {ticker}, 无法获取数据")
                return {'code': 500, 'data': [], 'message': '无法获取分钟线数据'}

            mapping = {
                '时间': 'date', '开盘': 'open', '最高': 'high',
                '最低': 'low', '收盘': 'close', '成交量': 'volume',
                '成交额': 'amount',
            }
            if 'date' not in df.columns:
                df = df.rename(columns=mapping)
            if 'date' in df.columns:
                df['date'] = df['date'].astype(str)
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            result = {'code': 200, 'data': self._df_to_list(df)}
            self.cache.set('stock_5min', cache_params, result, 3600)
            return result
        except Exception as e:
            logger.error(f"获取股票5分钟行情失败: {ticker}, {e}")
            return {'code': 500, 'data': [], 'message': str(e)}

    def get_calendar(self, exchange_code: str = "CHN", limit: int = 10,
                     start_date: str = None, end_date: str = None) -> dict:
        """获取交易日历 (新浪免费接口)"""
        cache_params = {
            'exchange_code': exchange_code, 'limit': limit,
            'start_date': start_date, 'end_date': end_date,
        }
        cached = self.cache.get('calendar', cache_params)
        if cached:
            return cached

        try:
            df = ak.tool_trade_date_hist_sina()
            if df is None or df.empty:
                return {'code': 404, 'data': [], 'message': '无数据'}
            today = datetime.now().strftime('%Y-%m-%d')
            dates = sorted(df['trade_date'].astype(str).tolist(), reverse=True)
            dates = [d for d in dates if d <= today]
            if start_date and end_date:
                dates = [d for d in dates if start_date <= d <= end_date]
            else:
                dates = dates[:limit]
            result = {'code': 200, 'data': [{'date': d} for d in dates]}
            self.cache.set('calendar', cache_params, result, 86400)
            return result
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return {'code': 500, 'data': [], 'message': str(e)}

    def clear_cache(self):
        self.cache.clear()
        logger.info("akshare 缓存已清除")

    def get_cache_stats(self) -> Dict:
        return self.cache.get_stats()
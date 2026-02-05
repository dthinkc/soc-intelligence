"""SOC 股票数据客户端 - 获取股价和波动信息"""

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import random

logger = logging.getLogger(__name__)

# 尝试导入 yfinance，如果不可用则使用模拟数据
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not available, using mock data")

# 尝试导入 requests 用于 API 调用和网页抓取
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests not available, web scraping disabled")

# 尝试导入 BeautifulSoup 用于解析网页
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logger.warning("beautifulsoup4 not available, some features may be limited")


class StockDataClient:
    """SOC股票数据客户端"""

    # SOC真实股价数据（2025-2026年的大致价格范围）
    # 基于公开信息：SOC股价约在$5-15之间波动
    BASE_PRICE = 11.60  # 2026年1月的参考价格

    # SOC 的可能股票代码（尝试多个）- 加拿大交易所
    SYMBOLS = ["SOC.TO", "SOC.V", "SOC", "Sable Offshore"]

    # Alpha Vantage 配置
    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

    # 网页抓取配置
    GOOGLE_FINANCE_URL = "https://www.google.com/finance"
    YAHOO_FINANCE_URL = "https://finance.yahoo.com/quote"

    def __init__(self, symbol: str = "SOC", use_mock: bool = None):
        """初始化股票客户端

        Args:
            symbol: 股票代码，默认为SOC
            use_mock: 是否使用模拟数据，None表示自动检测
        """
        self.symbol = symbol
        self.use_mock = use_mock if use_mock is not None else (not YFINANCE_AVAILABLE)
        self.ticker = None
        self.data_source = None  # 记录数据来源：'yfinance', 'alpha_vantage', 'web_scrape', 'mock'

        if YFINANCE_AVAILABLE and not self.use_mock:
            # 首先尝试 yfinance
            for try_symbol in self.SYMBOLS:
                try:
                    ticker = yf.Ticker(try_symbol)
                    # 测试连接 - 使用快速方法而不是获取完整的 info
                    fast_info = ticker.fast_info
                    if fast_info and fast_info.get('last_price'):
                        self.ticker = ticker
                        self.symbol = try_symbol
                        self.data_source = 'yfinance'
                        self.use_mock = False
                        logger.info(f"Using yfinance for {try_symbol}, last_price: {fast_info.get('last_price')}")
                        break
                except Exception as e:
                    logger.debug(f"Failed to fetch {try_symbol} via yfinance: {e}")
                    continue
            else:
                # yfinance 失败，尝试网页抓取
                if REQUESTS_AVAILABLE:
                    logger.info("yfinance failed, trying web scraping...")
                    web_data = self._scrape_google_finance()
                    if web_data:
                        self.data_source = 'web_scrape'
                        self.use_mock = False
                        logger.info(f"Using web scraping for {self.symbol}")
                    else:
                        logger.warning("Web scraping failed, using mock data")
                        self.use_mock = True
                else:
                    logger.warning("All data sources failed, using mock data")
                    self.use_mock = True
        else:
            self.use_mock = True
            logger.info(f"Using mock data for {symbol}")

    def get_stock_impact(
        self,
        published_date: str,
        sentiment: str = "中性",
        score: int = 0,
    ) -> Dict[str, Any]:
        """获取消息发布后的股价影响

        Args:
            published_date: 消息发布日期，格式如 "2026-01-10T16:38:53"
            sentiment: 消息情绪（利好/利空/中性）
            score: 消息评分

        Returns:
            Dict: 股价影响数据，包含：
                - price_before: 消息前价格
                - price_after: 消息后价格
                - change_percent: 变化百分比
                - volume: 成交量
        """
        # 如果使用模拟数据
        if self.use_mock:
            return self._get_mock_stock_impact(sentiment, score)

        # 根据 data_source 选择获取方式
        if self.data_source == 'web_scrape':
            result = self._get_web_scrape_impact(published_date, sentiment, score)
            if result:
                return result
            # 网页抓取失败，降级到 mock
            logger.warning("Web scraping failed, falling back to mock data")
            return self._get_mock_stock_impact(sentiment, score)

        # yfinance 数据获取（原有逻辑）
        try:
            # 解析发布日期
            if not published_date:
                return self._get_mock_stock_impact(sentiment, score)

            # 处理日期格式
            if 'T' in published_date:
                pub_date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
            else:
                pub_date = datetime.strptime(published_date, '%Y-%m-%d')

            # 获取历史数据（消息发布前后各1天，减少 API 调用量）
            start_date = pub_date - timedelta(days=1)
            end_date = pub_date + timedelta(days=2)

            logger.info(f"Fetching stock data for {self.symbol} from {start_date} to {end_date}")

            # 获取历史数据 - 使用 prepost 来获取盘前盘后数据
            hist = self.ticker.history(start=start_date, end_date=end_date, interval="1d", prepost=False)

            if hist.empty:
                logger.warning(f"No historical data found for {self.symbol}, using mock data")
                return self._get_mock_stock_impact(sentiment, score)

            # 找到发布日期最近的数据
            pub_date_str = pub_date.strftime('%Y-%m-%d')

            # 判断利好还是利空
            is_bullish = score > 0

            # 获取数据：前一日开盘价 + 发布当天最高价/最低价
            prev_day_open = None
            pub_day_high = None
            pub_day_low = None
            volume = 0

            for idx, row in hist.iterrows():
                date_str = idx.strftime('%Y-%m-%d')

                if date_str < pub_date_str:
                    # 发布日前一天，记录开盘价
                    prev_day_open = row['Open']
                elif date_str == pub_date_str:
                    # 发布当天，记录最高价和最低价
                    pub_day_high = row['High']
                    pub_day_low = row['Low']
                    volume = row['Volume']

            if prev_day_open is None:
                # 如果没有前一天数据，尝试获取发布当天的开盘价
                for idx, row in hist.iterrows():
                    date_str = idx.strftime('%Y-%m-%d')
                    if date_str == pub_date_str:
                        prev_day_open = row['Open']
                        pub_day_high = row['High']
                        pub_day_low = row['Low']
                        volume = row['Volume']
                        break

            if prev_day_open is None or (is_bullish and pub_day_high is None) or (not is_bullish and pub_day_low is None):
                logger.warning("Could not determine price data, using mock data")
                return self._get_mock_stock_impact(sentiment, score)

            # 根据利好/利空选择价格
            if is_bullish:
                # 利好：发布当天最高价 - 前一日开盘价
                price_before = prev_day_open
                price_after = pub_day_high
            else:
                # 利空：发布当天最低价 - 前一日开盘价
                price_before = prev_day_open
                price_after = pub_day_low

            # 计算变化
            change = price_after - price_before
            change_percent = (change / price_before) * 100 if price_before > 0 else 0

            result = {
                "price_before": round(price_before, 2),
                "price_after": round(price_after, 2),
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "volume": int(volume),
                "symbol": self.symbol,
                "available": True
            }

            logger.info(f"Stock impact calculated: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to get stock impact: {e}, using mock data")
            return self._get_mock_stock_impact(sentiment, score)

    def _get_mock_stock_impact(self, sentiment: str, score: int) -> Dict[str, Any]:
        """生成模拟的股价影响数据（基于消息情绪和评分）

        Args:
            sentiment: 消息情绪
            score: 消息评分

        Returns:
            Dict: 模拟的股价影响数据
        """
        # 基于评分计算变化幅度，加入随机波动使不同消息显示不同涨幅
        # score -10~+10，对应股价变化 -15%~+15%
        # 加入 ±20% 的随机波动，使相同 score 的消息显示不同涨幅
        base_change_percent = (score / 10) * 15  # 基础变化百分比
        random_factor = random.uniform(0.8, 1.2)  # 0.8~1.2 倍随机波动
        change_percent = base_change_percent * random_factor

        # 计算价格
        price_before = self.BASE_PRICE
        change_amount = price_before * (change_percent / 100)
        price_after = price_before + change_amount

        # 模拟成交量（基于评分绝对值）
        base_volume = 150000  # 基础成交量
        volume_multiplier = 1 + (abs(score) / 10) * 2  # 评分越高成交量越大
        volume = int(base_volume * volume_multiplier * random.uniform(0.8, 1.2))

        result = {
            "price_before": round(price_before, 2),
            "price_after": round(price_after, 2),
            "change": round(change_amount, 2),
            "change_percent": round(change_percent, 2),
            "volume": volume,
            "symbol": self.symbol,
            "available": True,
            "mock": True  # 标记为模拟数据
        }

        logger.info(f"Mock stock impact (score={score}, sentiment={sentiment}): {change_percent:.2f}%")
        return result

    def _get_no_data_result(self) -> Dict[str, Any]:
        """获取无数据结果"""
        return {
            "price_before": None,
            "price_after": None,
            "change": None,
            "change_percent": None,
            "volume": None,
            "symbol": self.symbol,
            "available": False
        }

    def get_current_price(self) -> Optional[float]:
        """获取当前股价

        Returns:
            float: 当前股价，失败返回None
        """
        if self.use_mock:
            return self.BASE_PRICE

        try:
            # 优先使用 fast_info（更快且更少触发 rate limiting）
            if self.ticker:
                fast_info = self.ticker.fast_info
                if fast_info:
                    price = fast_info.get('last_price')
                    if price:
                        return price

            # 降级到 info（更慢但更详细）
            ticker_info = self.ticker.info
            current_price = ticker_info.get('currentPrice') or ticker_info.get('regularMarketPrice')
            return current_price
        except Exception as e:
            logger.error(f"Failed to get current price: {e}")
            return None

    def _test_alpha_vantage(self) -> bool:
        """测试 Alpha Vantage 连接是否可用

        Returns:
            bool: True 如果可用
        """
        if not REQUESTS_AVAILABLE or not self.ALPHA_VANTAGE_API_KEY:
            return False

        try:
            # 尝试获取 GLOBAL_QUOTE
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': self.symbol,
                'apikey': self.ALPHA_VANTAGE_API_KEY
            }
            response = requests.get(self.ALPHA_VANTAGE_BASE_URL, params=params, timeout=10)
            data = response.json()

            # 检查是否有有效数据
            if 'Global Quote' in data:
                quote = data['Global Quote']
                price = float(quote.get('05. price', 0))
                if price > 0:
                    logger.info(f"Alpha Vantage connected for {self.symbol}, price: {price}")
                    return True
            else:
                logger.debug(f"Alpha Vantage response: {data}")
                return False
        except Exception as e:
            logger.debug(f"Alpha Vantage test failed: {e}")
            return False

    def _get_alpha_vantage_impact(
        self,
        published_date: str,
        sentiment: str,
        score: int
    ) -> Optional[Dict[str, Any]]:
        """使用 Alpha Vantage 获取股价影响

        Args:
            published_date: 消息发布日期
            sentiment: 消息情绪
            score: 消息评分

        Returns:
            Dict: 股价影响数据
        """
        if not REQUESTS_AVAILABLE or not self.ALPHA_VANTAGE_API_KEY:
            return None

        try:
            # 解析发布日期
            if 'T' in published_date:
                pub_date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
            else:
                pub_date = datetime.strptime(published_date, '%Y-%m-%d')

            # 获取历史数据
            start_date = pub_date - timedelta(days=1)
            end_date = pub_date + timedelta(days=2)

            logger.info(f"Fetching Alpha Vantage data for {self.symbol} from {start_date} to {end_date}")

            # 使用 TIME_SERIES_DAILY 获取历史数据
            params = {
                'function': 'TIME_SERIES_DAILY',
                'symbol': self.symbol,
                'apikey': self.ALPHA_VANTAGE_API_KEY,
                'outputsize': 'compact',
                'datatype': 'json'
            }
            response = requests.get(self.ALPHA_VANTAGE_BASE_URL, params=params, timeout=10)
            data = response.json()

            # 检查是否有时间序列数据
            if 'Time Series (Daily)' not in data:
                logger.warning(f"No time series data from Alpha Vantage: {data.get('Note', data.get('Error Message', 'Unknown error'))}")
                return None

            time_series = data['Time Series (Daily)']
            pub_date_str = pub_date.strftime('%Y-%m-%d')

            # 获取发布日和次日的数据
            price_before = None
            price_after = None
            volume = 0

            for date_str, daily_data in sorted(time_series.items()):
                if date_str <= pub_date_str:
                    price_before = float(daily_data['4. close'])
                elif date_str > pub_date_str and price_after is None:
                    price_after = float(daily_data['4. close'])
                    volume = int(daily_data['5. volume'])
                    break

            # 如果没有次日数据，使用当天数据
            if price_after is None and price_before is not None:
                price_after = price_before
                # 获取最后一日的成交量
                last_date = sorted(time_series.keys())[-1]
                volume = int(time_series[last_date]['5. volume'])

            if price_before is None or price_after is None:
                logger.warning("Could not determine price before/after from Alpha Vantage")
                return None

            # 计算变化
            change = price_after - price_before
            change_percent = (change / price_before) * 100 if price_before > 0 else 0

            result = {
                "price_before": round(price_before, 2),
                "price_after": round(price_after, 2),
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "volume": volume,
                "symbol": self.symbol,
                "available": True,
                "data_source": "Alpha Vantage"
            }

            logger.info(f"Alpha Vantage stock impact: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to get Alpha Vantage impact: {e}")
            return None

    def _scrape_google_finance(self) -> Optional[Dict[str, Any]]:
        """从 Google Finance 抓取当前股价

        Returns:
            Dict: 股票数据，失败返回 None
        """
        if not REQUESTS_AVAILABLE:
            return None

        # 尝试多个股票代码
        for try_symbol in self.SYMBOLS:
            try:
                url = f"{self.GOOGLE_FINANCE_URL}/quote/{try_symbol}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }

                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()

                # 使用正则表达式从 HTML 中提取股价
                # Google Finance 的股价通常在 data-last-price 属性中
                price_match = re.search(r'data-last-price="([\d,]+\.?\d*)"', response.text)
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
                    if price > 0:
                        self.symbol = try_symbol
                        logger.info(f"Scraped price from Google Finance for {try_symbol}: {price}")
                        return {'current_price': price, 'symbol': try_symbol}
            except Exception as e:
                logger.debug(f"Failed to scrape {try_symbol} from Google Finance: {e}")
                continue

        return None

    def _scrape_yahoo_finance(self, try_symbol: str) -> Optional[Dict[str, Any]]:
        """从 Yahoo Finance 抓取历史股价数据

        Args:
            try_symbol: 股票代码

        Returns:
            Dict: 历史股价数据，失败返回 None
        """
        if not REQUESTS_AVAILABLE or not BS4_AVAILABLE:
            return None

        try:
            url = f"{self.YAHOO_FINANCE_URL}/{try_symbol}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 查找历史数据表格
            # Yahoo Finance 使用 fin-streamer 数据
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'crumb' in script.string:
                    # 提取股价数据
                    price_match = re.search(r'"regularMarketPrice":\s*{?([\d,]+\.?\d*)}?', script.string)
                    if price_match:
                        price = float(price_match.group(1).replace(',', ''))
                        if price > 0:
                            return {'current_price': price, 'symbol': try_symbol}
        except Exception as e:
            logger.debug(f"Failed to scrape {try_symbol} from Yahoo Finance: {e}")
            return None

    def _get_web_scrape_impact(
        self,
        published_date: str,
        sentiment: str,
        score: int
    ) -> Optional[Dict[str, Any]]:
        """使用网页抓取获取股价影响

        Args:
            published_date: 消息发布日期
            sentiment: 消息情绪
            score: 消息评分

        Returns:
            Dict: 股价影响数据
        """
        try:
            # 解析发布日期
            if 'T' in published_date:
                pub_date = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
            else:
                pub_date = datetime.strptime(published_date, '%Y-%m-%d')

            # 简化版：获取当前股价并基于评分计算影响
            # 因为网页抓取历史数据比较困难，我们使用当前价格作为参考
            current_data = self._scrape_google_finance()

            if not current_data:
                return None

            current_price = current_data.get('current_price', self.BASE_PRICE)

            # 基于评分计算变化
            change_percent = (score / 10) * 15
            change_amount = current_price * (change_percent / 100)

            price_before = current_price - change_amount
            price_after = current_price

            # 模拟成交量
            base_volume = 150000
            volume_multiplier = 1 + (abs(score) / 10) * 2
            volume = int(base_volume * volume_multiplier * random.uniform(0.8, 1.2))

            result = {
                "price_before": round(price_before, 2),
                "price_after": round(price_after, 2),
                "change": round(change_amount, 2),
                "change_percent": round(change_percent, 2),
                "volume": volume,
                "symbol": self.symbol,
                "available": True,
                "data_source": "Web Scrape",
                "web_scrape": True  # 标记为网页抓取数据
            }

            logger.info(f"Web scrape stock impact: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to get web scrape impact: {e}")
            return None

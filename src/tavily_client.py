"""Tavily 搜索客户端 - 实时情报获取与去重"""

import logging
import hashlib
import re
from typing import List, Dict, Optional, Any, Set
from datetime import datetime, timedelta
from tavily import TavilyClient
import requests
from bs4 import BeautifulSoup

from .config import get_config

logger = logging.getLogger(__name__)


def extract_date_from_text(text: str, current_year: int = None) -> Optional[str]:
    """从文本中提取日期（增强版，支持时间提取）

    Args:
        text: 文本内容
        current_year: 当前年份（用于处理没有年份的日期），默认使用当前年份

    Returns:
        Optional[str]: ISO 格式的日期时间字符串，如果找不到则返回 None
    """
    if not text:
        return None

    # 默认使用当前年份（2026）
    if current_year is None:
        current_year = 2026

    # 月份映射
    months = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4,
        'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8,
        'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }

    # 时区偏移映射（转换为 UTC 小时偏移）
    timezone_offsets = {
        'ET': -5,  # Eastern Time (EST)
        'CT': -6,  # Central Time (CST)
        'MT': -7,  # Mountain Time (MST)
        'PT': -8,  # Pacific Time (PST)
        'EST': -5,
        'CST': -6,
        'MST': -7,
        'PST': -8,
        'EDT': -4,  # Eastern Daylight Time
        'CDT': -5,  # Central Daylight Time
        'MDT': -6,  # Mountain Daylight Time
        'PDT': -7,  # Pacific Daylight Time
    }

    def parse_time_to_utc(time_str: str, period: str, tz: str) -> tuple:
        """将时间字符串转换为 UTC 小时和分钟

        Args:
            time_str: 时间字符串，如 "8:01"
            period: "AM" 或 "PM"
            tz: 时区代码，如 "ET", "PT"

        Returns:
            tuple: (hour_24, minute) UTC 时间
        """
        try:
            # 解析时间
            if ':' in time_str:
                hour_str, minute_str = time_str.split(':')
                hour = int(hour_str)
                minute = int(minute_str)
            else:
                hour = int(time_str)
                minute = 0

            # 处理 AM/PM
            period_upper = period.upper().replace('.', '')
            if period_upper == 'PM' and hour != 12:
                hour += 12
            elif period_upper == 'AM' and hour == 12:
                hour = 0

            # 转换为 UTC（通过时区偏移）
            tz_upper = tz.upper().replace('.', '')
            offset = timezone_offsets.get(tz_upper, 0)
            hour -= offset  # 减去时区偏移得到 UTC

            # 标准化小时到 0-23 范围
            hour = hour % 24

            return (hour, minute)
        except Exception:
            return (0, 0)

    # 首先尝试提取带时间的完整日期时间格式（优先级最高）
    # 格式1: "Jan. 7, 2026 at 8:01 a.m. ET" 或 "Jan 7, 2026 at 3:45 p.m. ET"
    datetime_with_time_pattern = (
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\s+at\s+'
        r'(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?|am|pm|AM|PM)\s*(?:ET|CT|MT|PT|EST|CST|MST|PST|EDT|CDT|MDT|PDT)?'
    )
    match = re.search(datetime_with_time_pattern, text, re.IGNORECASE)
    if match:
        try:
            month = months.get(match.group(1)[:3], 1)
            day = int(match.group(2))
            year = int(match.group(3))
            time_str = f"{match.group(4)}:{match.group(5)}"
            period = match.group(6)
            # 查找时区
            tz_match = re.search(r'\b(ET|CT|MT|PT|EST|CST|MST|PST|EDT|CDT|MDT|PDT)\b', text[match.end():match.end()+10], re.IGNORECASE)
            tz = tz_match.group(1) if tz_match else 'ET'  # 默认 ET

            if 1 <= day <= 31 and 1 <= month <= 12 and 2020 <= year <= 2030:
                hour_24, minute = parse_time_to_utc(time_str, period, tz)
                logger.info(f"Extracted datetime with time: {year}-{month:02d}-{day:02d} {hour_24}:{minute:02d} UTC")
                return f"{year}-{month:02d}-{day:02d}T{hour_24:02d}:{minute:02d}:00Z"
        except Exception as e:
            logger.debug(f"Failed to parse datetime with time: {e}")

    # 格式2: "January 23, 2026, 2:54 PM" 或 "Jan 23, 2026, 2:54 PM" (逗号分隔)
    datetime_comma_pattern = (
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4}),\s+'
        r'(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?|am|pm|AM|PM)'
    )
    match = re.search(datetime_comma_pattern, text, re.IGNORECASE)
    if match:
        try:
            month = months.get(match.group(1)[:3], 1)
            day = int(match.group(2))
            year = int(match.group(3))
            time_str = f"{match.group(4)}:{match.group(5)}"
            period = match.group(6)
            # 查找时区（在这种格式中时区可能在时间后面）
            tz_match = re.search(r'(ET|CT|MT|PT|EST|CST|MST|PST|EDT|CDT|MDT|PDT)', text[match.end():match.end()+5], re.IGNORECASE)
            tz = tz_match.group(1) if tz_match else 'ET'  # 默认 ET

            if 1 <= day <= 31 and 1 <= month <= 12 and 2020 <= year <= 2030:
                hour_24, minute = parse_time_to_utc(time_str, period, tz)
                logger.info(f"Extracted datetime with time (comma format): {year}-{month:02d}-{day:02d} {hour_24}:{minute:02d} UTC")
                return f"{year}-{month:02d}-{day:02d}T{hour_24:02d}:{minute:02d}:00Z"
        except Exception as e:
            logger.debug(f"Failed to parse comma datetime: {e}")

    # 格式3: "Published Dec 23, 2025 | 11:13 AM EST" (竖线分隔，有Published前缀)
    published_datetime_pattern = (
        r'Published\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\s+\|\s+'
        r'(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?|am|pm|AM|PM)\s+(ET|CT|MT|PT|EST|CST|MST|PST|EDT|CDT|MDT|PDT)'
    )
    match = re.search(published_datetime_pattern, text, re.IGNORECASE)
    if match:
        try:
            month = months.get(match.group(1)[:3], 1)
            day = int(match.group(2))
            year = int(match.group(3))
            time_str = f"{match.group(4)}:{match.group(5)}"
            period = match.group(6)
            tz = match.group(7)  # 时区直接在模式中捕获

            if 1 <= day <= 31 and 1 <= month <= 12 and 2020 <= year <= 2030:
                hour_24, minute = parse_time_to_utc(time_str, period, tz)
                logger.info(f"Extracted published datetime: {year}-{month:02d}-{day:02d} {hour_24}:{minute:02d} UTC")
                return f"{year}-{month:02d}-{day:02d}T{hour_24:02d}:{minute:02d}:00Z"
        except Exception as e:
            logger.debug(f"Failed to parse published datetime: {e}")

    # 常见日期模式（按优先级排序）
    # 每个模式返回 (year, month, day) 元组
    patterns = [
        # "Monday, December 23, 2025" → year=groups[3], month=groups[1], day=groups[2]
        (r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*day,?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})',
         lambda m: (int(m.group(3)), months.get(m.group(1)[:3], 1), int(m.group(2)))),

        # "December 23, 2025" or "Dec 23, 2025" → year=groups[2], month=groups[0], day=groups[1]
        (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})',
         lambda m: (int(m.group(3)), months.get(m.group(1)[:3], 1), int(m.group(2)))),

        # "Jan 30 2026" (没有逗号) → year=groups[2], month=groups[0], day=groups[1]
        (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\s+(\d{4})',
         lambda m: (int(m.group(3)), months.get(m.group(1)[:3], 1), int(m.group(2)))),

        # "2025-12-23" or "2025/12/23" → year=groups[0], month=groups[1], day=groups[2]
        (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})',
         lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3)))),

        # "23.12.2025" or "23/12/2025" or "23-12-2025" → year=groups[2], month=groups[1], day=groups[0]
        (r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})',
         lambda m: (int(m.group(3)), int(m.group(2)), int(m.group(1)))),

        # "Jan 30" (没有年份，使用当前年份) → month=groups[0], day=groups[1]
        (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:\s|$|,)',
         lambda m: (current_year, months.get(m.group(1)[:3], 1), int(m.group(2)))),
    ]

    # 首先尝试匹配所有日期格式（优先于相对日期）
    for pattern, extractor in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                year, month, day = extractor(match)
                # 验证日期有效性
                if 1 <= day <= 31 and 1 <= month <= 12 and 2020 <= year <= 2030:
                    return f"{year}-{month:02d}-{day:02d}T00:00:00Z"
            except Exception:
                continue

    # 处理相对日期（Today, Yesterday）- 只在没有找到具体日期时才使用
    # 使用更精确的模式，避免匹配 "today announced" 之类的文本
    text_lower = text.lower()

    # 检查是否是真正的 "Today" 日期引用（通常是标题或开头的短语）
    today_patterns = [
        r'^today\s*[,-]?',  # 开头是 "Today"
        r'\(today\)\s',     # "(Today) "
        r'today,\s',        # "Today, "
        r'posted today\b',  # "posted today"
        r'published today\b', # "published today"
    ]

    for pattern in today_patterns:
        if re.search(pattern, text_lower):
            from datetime import datetime as dt
            now = dt.now()
            return now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 检查是否是真正的 "Yesterday" 日期引用
    yesterday_patterns = [
        r'^yesterday\s*[,-]?',
        r'\(yesterday\)\s',
        r'yesterday,\s',
        r'posted yesterday\b',
        r'published yesterday\b',
    ]

    for pattern in yesterday_patterns:
        if re.search(pattern, text_lower):
            from datetime import datetime as dt, timedelta as td
            yesterday = dt.now() - td(days=1)
            return yesterday.strftime("%Y-%m-%dT%H:%M:%SZ")

    return None


class TavilySearchClient:
    """Tavily 搜索客户端 - 情报去重与精简"""

    def __init__(self, api_key: Optional[str] = None):
        """初始化 Tavily 客户端

        Args:
            api_key: Tavily API Key，默认从配置读取
        """
        config = get_config()
        self.api_key = api_key or config.TAVILY_API_KEY
        self.max_results = config.SEARCH_MAX_RESULTS
        self.client = TavilyClient(api_key=self.api_key)

        # 历史记录用于去重
        self._seen_urls: Set[str] = set()
        self._seen_hashes: Set[str] = set()

    def search_intelligence(
        self,
        query: str = "SOC PHMSA pipeline restart approval Sable",
        max_results: Optional[int] = None,
        days_lookback: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """搜索 SOC 情报（去重版）

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            days_lookback: 回溯天数

        Returns:
            List[Dict]: 去重后的情报列表
        """
        config = get_config()
        max_results = max_results or self.max_results
        days_lookback = days_lookback or config.SEARCH_DAYS_LOOKBACK

        # 每次搜索时清除历史记录，避免永久去重
        self._seen_urls.clear()
        self._seen_hashes.clear()

        try:
            logger.info(f"Searching intelligence: {query}")

            response = self.client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results * 2,  # 多取一些用于去重
                include_raw_content=True,
                days=days_lookback,
            )

            results = self._parse_and_deduplicate(response)
            logger.info(f"Found {len(results)} unique intelligence items")

            return results

        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return []

    def _parse_and_deduplicate(self, response: Dict) -> List[Dict[str, Any]]:
        """解析并去重搜索结果

        Args:
            response: Tavily API 响应

        Returns:
            List[Dict]: 去重后的情报列表
        """
        results = []

        for item in response.get("results", []):
            url = item.get("url", "")
            content = item.get("content", "")
            title = item.get("title", "")

            # URL 去重
            if url in self._seen_urls:
                continue

            # 内容哈希去重（检测相似内容）
            content_hash = self._content_hash(title + content[:200])
            if content_hash in self._seen_hashes:
                continue

            # 记录已处理
            self._seen_urls.add(url)
            self._seen_hashes.add(content_hash)

            # 获取发布时间 - 新优先级：URL抓取 > Tavily > 内容提取
            # URL抓取最准确（包含具体时间），Tavily 可能只有日期（00:00）
            published_date = ""

            # 1. 优先尝试从 URL 页面抓取日期（最准确，包含具体时间）
            try:
                fetched_date = self.fetch_publish_date_from_url(url)
                if fetched_date:
                    published_date = fetched_date
                    logger.info(f"Fetched accurate date from URL: {published_date}")
            except Exception as e:
                logger.debug(f"Failed to fetch date from URL: {e}")

            # 2. 如果 URL 抓取失败，使用 Tavily 返回的日期
            if not published_date:
                tavily_date = item.get("published_date") or ""
                if tavily_date:
                    published_date = tavily_date
                    logger.debug(f"Using Tavily date: {published_date}")

            # 3. 如果 Tavily 也没有，尝试从内容中提取日期
            if not published_date:
                published_date = self._extract_date_from_content(content, title)
                logger.debug(f"Extracted from content: {published_date}")

            # 如果所有方法都失败，保留空字符串
            if not published_date:
                logger.debug(f"No date found for: {title[:50]}... (will use empty string)")

            # 精简格式
            result = {
                "title": title,
                "url": url,
                "summary": self._extract_summary(content),
                "published_date": published_date,
                "source": self._extract_domain(url),
            }
            results.append(result)

        return results[:self.max_results]

    def _content_hash(self, text: str) -> str:
        """生成内容哈希用于去重

        Args:
            text: 文本内容

        Returns:
            str: MD5 哈希值
        """
        return hashlib.md5(text.encode()).hexdigest()

    def _extract_summary(self, content: str, max_length: int = 200) -> str:
        """提取核心摘要

        Args:
            content: 原始内容
            max_length: 最大长度

        Returns:
            str: 精简摘要
        """
        # 移除多余空白
        content = " ".join(content.split())

        # 截取摘要
        if len(content) > max_length:
            return content[:max_length] + "..."

        return content

    def _extract_domain(self, url: str) -> str:
        """提取域名

        Args:
            url: URL 地址

        Returns:
            str: 域名
        """
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.replace("www.", "")
        except:
            return "Unknown"

    def get_latest_intelligence(
        self,
        keywords: Optional[List[str]] = None,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """获取最新情报流

        Args:
            keywords: 关键词列表
            max_results: 最大结果数（默认3条，节省API配额）

        Returns:
            List[Dict]: 情报列表
        """
        if keywords is None:
            # 使用更广泛的关键词以获取各种类型的 SOC 新闻
            # 包括：股价新闻、法院裁决、SEC 文件、以及 PHMSA 审批等
            keywords = ["Sable Offshore", "SOC", "stock", "news", "PHMSA", "pipeline"]

        query = " ".join(keywords)
        return self.search_intelligence(query=query, max_results=max_results or 5, days_lookback=90)

    def clear_history(self) -> None:
        """清除历史记录（用于重置去重状态）"""
        self._seen_urls.clear()
        self._seen_hashes.clear()
        logger.info("Deduplication history cleared")

    def fetch_publish_date_from_url(self, url: str) -> Optional[str]:
        """从新闻页面 URL 获取真实发布时间

        Args:
            url: 新闻页面 URL

        Returns:
            Optional[str]: ISO 格式的日期时间字符串，如果获取失败则返回 None
        """
        # 跳过已知有问题的域名（Yahoo Finance 需要 consent，会导致超时）
        problematic_domains = ['finance.yahoo.com', 'yahoo.com', 'consent.yahoo.com']
        if any(domain in url for domain in problematic_domains):
            logger.debug(f"Skipping problematic URL: {url}")
            return None

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Sec-Fetch-CH-UA': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                'Sec-Fetch-CH-UA-Mobile': '?0',
                'Sec-Fetch-CH-UA-Platform': '"Windows"',
                'Cache-Control': 'max-age=0',
                'Referer': 'https://www.google.com/',
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 常见的日期选择器（按优先级排序）
            date_selectors = [
                # JSON-LD 结构化数据
                ('script[type="application/ld+json"]', 'json'),
                # meta 标签 - 优先级最高
                'meta[property="article:published_time"]',
                'meta[property="article:modified_time"]',
                'meta[name="date"]',
                'meta[name="pubdate"]',
                'meta[name="publish_date"]',
                'meta[name="article:published_time"]',
                'meta[name="publishdate"]',
                'meta[property="og:published_time"]',
                'meta[property="og:article:published_time"]',
                # time 标签
                'time[datetime]',
                'time[pubdate]',
                'time[class*="date"]',
                'time[class*="time"]',
                # 常见 class 名称 - 更广泛的匹配
                '[class*="date"]',
                '[class*="time"]',
                '[class*="publish"]',
                '[class*="timestamp"]',
                '[id*="date"]',
                '[id*="time"]',
                '[id*="publish"]',
                # 特定网站的日期选择器
                '.article-date',
                '.post-date',
                '.entry-date',
                '.news-date',
                '.publication-date',
                '.published-date',
                '.date-published',
                '.post-meta-time',
                '.meta-date',
                '.byline-date',
                'span.date',
                'div.date',
                'p.date',
                '.timestamp',
                'article time',
                # Business Wire 特定
                '.bw-release-time',
                '.bw-pubdate',
                # MSN 特定
                '.authorInfoText',
                '.at-metadata',
            ]

            # 1. 先尝试 JSON-LD
            json_script = soup.find('script', type='application/ld+json')
            if json_script:
                import json
                try:
                    data = json.loads(json_script.string)
                    # 查找日期字段
                    date_fields = ['datePublished', 'dateCreated', 'publishDate', 'publishedDate']
                    for field in date_fields:
                        if field in data:
                            date_str = self._normalize_iso_date(data[field])
                            if date_str:
                                logger.info(f"Found date from JSON-LD ({field}): {date_str}")
                                return date_str

                    # 如果是 NewsArticle，可能有更深层结构
                    if isinstance(data, list) and len(data) > 0:
                        for item in data:
                            for field in date_fields:
                                if field in item:
                                    date_str = self._normalize_iso_date(item[field])
                                    if date_str:
                                        logger.info(f"Found date from JSON-LD array ({field}): {date_str}")
                                        return date_str
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass

            # 2. 尝试 meta 标签
            for selector in date_selectors[1:7]:
                element = soup.select_one(selector)
                if element:
                    date_str = element.get('content') or element.get('datetime') or element.text
                    date_str = self._normalize_iso_date(date_str)
                    if date_str:
                        logger.info(f"Found date from {selector}: {date_str}")
                        return date_str

            # 3. 尝试 time 标签
            time_elements = soup.find_all('time')
            for time_elem in time_elements:
                date_str = time_elem.get('datetime') or time_elem.text
                date_str = self._normalize_iso_date(date_str)
                if date_str:
                    logger.info(f"Found date from time element: {date_str}")
                    return date_str

            # 4. 尝试常见 class 名称
            for selector in date_selectors[7:]:
                elements = soup.select(selector)
                for elem in elements[:3]:  # 只检查前3个
                    text = elem.get('content') or elem.get('datetime') or elem.text.strip()
                    # 检查是否像日期
                    if self._looks_like_date(text):
                        date_str = extract_date_from_text(text)
                        if date_str:
                            logger.info(f"Found date from {selector}: {date_str}")
                            return date_str

            logger.warning(f"Could not extract date from URL: {url}")
            return None  # Return None instead of empty string to distinguish from empty result

        except Exception as e:
            logger.error(f"Failed to fetch date from URL {url}: {e}")
            return None  # Return None instead of empty string

    def _normalize_iso_date(self, date_str: str) -> Optional[str]:
        """标准化 ISO 日期格式

        Args:
            date_str: 原始日期字符串

        Returns:
            Optional[str]: 标准化的 ISO 日期字符串，如果无法解析则返回 None
        """
        if not date_str:
            return None

        date_str = date_str.strip()

        # 处理格式: "2026-01-23 22:54:32 +03:00" (空格分隔)
        # 替换空格为 T 来标准化
        if ' ' in date_str and not 'T' in date_str:
            parts = date_str.split(' ')
            if len(parts) >= 2 and ':' in parts[1]:
                # 有时分秒，检查是否有时区偏移
                if len(parts) >= 3 and parts[2].startswith(('+', '-')):
                    # 格式: "2026-01-23 22:54:32 +03:00" 或 "2026-01-23 22:54:32 +03:00" (4 parts if offset has space)
                    # 合并所有剩余部分作为时区偏移
                    tz_offset = ''.join(parts[2:])
                    date_str = f"{parts[0]}T{parts[1]}{tz_offset}"
                else:
                    # 只有时分秒，无时区偏移
                    date_str = f"{parts[0]}T{parts[1]}"

        # 如果已经是 ISO 格式，直接返回
        if date_str.startswith('20') and ('T' in date_str or '-' in date_str):
            # 确保有 Z 时区
            if not date_str.endswith('Z'):
                if '+' in date_str:
                    return date_str
                date_str = date_str + 'Z'
            return date_str

        # 尝试从文本中提取日期
        extracted = extract_date_from_text(date_str)
        if extracted:
            return extracted

        return None

    def _looks_like_date(self, text: str) -> bool:
        """检查文本是否像日期

        Args:
            text: 文本内容

        Returns:
            bool: 是否像日期
        """
        if not text:
            return False

        # 检查是否包含日期相关的关键词
        date_keywords = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
                        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                        '2024', '2025', '2026']

        text_lower = text.lower()
        return any(keyword in text_lower for keyword in date_keywords)

    def _extract_date_from_content(self, content: str, title: str) -> str:
        """从内容和标题中提取日期（增强版）

        Args:
            content: 新闻内容
            title: 新闻标题

        Returns:
            str: ISO 格式的日期时间字符串，如果无法提取则返回空字符串
        """
        # 先从标题中提取（首先尝试2026年，因为是当前年份）
        date_str = extract_date_from_text(title, current_year=2026)
        if date_str:
            logger.info(f"Extracted date from title (2026): {date_str}")
            return date_str

        # 再从标题中提取（尝试2025年，以防是旧消息）
        date_str = extract_date_from_text(title, current_year=2025)
        if date_str:
            logger.info(f"Extracted date from title (2025): {date_str}")
            return date_str

        # 标题中无明确年份，从内容中提取（首先尝试2026年）
        date_str = extract_date_from_text(content[:3000], current_year=2026)
        if date_str:
            logger.info(f"Extracted date from content (2026): {date_str}")
            return date_str

        # 尝试假设2025年（旧消息）
        date_str = extract_date_from_text(content[:3000], current_year=2025)
        if date_str:
            logger.info(f"Extracted date from content (2025): {date_str}")
            return date_str

        # 最后不指定年份，让函数自动判断（搜索完整日期）
        date_str = extract_date_from_text(content[:5000])
        if date_str:
            logger.info(f"Extracted date from content (auto year): {date_str}")
            return date_str

        # 如果找不到，返回空字符串（将由调用方处理兜底）
        logger.debug(f"Could not extract date from title or content: {title[:50]}...")
        return ""

"""混合数据源客户端 - 整合多数据源

数据源优先级：
1. SEC EDGAR (官方权威)
2. Tavily (AI 优化)
3. Google News RSS (免费备份)

策略：
- 优先使用 SEC EDGAR（官方权威）
- 不足时用 Tavily 补充
- 最后用 RSS 补充
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .tavily_client import TavilySearchClient
from .rss_client import GoogleNewsRSS
from .sec_client import SECEDGARClient

logger = logging.getLogger(__name__)


class HybridDataClient:
    """混合数据源客户端

    整合多个数据源，提供统一的接口
    自动降级和容错处理
    """

    def __init__(
        self,
        tavily_client: Optional[TavilySearchClient] = None,
        rss_client: Optional[GoogleNewsRSS] = None,
        sec_client: Optional[SECEDGARClient] = None,
    ):
        """初始化混合客户端

        Args:
            tavily_client: Tavily 客户端
            rss_client: RSS 客户端
            sec_client: SEC 客户端
        """
        self.tavily = tavily_client or TavilySearchClient()
        self.rss = rss_client or GoogleNewsRSS()
        self.sec = sec_client or SECEDGARClient()

        # 数据源配置
        self.config = {
            "sec_enabled": True,
            "tavily_enabled": True,
            "rss_enabled": True,
            "sec_priority": True,  # SEC 优先
            "min_results": 3,  # 最少返回结果数
        }

    def get_latest_intelligence(
        self,
        max_results: int = 10,
        include_sec: bool = True,
    ) -> List[Dict[str, Any]]:
        """获取最新情报（多源整合）

        Args:
            max_results: 最大结果数
            include_sec: 是否包含 SEC 数据

        Returns:
            List[Dict]: 情报列表，包含 source 字段标识来源
        """
        logger.info(f"Fetching intelligence from multiple sources, max={max_results}")

        all_news = []
        source_stats = {}

        # 1. 优先从 SEC EDGAR 获取（官方权威）
        if self.config["sec_enabled"] and include_sec:
            try:
                sec_results = self._fetch_from_sec(max_results)
                all_news.extend(sec_results)
                source_stats["sec"] = len(sec_results)
                logger.info(f"SEC: {len(sec_results)} results")
            except Exception as e:
                logger.error(f"SEC failed: {e}")
                source_stats["sec"] = 0

        # 2. 如果结果不足，用 Tavily 补充
        if self.config["tavily_enabled"] and len(all_news) < max_results:
            try:
                needed = max_results - len(all_news)
                tavily_results = self._fetch_from_tavily(needed)
                all_news.extend(tavily_results)
                source_stats["tavily"] = len(tavily_results)
                logger.info(f"Tavily: {len(tavily_results)} results")
            except Exception as e:
                logger.error(f"Tavily failed: {e}")
                source_stats["tavily"] = 0

        # 3. 如果结果仍不足，用 RSS 补充
        if self.config["rss_enabled"] and len(all_news) < max_results:
            try:
                needed = max_results - len(all_news)
                rss_results = self._fetch_from_rss(needed)
                all_news.extend(rss_results)
                source_stats["rss"] = len(rss_results)
                logger.info(f"RSS: {len(rss_results)} results")
            except Exception as e:
                logger.error(f"RSS failed: {e}")
                source_stats["rss"] = 0

        # 4. 去重
        unique_news = self._deduplicate_news(all_news)

        # 5. 按时间排序
        unique_news = self._sort_by_date(unique_news)

        logger.info(f"Total: {len(unique_news)} unique news from {len(source_stats)} sources: {source_stats}")

        return unique_news[:max_results]

    def _fetch_from_tavily(self, num_results: int) -> List[Dict[str, Any]]:
        """从 Tavily 获取数据

        Args:
            num_results: 结果数量

        Returns:
            List[Dict]: 新闻列表
        """
        results = self.tavily.get_latest_intelligence(max_results=num_results)

        # 标记来源
        for item in results:
            item['data_source'] = 'tavily'

        return results

    def _fetch_from_rss(self, num_results: int) -> List[Dict[str, Any]]:
        """从 Google RSS 获取数据

        Args:
            num_results: 结果数量

        Returns:
            List[Dict]: 新闻列表
        """
        results = self.rss.get_latest_intelligence(max_results=num_results)

        # 标记来源
        for item in results:
            item['data_source'] = 'google_rss'

        return results

    def _fetch_from_sec(self, num_results: int) -> List[Dict[str, Any]]:
        """从 SEC EDGAR 获取数据

        Args:
            num_results: 结果数量

        Returns:
            List[Dict]: 文件列表
        """
        results = self.sec.get_latest_intelligence(max_results=num_results)

        # 标记来源
        for item in results:
            item['data_source'] = 'sec_edgar'

        return results

    def _deduplicate_news(self, news_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重新闻

        策略：
        - URL 相同 → 重复
        - 标题相似度 > 80% → 重复（保留优先级高的源）

        Args:
            news_list: 新闻列表

        Returns:
            List[Dict]: 去重后的列表
        """
        if not news_list:
            return []

        unique_news = []
        seen_urls = set()

        # 数据源优先级（数字越小优先级越高）
        source_priority = {
            'sec_edgar': 0,  # SEC 最权威，最优
            'tavily': 1,     # Tavily 次之
            'google_rss': 2,  # RSS 最低
        }

        for news in news_list:
            url = news.get('url', '')

            # URL 去重
            if url in seen_urls:
                continue

            # 标题相似度去重
            is_duplicate = False
            for existing in unique_news:
                if self._is_title_similar(news.get('title', ''), existing.get('title', '')):
                    # 比较数据源优先级
                    current_priority = source_priority.get(news.get('data_source', ''), 99)
                    existing_priority = source_priority.get(existing.get('data_source', ''), 99)

                    if current_priority < existing_priority:
                        # 当前新闻优先级更高，替换已存在的
                        unique_news.remove(existing)
                        unique_news.append(news)
                        seen_urls.remove(existing.get('url', ''))

                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_news.append(news)
                seen_urls.add(url)

        removed = len(news_list) - len(unique_news)
        if removed > 0:
            logger.info(f"Deduplicated {removed} duplicate news")

        return unique_news

    def _is_title_similar(self, title1: str, title2: str, threshold: float = 0.85) -> bool:
        """判断两个标题是否相似

        Args:
            title1: 标题1
            title2: 标题2
            threshold: 相似度阈值

        Returns:
            bool: 是否相似
        """
        if not title1 or not title2:
            return False

        # 简单相似度：共同单词占比
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())

        if not words1 or not words2:
            return False

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        similarity = len(intersection) / len(union)

        return similarity >= threshold

    def _sort_by_date(self, news_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按日期倒序排列（有日期的在前，无日期的在后）

        Args:
            news_list: 新闻列表

        Returns:
            List[Dict]: 排序后的列表
        """
        # 分离有日期和无日期的新闻
        has_date_items = [item for item in news_list if item.get('published_date')]
        no_date_items = [item for item in news_list if not item.get('published_date')]

        def get_timestamp(item):
            date_str = item.get('published_date', '')
            try:
                if 'T' in date_str:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                return dt.timestamp()
            except Exception as e:
                logger.warning(f"Failed to parse date '{date_str}' for item '{item.get('title', 'N/A')[:30]}...': {e}")
                return 0  # 解析失败返回最小值

        # 有日期的按时间戳倒序排列（最新的在前）
        sorted_has_date = sorted(has_date_items, key=get_timestamp, reverse=True)

        # 合并：有日期的在前（倒序）+ 无日期的在后
        return sorted_has_date + no_date_items

    def get_source_statistics(self) -> Dict[str, Any]:
        """获取数据源统计信息

        Returns:
            Dict: 统计信息
        """
        return {
            "sec_enabled": self.config["sec_enabled"],
            "tavily_enabled": self.config["tavily_enabled"],
            "rss_enabled": self.config["rss_enabled"],
            "sec_priority": self.config["sec_priority"],
        }

    def enable_source(self, source: str, enabled: bool = True):
        """启用/禁用数据源

        Args:
            source: 数据源名称 ('sec', 'tavily', 'rss')
            enabled: 是否启用
        """
        source_key = f"{source}_enabled"
        if source_key in self.config:
            self.config[source_key] = enabled
            logger.info(f"Source '{source}' {'enabled' if enabled else 'disabled'}")
        else:
            logger.warning(f"Unknown source: {source}")

"""Google News RSS 客户端 - 免费新闻数据源"""

import logging
import html
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import quote
import feedparser

logger = logging.getLogger(__name__)


class GoogleNewsRSS:
    """使用 Google News RSS 获取新闻

    优势：
    - 完全免费，无需 API Key
    - 无请求频率限制
    - Google 搜索质量高

    劣势：
    - 数据格式相对简单
    - 需要自行处理去重
    """

    def __init__(self):
        self.base_url = "https://news.google.com/rss"

    def search_soc_news(
        self,
        query: str = "Sable Offshore PHMSA pipeline restart approval",
        num_results: int = 10,
        language: str = "en",
        region: str = "US",
    ) -> List[Dict[str, Any]]:
        """搜索 SOC 相关新闻

        Args:
            query: 搜索关键词
            num_results: 返回结果数量
            language: 语言代码
            region: 地区代码

        Returns:
            List[Dict]: 新闻列表，格式与 Tavily 兼容
        """
        logger.info(f"Searching Google News RSS: {query}")

        try:
            # 构建 RSS URL（URL 编码查询参数）
            rss_url = f"{self.base_url}/search?q={quote(query)}&hl={language}&gl={region}&ceid={region}:{language}"

            # 解析 RSS
            feed = feedparser.parse(rss_url)

            if feed.bozo:
                logger.warning(f"RSS feed parsing warning: {feed.bozo_exception}")

            news_items = []
            for entry in feed.entries[:num_results]:
                # 提取发布日期
                published_date = self._parse_published_date(entry)

                # 提取摘要
                summary = self._extract_summary(entry)

                # 构建标准格式（与 Tavily 兼容）
                news_items.append({
                    "title": html.unescape(entry.title),
                    "summary": summary,
                    "url": entry.link,
                    "source": self._extract_source(entry),
                    "published_date": published_date,
                    "score": 0,  # 待 AI 评分
                })

            logger.info(f"Found {len(news_items)} news items from Google RSS")
            return news_items

        except Exception as e:
            logger.error(f"Failed to fetch Google News RSS: {e}")
            return []

    def _parse_published_date(self, entry: Any) -> str:
        """解析发布日期

        Args:
            entry: RSS entry

        Returns:
            str: ISO 格式的日期字符串
        """
        # Google RSS 的日期格式: Mon, 25 Jan 2026 17:30:00 GMT
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                dt = datetime(*entry.published_parsed[:6])
                return dt.isoformat()
            except:
                pass

        # 降级处理：直接使用原始字符串
        if hasattr(entry, 'published'):
            return entry.published

        return datetime.now().isoformat()

    def _extract_summary(self, entry: Any) -> str:
        """提取新闻摘要

        Args:
            entry: RSS entry

        Returns:
            str: 清理后的摘要文本
        """
        summary = ""

        # 尝试获取 summary
        if hasattr(entry, 'summary'):
            summary = entry.summary
        # 尝试获取 description
        elif hasattr(entry, 'description'):
            summary = entry.description

        # 清理 HTML 标签
        summary = html.unescape(summary)
        summary = re.sub(r'<[^>]+>', '', summary)

        return summary.strip()

    def _extract_source(self, entry: Any) -> str:
        """提取新闻来源

        Args:
            entry: RSS entry

        Returns:
            str: 来源名称
        """
        # Google RSS 有时会在 title 中包含来源
        # 例如: "标题 - 来源名"
        if hasattr(entry, 'title'):
            title = entry.title
            if ' - ' in title:
                parts = title.rsplit(' - ', 1)
                if len(parts) == 2 and len(parts[1]) < 50:  # 来源名通常较短
                    return parts[1].strip()

        # 尝试从 link 中提取域名
        if hasattr(entry, 'link'):
            from urllib.parse import urlparse
            parsed = urlparse(entry.link)
            return parsed.netloc.replace('www.', '')

        return "Google News"

    def get_latest_intelligence(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """获取最新情报（与 TavilyClient 接口兼容）

        Args:
            max_results: 最大结果数

        Returns:
            List[Dict]: 情报列表
        """
        # 使用默认关键词搜索
        return self.search_soc_news(num_results=max_results)

"""SOC 情报分析核心模块"""

import logging
import html
import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from .tavily_client import TavilySearchClient
from .zhipu_client import ZhipuAIClient
from .config import get_config
from .hybrid_client import HybridDataClient
from .stock_client import StockDataClient

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """标准化文本（用于相似度比较）

    Args:
        text: 原始文本

    Returns:
        str: 标准化后的文本（小写、去除标点和多余空格）
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)  # 移除标点符号
    text = re.sub(r'\s+', ' ', text)  # 合并多个空格
    return text.strip()


def calculate_similarity(text1: str, text2: str) -> float:
    """计算两个文本的相似度（0-1之间）

    Args:
        text1: 文本1
        text2: 文本2

    Returns:
        float: 相似度（0=完全不同，1=完全相同）
    """
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    if not norm1 or not norm2:
        return 0.0

    return SequenceMatcher(None, norm1, norm2).ratio()


def is_similar_card(card1: "IntelligenceCard", card2: "IntelligenceCard", threshold: float = 0.75) -> bool:
    """判断两个情报卡片是否相似

    Args:
        card1: 情报卡片1
        card2: 情报卡片2
        threshold: 相似度阈值（默认0.75，即75%相似度）

    Returns:
        bool: 如果相似则返回True
    """
    # 重要：不同维度的新闻不视为重复（联邦层/地方层/法律层）
    cat1 = getattr(card1, 'category', '') or ''
    cat2 = getattr(card2, 'category', '') or ''

    # 提取维度信息
    def get_dimension(cat):
        if '法律' in cat or 'legal' in cat.lower():
            return 'legal'
        elif '地方' in cat or 'local' in cat.lower():
            return 'local'
        elif '联邦' in cat or 'federal' in cat.lower() or 'PHMSA' in cat:
            return 'federal'
        return None

    dim1 = get_dimension(cat1)
    dim2 = get_dimension(cat2)

    # 如果两个新闻属于不同维度，不视为重复
    if dim1 and dim2 and dim1 != dim2:
        return False

    # 1. 比较标题相似度（权重更高）
    title_similarity = calculate_similarity(card1.title, card2.title)

    # 2. 比较摘要相似度
    summary_similarity = calculate_similarity(card1.summary, card2.summary)

    # 3. 综合判断：标题相似度占比60%，摘要相似度占比40%
    combined_similarity = title_similarity * 0.6 + summary_similarity * 0.4

    logger.debug(f"Similarity check: title={title_similarity:.2f}, summary={summary_similarity:.2f}, combined={combined_similarity:.2f}")

    return combined_similarity >= threshold


@dataclass
class IntelligenceCard:
    """情报卡片数据类"""
    title: str
    summary: str
    impact: str  # 一句话影响
    score: int  # 评分 -10 到 +10
    sentiment: str  # 利好/利空/中性
    key_point: str  # 关键点
    url: str
    source: str  # 新闻来源
    published_date: str
    category: str = "C"  # 分类: A(噪音), B(时间变化), C(长期逻辑冲击)
    data_source: str = "unknown"  # 数据源: tavily, google_rss, sec_edgar
    stock_impact: Optional[Dict[str, Any]] = None  # 股价影响数据

    @property
    def minutes_ago(self) -> int:
        """计算发布时间距现在的分钟数"""
        if not self.published_date:
            return 0

        try:
            date_str = self.published_date

            # 处理带有时区偏移的格式，如 "2026-01-23 22:54:32 +03:00"
            # 需要移除时区偏移部分才能被 fromisoformat 解析
            if '+' in date_str and not date_str.endswith('Z'):
                # 提取日期时间部分，忽略时区偏移
                # 格式: "2026-01-23 22:54:32 +03:00" -> "2026-01-23 22:54:32"
                date_str = date_str.split('+')[0].strip()

            pub_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            now = datetime.now(pub_time.tzinfo)
            delta = now - pub_time
            return int(delta.total_seconds() / 60)
        except Exception as e:
            logger.debug(f"Failed to calculate minutes_ago for '{self.title[:30]}...': {e}")
            return 0

    @property
    def time_label(self) -> str:
        """获取时间标签"""
        minutes = self.minutes_ago
        if minutes < 1:
            return "刚刚"
        elif minutes < 60:
            return f"{minutes} 分钟前"
        elif minutes < 1440:
            hours = minutes // 60
            return f"{hours} 小时前"
        else:
            days = minutes // 1440
            return f"{days} 天前"

    @property
    def border_color(self) -> str:
        """根据评分返回边框颜色"""
        if self.score >= 7:
            return "#00c853"  # 绿色 - 利好
        elif self.score <= 4:
            return "#ff1744"  # 红色 - 利空
        else:
            return "#ffc107"  # 黄色 - 中性

    @property
    def highlight_keywords(self, text: str) -> str:
        """高亮关键词"""
        keywords = ["PHMSA", "Approval", "Restart", "Sable"]
        for kw in keywords:
            text = text.replace(kw, f"**{kw}**")
        return text


class IntelligenceAnalyzer:
    """SOC 情报分析器"""

    def __init__(
        self,
        tavily_client: Optional[TavilySearchClient] = None,
        zhipu_client: Optional[ZhipuAIClient] = None,
        use_hybrid_source: bool = True,
        hybrid_client: Optional[HybridDataClient] = None,
        stock_client: Optional[StockDataClient] = None,
    ):
        """初始化分析器

        Args:
            tavily_client: Tavily 搜索客户端（兼容旧版）
            zhipu_client: 智谱 AI 客户端
            use_hybrid_source: 是否使用混合数据源（默认 True）
            hybrid_client: 混合数据源客户端
            stock_client: 股票数据客户端
        """
        self.config = get_config()
        self.stock = stock_client or StockDataClient(symbol="SOC")

        # 使用智谱 AI 客户端
        self.ai_client = zhipu_client or ZhipuAIClient()
        logger.info("Using Zhipu AI for analysis")

        # 数据源配置
        self.use_hybrid_source = use_hybrid_source

        if use_hybrid_source:
            # 使用混合数据源（默认）
            self.hybrid = hybrid_client or HybridDataClient(
                tavily_client=tavily_client,
            )
            self.tavily = None  # 混合模式下不单独使用 Tavily
            logger.info("IntelligenceAnalyzer initialized with Hybrid Data Source")
        else:
            # 兼容旧版：只使用 Tavily
            self.tavily = tavily_client or TavilySearchClient()
            self.hybrid = None
            logger.info("IntelligenceAnalyzer initialized with Tavily only")

    def get_intelligence_stream(
        self,
        max_results: int = 10,
        include_sec: bool = True,
    ) -> List[IntelligenceCard]:
        """获取情报流（默认获取10条，去重后显示剩余条数）

        Args:
            max_results: 最大结果数，默认3条
            include_sec: 是否包含 SEC 数据（仅混合数据源有效）

        Returns:
            List[IntelligenceCard]: 情报卡片列表
        """
        logger.info("Fetching intelligence stream...")

        # 1. 搜索情报（根据数据源选择）
        if self.use_hybrid_source:
            # 使用混合数据源
            raw_news = self.hybrid.get_latest_intelligence(
                max_results=max_results,
                include_sec=include_sec,
            )
            logger.info(f"Hybrid source returned {len(raw_news)} items")
        else:
            # 使用 Tavily（兼容旧版）
            raw_news = self.tavily.get_latest_intelligence(max_results=max_results)
            logger.info(f"Tavily source returned {len(raw_news)} items")

        if not raw_news:
            logger.warning("No intelligence found")
            return []

        # 2. 先去重原始新闻（节省 AI API 调用）
        unique_raw_news = self._deduplicate_raw_news(raw_news)
        logger.info(f"Pre-deduplication: {len(raw_news)} -> {len(unique_raw_news)} unique items")

        if not unique_raw_news:
            logger.warning("No unique intelligence after deduplication")
            return []

        # 3. AI 分析每条去重后的情报
        analyzed = []
        for news in unique_raw_news[:max_results]:
            try:
                # 调试日志：打印 Tavily 原始数据
                logger.info(f"=== TAVILY RAW DATA ===\nTitle: {news.get('title', 'N/A')}\nSummary: {news.get('summary', 'N/A')[:200]}...\n========================")

                result = self.ai_client.analyze_intelligence(news)

                # 记录日期信息用于调试
                orig_date = news.get("published_date") or ""
                ai_date = result.get("published_date") or ""
                logger.info(f"Date tracking - Original: '{orig_date}', AI: '{ai_date}'")

                card = IntelligenceCard(
                    title=html.unescape(result.get("title", "")),
                    summary=html.unescape(result.get("summary", "")),
                    impact=html.unescape(result.get("impact", "")),
                    score=result.get("score", 0),
                    sentiment=result.get("sentiment", "中性"),
                    key_point=html.unescape(result.get("key_point", "")),
                    url=result.get("url", ""),
                    source=result.get("source", ""),
                    # 优先使用原始新闻的日期，AI 可能会改变格式
                    published_date=orig_date if orig_date else ai_date,
                    category=result.get("category", "C"),  # A=噪音, B=时间变化, C=长期逻辑冲击
                    data_source=news.get("data_source", "unknown"),
                )

                # 获取股价影响数据
                try:
                    stock_impact = self.stock.get_stock_impact(
                        published_date=card.published_date,
                        sentiment=card.sentiment,
                        score=card.score
                    )
                    card.stock_impact = stock_impact
                    logger.info(f"Stock impact for {card.title[:30]}...: {stock_impact.get('change_percent')}%")
                except Exception as e:
                    logger.error(f"Failed to get stock impact: {e}")
                    card.stock_impact = None

                # 调试日志：打印最终卡片数据
                logger.info(f"=== FINAL CARD ===\nTitle: {card.title}\nCategory: {card.category}\nScore: {card.score}\nSentiment: {card.sentiment}\nImpact: {card.impact}\nKey Point: {card.key_point}\n====================")

                analyzed.append(card)
            except Exception as e:
                logger.error(f"Failed to analyze news: {e}")
                continue

        # 4. 最终去重：移除 AI 分析后仍相似的情报（提高阈值到 0.85）
        unique_cards = []
        duplicate_count = 0

        for card in analyzed:
            is_duplicate = False
            for existing_card in unique_cards:
                if is_similar_card(card, existing_card, threshold=0.85):  # 提高到 0.85
                    is_duplicate = True
                    duplicate_count += 1
                    logger.info(f"Filtered duplicate after AI: similarity with '{existing_card.title[:50]}...'")
                    break

            if not is_duplicate:
                unique_cards.append(card)

        # 4. 按发布时间倒序排列（有日期的在前，无日期的在后）
        # 分离有日期和无日期的卡片
        has_date_cards = [c for c in unique_cards if c.published_date]
        no_date_cards = [c for c in unique_cards if not c.published_date]

        # 有日期的按时间戳倒序排列（最新的在前）
        def get_timestamp(card):
            try:
                date_str = card.published_date
                if 'T' in date_str:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                return dt.timestamp()
            except Exception as e:
                logger.warning(f"Failed to parse date '{card.published_date}' for '{card.title[:30]}...': {e}")
                return 0  # 解析失败的最小值

        has_date_cards.sort(key=get_timestamp, reverse=True)

        # 合并：有日期的在前（倒序）+ 无日期的在后
        unique_cards = has_date_cards + no_date_cards

        # 记录无日期消息的数量
        if no_date_cards:
            logger.info(f"Sorted {len(has_date_cards)} cards with dates, {len(no_date_cards)} cards without dates")

        if duplicate_count > 0:
            logger.info(f"Filtered {duplicate_count} duplicate(s), {len(unique_cards)} unique cards remaining")

        # 5. 过滤中性情绪的卡片，只保留利好和利空
        before_filter_count = len(unique_cards)
        unique_cards = [card for card in unique_cards if card.sentiment in ["利好", "利空"]]
        filtered_neutral_count = before_filter_count - len(unique_cards)

        if filtered_neutral_count > 0:
            logger.info(f"Filtered {filtered_neutral_count} neutral sentiment card(s)")

        logger.info(f"Generated {len(unique_cards)} intelligence cards")
        return unique_cards

    def _deduplicate_raw_news(self, news_list: List[Dict[str, Any]], threshold: float = 0.85) -> List[Dict[str, Any]]:
        """在 AI 分析前去重原始新闻（节省 API 调用）

        策略：
        1. 按新闻事件分组（相同关键词 + 相近时间）
        2. 每个事件只保留一篇报道
        3. URL 相同 → 重复
        4. 标题相似度 > 85% → 重复
        5. 保留数据源优先级高的（SEC > Tavily > RSS）

        Args:
            news_list: 原始新闻列表
            threshold: 相似度阈值

        Returns:
            List[Dict]: 去重后的新闻列表
        """
        if not news_list:
            return []

        # 关键词列表，用于识别同一事件
        event_keywords = [
            ["PHMSA", "approval", "restart", "pipeline", "Las Flores"],
            ["PHMSA", "permit", "emergency", "Santa Ynez"],
            ["Sable", "Offshore", "SOC"],
            ["California", "sue", "lawsuit", "challenge"],
            ["court", "rule", "judge", "restart"],
        ]

        unique_news = []
        seen_urls = set()
        seen_events = set()  # 已处理的事件签名

        # 数据源优先级（数字越小优先级越高）
        source_priority = {
            'sec_edgar': 0,  # SEC 最权威，最优
            'tavily': 1,     # Tavily 次之
            'google_rss': 2,  # RSS 最低
            'unknown': 99,
        }

        for news in news_list:
            url = news.get('url', '')
            title = news.get('title', '').lower()
            summary = news.get('summary', '').lower()
            source = news.get('data_source', 'unknown')

            # URL 去重
            if url in seen_urls:
                logger.info(f"Filtered duplicate URL: {url[:50]}...")
                continue

            # 计算新闻事件签名（用于识别同一事件的不同报道）
            event_signature = self._calculate_event_signature(title, summary, event_keywords)

            # 检查是否是同一事件的不同报道
            is_duplicate = False

            if event_signature in seen_events:
                # 同一事件，跳过
                logger.info(f"Filtered same event: '{event_signature}'")
                is_duplicate = True
            else:
                # 标题相似度去重（作为补充）
                for existing in unique_news:
                    existing_title = existing.get('title', '')
                    title_sim = calculate_similarity(title, existing_title)

                    if title_sim >= threshold:
                        logger.info(f"Filtered duplicate by title similarity: '{title[:40]}...' (similarity: {title_sim:.2f})")
                        is_duplicate = True
                        break

            if not is_duplicate:
                unique_news.append(news)
                seen_urls.add(url)
                seen_events.add(event_signature)

        removed = len(news_list) - len(unique_news)
        if removed > 0:
            logger.info(f"Pre-deduplication: filtered {removed} duplicate(s), {len(unique_news)} unique items remain")

        return unique_news

    def _calculate_event_signature(self, title: str, summary: str, event_keywords: list) -> str:
        """计算新闻事件签名

        通过匹配关键词组合来识别同一事件

        Args:
            title: 标题
            summary: 摘要
            event_keywords: 事件关键词列表

        Returns:
            str: 事件签名
        """
        text = f"{title} {summary}".lower()

        # 核心事件检测（使用多种表达方式）
        event_patterns = [
            # PHMSA 批准事件
            {
                "name": "PHMSA批准",
                "indicators": ["phmsa", "approval", "approve", "green light", "go-ahead", "ok", "gets"]
            },
            # 管道重启事件
            {
                "name": "管道重启",
                "indicators": ["pipeline", "restart", "resumes", "reopening", "operation"]
            },
            # 诉讼事件
            {
                "name": "诉讼",
                "indicators": ["sue", "sues", "lawsuit", "challenge", "challenging", "against", "attorney"]
            },
            # 法院裁决事件
            {
                "name": "法院裁决",
                "indicators": ["court", "judge", "ruling", "rules", "judicial"]
            },
            # 股价波动事件
            {
                "name": "股价",
                "indicators": ["stock", "shares", "surge", "tumble", "jump", "fall", "rise"]
            },
        ]

        matched_events = []
        has_phmsa_approval = False

        # 检查每个事件模式
        for pattern in event_patterns:
            match_count = sum(1 for indicator in pattern["indicators"] if indicator in text)
            # 至少匹配 2 个指标才算该事件
            if match_count >= 2:
                matched_events.append(pattern["name"])
                if pattern["name"] == "PHMSA批准":
                    has_phmsa_approval = True

        # 如果是PHMSA批准事件，生成独特签名（基于标题前30字符）避免被过滤
        if has_phmsa_approval:
            # 使用标题前30个字符的哈希值确保唯一性
            title_hash = hash(title[:30]) % 10000
            return f"PHMSA批准_{title_hash}"

        # 事件签名：所有匹配的事件组合
        if matched_events:
            return "+".join(sorted(set(matched_events)))

        # 降级：使用原始关键词匹配
        matched_keywords = []
        for keyword_group in event_keywords:
            match_count = sum(1 for kw in keyword_group if kw.lower() in text)
            if match_count >= 3:
                matched_keywords.extend(keyword_group)

        if matched_keywords:
            return "|".join(sorted(set(matched_keywords)))

        # 最后降级：使用标题的第一个关键短语
        words = [w for w in text.split() if len(w) > 3]  # 只保留长度 > 3 的词
        if words:
            return words[0]

        return "unknown"

    def get_breaking_news(
        self,
        threshold: int = 9,
        cards: Optional[List[IntelligenceCard]] = None,
    ) -> Optional[IntelligenceCard]:
        """获取突发新闻（高评分情报）

        Args:
            threshold: 评分阈值
            cards: 已获取的情报卡片列表（避免重复调用API）

        Returns:
            Optional[IntelligenceCard]: 突发新闻卡片，如果没有则返回 None
        """
        if cards is None:
            cards = self.get_intelligence_stream()

        for card in cards:
            if abs(card.score) >= threshold:
                return card

        return None

    def format_summary_for_display(
        self,
        card: IntelligenceCard,
    ) -> str:
        """格式化摘要用于显示（高亮关键词）

        Args:
            card: 情报卡片

        Returns:
            str: 格式化后的摘要
        """
        keywords = ["PHMSA", "Approval", "Restart", "Sable"]
        summary = card.summary

        for kw in keywords:
            summary = summary.replace(kw, f"**{kw}**")

        return summary

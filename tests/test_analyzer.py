"""SOC 实时情报系统 - 测试用例

测试范围：
1. 情报卡片去重功能
2. 时间排序功能
3. 情报过滤功能
4. 数据源集成测试
"""

import pytest
from datetime import datetime, timedelta
from src.analyzer import (
    IntelligenceCard,
    IntelligenceAnalyzer,
    calculate_similarity,
    is_similar_card,
)


class TestIntelligenceCard:
    """测试 IntelligenceCard 数据类"""

    def test_create_card(self):
        """测试创建情报卡片"""
        card = IntelligenceCard(
            title="PHMSA approves Sable pipeline restart",
            summary="Federal regulator approved the restart plan",
            impact="巩固联邦层批准",
            score=7,
            sentiment="利好",
            key_point="PHMSA批准",
            url="https://example.com/news/1",
            source="example.com",
            published_date="2025-12-23T10:00:00Z",
            category="联邦层",
        )

        assert card.title == "PHMSA approves Sable pipeline restart"
        assert card.score == 7
        assert card.sentiment == "利好"

    def test_minutes_ago(self):
        """测试时间计算"""
        # 创建 1 小时前的卡片
        pub_date = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        card = IntelligenceCard(
            title="Test",
            summary="Test",
            impact="Test",
            score=5,
            sentiment="中性",
            key_point="Test",
            url="https://example.com",
            source="example.com",
            published_date=pub_date,
        )

        assert 55 <= card.minutes_ago <= 65  # 允许一些误差


class TestSimilarity:
    """测试相似度计算"""

    def test_identical_text(self):
        """测试完全相同的文本"""
        sim = calculate_similarity("PHMSA approves pipeline", "PHMSA approves pipeline")
        assert sim == 1.0

    def test_similar_text(self):
        """测试相似的文本"""
        sim = calculate_similarity(
            "PHMSA approves Sable pipeline restart",
            "PHMSA approved Sable pipeline restart plan"
        )
        assert sim > 0.7

    def test_different_text(self):
        """测试不同的文本"""
        sim = calculate_similarity(
            "PHMSA approves pipeline",
            "Stock market surges today"
        )
        assert sim < 0.3

    def test_empty_text(self):
        """测试空文本"""
        sim = calculate_similarity("", "")
        assert sim == 0.0


class TestDeduplication:
    """测试去重功能"""

    def test_identical_cards(self):
        """测试完全相同的卡片"""
        card1 = IntelligenceCard(
            title="PHMSA approves pipeline",
            summary="Federal approval granted",
            impact="利好",
            score=7,
            sentiment="利好",
            key_point="PHMSA",
            url="https://example.com/1",
            source="example.com",
            published_date="2025-12-23T10:00:00Z",
            category="联邦层",
        )

        card2 = IntelligenceCard(
            title="PHMSA approves pipeline",
            summary="Federal approval granted",
            impact="利好",
            score=7,
            sentiment="利好",
            key_point="PHMSA",
            url="https://example.com/1",
            source="example.com",
            published_date="2025-12-23T10:00:00Z",
            category="联邦层",
        )

        assert is_similar_card(card1, card2, threshold=0.85)

    def test_similar_but_different_dimension(self):
        """测试相似但不同维度的卡片（不应视为重复）"""
        card1 = IntelligenceCard(
            title="PHMSA approves pipeline restart",
            summary="Federal approval",
            impact="联邦层批准",
            score=7,
            sentiment="利好",
            key_point="PHMSA",
            url="https://example.com/1",
            source="example.com",
            published_date="2025-12-23T10:00:00Z",
            category="联邦层",
        )

        card2 = IntelligenceCard(
            title="Court blocks pipeline restart",
            summary="Legal challenge",
            impact="法律层阻碍",
            score=-7,
            sentiment="利空",
            key_point="诉讼",
            url="https://example.com/2",
            source="example.com",
            published_date="2025-12-23T10:00:00Z",
            category="法律层",
        )

        # 不同维度不应视为重复
        assert not is_similar_card(card1, card2, threshold=0.85)

    def test_different_cards(self):
        """测试不同的卡片"""
        card1 = IntelligenceCard(
            title="PHMSA approves pipeline",
            summary="Federal approval",
            impact="利好",
            score=7,
            sentiment="利好",
            key_point="PHMSA",
            url="https://example.com/1",
            source="example.com",
            published_date="2025-12-23T10:00:00Z",
            category="联邦层",
        )

        card2 = IntelligenceCard(
            title="Stock market rallies",
            summary="Market surge",
            impact="利好",
            score=5,
            sentiment="利好",
            key_point="股市",
            url="https://example.com/2",
            source="example.com",
            published_date="2025-12-23T10:00:00Z",
            category="联邦层",
        )

        assert not is_similar_card(card1, card2, threshold=0.85)


class TestSorting:
    """测试排序功能"""

    def test_sort_by_date_descending(self):
        """测试按日期倒序排列"""
        cards = [
            IntelligenceCard(
                title="Card 1",
                summary="Summary 1",
                impact="Impact 1",
                score=5,
                sentiment="中性",
                key_point="Key 1",
                url="https://example.com/1",
                source="example.com",
                published_date="2025-12-20T10:00:00Z",
            ),
            IntelligenceCard(
                title="Card 2",
                summary="Summary 2",
                impact="Impact 2",
                score=7,
                sentiment="利好",
                key_point="Key 2",
                url="https://example.com/2",
                source="example.com",
                published_date="2025-12-23T10:00:00Z",  # 最新
            ),
            IntelligenceCard(
                title="Card 3",
                summary="Summary 3",
                impact="Impact 3",
                score=3,
                sentiment="利空",
                key_point="Key 3",
                url="https://example.com/3",
                source="example.com",
                published_date="2025-12-22T10:00:00Z",
            ),
        ]

        analyzer = IntelligenceAnalyzer()
        sorted_cards = analyzer._sort_cards_by_date(cards)

        # 验证顺序：最新在前
        assert sorted_cards[0].published_date == "2025-12-23T10:00:00Z"
        assert sorted_cards[1].published_date == "2025-12-22T10:00:00Z"
        assert sorted_cards[2].published_date == "2025-12-20T10:00:00Z"

    def test_sort_with_undated_cards(self):
        """测试包含无日期卡片的排序"""
        cards = [
            IntelligenceCard(
                title="Card 1",
                summary="Summary 1",
                impact="Impact 1",
                score=5,
                sentiment="中性",
                key_point="Key 1",
                url="https://example.com/1",
                source="example.com",
                published_date="2025-12-20T10:00:00Z",
            ),
            IntelligenceCard(
                title="Card 2",
                summary="Summary 2",
                impact="Impact 2",
                score=7,
                sentiment="利好",
                key_point="Key 2",
                url="https://example.com/2",
                source="example.com",
                published_date="",  # 无日期
            ),
            IntelligenceCard(
                title="Card 3",
                summary="Summary 3",
                impact="Impact 3",
                score=3,
                sentiment="利空",
                key_point="Key 3",
                url="https://example.com/3",
                source="example.com",
                published_date="2025-12-23T10:00:00Z",  # 最新
            ),
        ]

        analyzer = IntelligenceAnalyzer()
        sorted_cards = analyzer._sort_cards_by_date(cards)

        # 有日期的在前（按倒序），无日期的在后
        assert sorted_cards[0].published_date == "2025-12-23T10:00:00Z"
        assert sorted_cards[1].published_date == "2025-12-20T10:00:00Z"
        assert sorted_cards[2].published_date == ""


class TestDisplayLimit:
    """测试显示数量限制"""

    def test_display_latest_5_cards(self):
        """测试只显示最新 5 条消息"""
        # 创建 10 张卡片
        cards = []
        for i in range(10):
            card = IntelligenceCard(
                title=f"Card {i}",
                summary=f"Summary {i}",
                impact=f"Impact {i}",
                score=5,
                sentiment="中性",
                key_point=f"Key {i}",
                url=f"https://example.com/{i}",
                source="example.com",
                published_date=f"2025-12-{20+i:02d}T10:00:00Z",
            )
            cards.append(card)

        analyzer = IntelligenceAnalyzer()
        sorted_cards = analyzer._sort_cards_by_date(cards)

        # 只返回前 5 张
        latest_5 = sorted_cards[:5]
        assert len(latest_5) == 5
        # 验证是最新的 5 张
        assert latest_5[0].title == "Card 9"
        assert latest_5[4].title == "Card 5"


class TestCausalChainStatus:
    """测试三维因果链状态"""

    def test_all_supporting(self):
        """测试全部支持状态"""
        cards = [
            IntelligenceCard(
                title="Federal approval",
                summary="PHMSA approved",
                impact="联邦层支持",
                score=8,
                sentiment="利好",
                key_point="PHMSA",
                url="https://example.com/1",
                source="example.com",
                published_date="2025-12-23T10:00:00Z",
                category="联邦层",
            ),
            IntelligenceCard(
                title="Local permit granted",
                summary="County approved",
                impact="地方层支持",
                score=7,
                sentiment="利好",
                key_point="许可",
                url="https://example.com/2",
                source="example.com",
                published_date="2025-12-22T10:00:00Z",
                category="地方层",
            ),
            IntelligenceCard(
                title="Court denies injunction",
                summary="Legal challenge failed",
                impact="法律层无阻碍",
                score=6,
                sentiment="利好",
                key_point="法院",
                url="https://example.com/3",
                source="example.com",
                published_date="2025-12-21T10:00:00Z",
                category="法律层",
            ),
        ]

        # 期望全部为支持状态
        federal_support = sum(1 for c in cards if "联邦" in c.category and c.score > 3)
        local_support = sum(1 for c in cards if "地方" in c.category and c.score > 3)
        legal_support = sum(1 for c in cards if "法律" in c.category and c.score > 3)

        assert federal_support == 1
        assert local_support == 1
        assert legal_support == 1


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

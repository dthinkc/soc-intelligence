"""测试 AI 日期提取"""

import sys
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.zhipu_client import ZhipuAIClient

def main():
    print("=" * 60)
    print("测试 AI 日期提取")
    print("=" * 60)

    client = ZhipuAIClient()

    # 测试新闻（没有日期的那条）
    test_news = {
        "title": "Sable Offshore says PHMSA approves Las Flores pipeline restart plan",
        "summary": "Sable Offshore Corp announced that the Pipeline and Hazardous Materials Safety Administration (PHMSA) has approved the restart plan for the Las Flores pipeline system. The company stated that this approval is a significant milestone towards resuming operations.",
        "url": "https://example.com/news",
        "source": "Example",
        "published_date": "",  # 原始日期为空
    }

    print("\n测试新闻:")
    print(f"标题: {test_news['title']}")
    print(f"摘要: {test_news['summary'][:100]}...")
    print(f"原始日期: {test_news['published_date'] or '(空)'}")

    # 清空缓存
    ZhipuAIClient.clear_cache()

    # 分析
    print("\n正在分析...")
    result = client.analyze_intelligence(test_news)

    ai_date = result.get('published_date', '(空)')
    print(f"\nAI 提取的日期: {ai_date}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()

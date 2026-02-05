"""检查 Tavily 原始数据"""

import sys
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.tavily_client import TavilySearchClient

def main():
    print("=" * 60)
    print("检查 Tavily 原始数据")
    print("=" * 60)

    client = TavilySearchClient()

    # 获取情报
    print("\n正在获取情报...")
    results = client.search_intelligence(max_results=5)

    print(f"\n获取到 {len(results)} 条情报")

    for i, item in enumerate(results, 1):
        print(f"\n{'=' * 60}")
        print(f"[{i}] {item.get('title', 'N/A')[:60]}...")
        print(f"    URL: {item.get('url', 'N/A')[:60]}...")
        print(f"    原始日期: {item.get('published_date', 'N/A')}")
        print(f"    摘要: {item.get('summary', 'N/A')[:150]}...")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()

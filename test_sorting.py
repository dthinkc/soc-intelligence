"""测试数据获取和排序逻辑"""

import sys
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.analyzer import IntelligenceAnalyzer
from datetime import datetime

def main():
    print("=" * 60)
    print("测试数据获取和排序")
    print("=" * 60)

    analyzer = IntelligenceAnalyzer()

    # 获取情报
    print("\n1. 正在获取情报...")
    cards = analyzer.get_intelligence_stream(max_results=10)

    print(f"\n2. 获取到 {len(cards)} 条情报")

    # 打印每条情报的时间
    print("\n3. 情报列表（按当前顺序）:")
    print("-" * 60)
    for i, card in enumerate(cards, 1):
        print(f"\n[{i}] {card.title[:50]}...")
        print(f"    日期: {card.published_date}")
        print(f"    来源: {card.data_source}")

        # 解析时间戳
        if card.published_date:
            try:
                date_str = card.published_date
                if 'T' in date_str:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                print(f"    时间戳: {dt.timestamp()}")
                print(f"    解析后: {dt}")
            except Exception as e:
                print(f"    解析错误: {e}")
        else:
            print(f"    时间戳: None (无日期)")

    # 检查排序是否正确
    print("\n4. 检查排序:")
    print("-" * 60)

    # 提取所有有日期的卡片的时间戳
    timestamps = []
    for card in cards:
        if card.published_date:
            try:
                date_str = card.published_date
                if 'T' in date_str:
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                timestamps.append((card.title[:40], dt.timestamp(), dt))
            except Exception as e:
                print(f"解析错误: {card.title[:40]}: {e}")

    # 检查是否是降序排列
    is_descending = all(timestamps[i][1] >= timestamps[i+1][1] for i in range(len(timestamps)-1))

    print(f"\n有日期的情报数量: {len(timestamps)}")
    print(f"是否按时间降序排列: {is_descending}")

    if not is_descending and len(timestamps) > 1:
        print("\n⚠️ 发现排序问题！时间戳不是降序排列：")
        for title, ts, dt in timestamps:
            print(f"  {dt} | {ts} | {title}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()

"""测试日期时间处理"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_date_parsing():
    """测试各种日期格式的解析"""

    test_dates = [
        "2025-12-23T11:33:40.000Z",
        "2025-12-23T20:00:02+00:00",
        "2026-02-04T20:50:51-05:00",
        "2026-01-02T12:11:07.000Z",
        "2025-12-22T00:00:00Z",
    ]

    print("=" * 60)
    print("测试日期时间解析")
    print("=" * 60)

    for date_str in test_dates:
        print(f"\n原始: {date_str}")

        # 解析日期
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            print(f"解析后: {dt}")
            print(f"ISO格式: {dt.isoformat()}")

            # 转换为 UTC（如果有时区偏移）
            if dt.tzinfo is not None:
                dt_utc = dt.astimezone(timezone.utc)
                print(f"UTC时间: {dt_utc}")

            # 格式化为输出格式
            formatted = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            print(f"输出格式: {formatted}")

            # 检查时间是否被保留
            if dt.hour == 0 and dt.minute == 0:
                print("⚠️ 只有日期，无具体时间")
            else:
                print(f"✓ 有具体时间: {dt.hour:02d}:{dt.minute:02d}")

        except Exception as e:
            print(f"❌ 解析失败: {e}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_date_parsing()

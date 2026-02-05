"""SOC 实时情报系统 - Followin 风格"""

import os
import sys
import logging
import time
import re
import html
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import streamlit as st

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import get_config
from src.analyzer import IntelligenceAnalyzer, IntelligenceCard

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 页面配置 - 无侧边栏全屏布局
st.set_page_config(
    page_title="SOC 实时情报",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 自定义 CSS - Followin 浅色风格
st.markdown("""
<style>
    /* 隐藏侧边栏 */
    [data-testid="stSidebar"] {
        display: none;
    }

    /* 页面背景 - 响应式设计 */
    .main .block-container {
        background: #F8F9FA;
        padding: 1rem 1.5rem;
        width: 100%;
        max-width: 1200px;  /* 桌面端最大宽度 */
        margin: 0 auto;     /* 居中显示 */
    }

    /* 移动端优化 */
    @media (max-width: 768px) {
        .main .block-container {
            padding: 0.75rem 1rem;
            max-width: 100%;
        }
    }

    /* 顶部导航栏 */
    .header-nav {
        position: sticky;
        top: 0;
        background: #FFFFFF;
        padding: 1rem 1.5rem;
        z-index: 999;
        border-bottom: 1px solid #E5E7EB;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }

    .header-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #111827;
    }

    .header-meta {
        font-size: 0.85rem;
        color: #6B7280;
    }

    /* 突发情报横幅 */
    .breaking-banner {
        background: linear-gradient(90deg, #10B981, #059669);
        padding: 0.8rem 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }

    /* 加载动画 */
    .loading-container {
        text-align: center;
        padding: 3rem;
        background: #FFFFFF;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """初始化会话状态"""
    if "intelligence_cards" not in st.session_state:
        st.session_state.intelligence_cards = []

    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = None

    if "breaking_news" not in st.session_state:
        st.session_state.breaking_news = None

    if "refresh_interval" not in st.session_state:
        st.session_state.refresh_interval = 300  # 5分钟

    # 跟踪是否正在获取数据（防止并行请求重复调用）
    if "is_fetching" not in st.session_state:
        st.session_state.is_fetching = False

    # 跟踪是否已经自动加载过数据
    if "has_auto_loaded" not in st.session_state:
        st.session_state.has_auto_loaded = False


def render_header():
    """渲染顶部导航栏 - Followin 风格"""
    st.markdown("""
    <div class="header-nav">
        <div class="header-title">📡 SOC 实时情报</div>
        <div class="header-meta">
            <span>PHMSA 审批追踪</span>
            <span style="margin: 0 10px;">|</span>
            <span id="last-update">实时更新</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_causal_chain_status():
    """渲染三维因果链整体状态 - 低调说明样式"""
    logger.info(f"render_causal_chain_status() called, cards: {len(st.session_state.intelligence_cards)}")

    if not st.session_state.intelligence_cards:
        logger.info("No cards, returning early")
        return

    # 分析三个维度的整体状态 - 每条消息只归类到主要维度
    federal_status = {"support": 0, "oppose": 0}
    local_status = {"support": 0, "oppose": 0}
    legal_status = {"support": 0, "oppose": 0}

    for card in st.session_state.intelligence_cards:
        impact = card.impact or ""
        score = card.score or 0
        category = card.category if hasattr(card, 'category') else ""

        logger.info(f"Card: {card.title[:30]}... score={score}, category={category}")

        # 优先使用AI返回的category字段
        dimension = None
        if "法律" in category:
            dimension = "legal"
        elif "地方" in category or "圣巴巴拉" in category:
            dimension = "local"
        elif "联邦" in category or "PHMSA" in category:
            dimension = "federal"
        else:
            # category不明确时，用impact中的明确表述判断
            if "涉及法律层" in impact or "法律层断裂" in impact:
                dimension = "legal"
            elif "涉及地方层" in impact or "地方层断裂" in impact:
                dimension = "local"
            elif "涉及联邦层" in impact or "联邦层断裂" in impact:
                dimension = "federal"
            else:
                # 最后才用关键词匹配，扩大匹配范围
                if any(kw in impact for kw in ["法院", "禁令", "诉讼", "起诉", "法律层", "lawsuit", "sues", "suing", "litigation", "court"]):
                    dimension = "legal"
                elif any(kw in impact for kw in ["地方", "圣巴巴拉", "County", "Local", "local", "郡政府", " county"]):
                    dimension = "local"
                elif any(kw in impact for kw in ["PHMSA", "联邦", "federal", "Federal", " Pipeline", "管道批准", "federal approval"]):
                    dimension = "federal"

        # 根据维度统计
        if dimension == "legal":
            if score > 3:
                legal_status["support"] += 1
                logger.info(f"  -> 法律层支持+1")
            elif score < -3:
                legal_status["oppose"] += 1
                logger.info(f"  -> 法律层阻碍+1")
        elif dimension == "local":
            if score > 3:
                local_status["support"] += 1
                logger.info(f"  -> 地方层支持+1")
            elif score < -3:
                local_status["oppose"] += 1
                logger.info(f"  -> 地方层阻碍+1")
        elif dimension == "federal":
            if score > 3:
                federal_status["support"] += 1
                logger.info(f"  -> 联邦层支持+1")
            elif score < -3:
                federal_status["oppose"] += 1
                logger.info(f"  -> 联邦层阻碍+1")
        else:
            logger.info(f"  -> 未匹配到任何维度")

    # 获取状态信息
    def get_status_info(status_dict):
        if status_dict["support"] > status_dict["oppose"]:
            return "✅ 支持"
        elif status_dict["oppose"] > status_dict["support"]:
            return "⚠️ 阻碍"
        else:
            return "⏳ 观察中"

    fed_status = get_status_info(federal_status)
    local_status_text = get_status_info(local_status)
    legal_status_text = get_status_info(legal_status)

    # 低调的说明样式
    st.markdown("""
    <div style="
        background: #F3F4F6;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-bottom: 1rem;
        border-left: 3px solid #6B7280;
    ">
        <div style="font-size: 0.7rem; color: #6B7280; margin-bottom: 0.35rem;">三维因果链整体状态</div>
        <div style="display: flex; gap: 1.5rem; font-size: 0.8rem; color: #374151;">
            <span><strong>联邦层(PHMSA):</strong> {fed_status}</span>
            <span><strong>地方层:</strong> {local_status_text}</span>
            <span><strong>法律层:</strong> {legal_status_text}</span>
        </div>
        <div style="font-size: 0.65rem; color: #9CA3AF; margin-top: 0.35rem;">
            PHMSA 批准 + 地方许可 + 法律通关 = 现金流恢复
        </div>
    </div>
    """.format(
        fed_status=fed_status,
        local_status_text=local_status_text,
        legal_status_text=legal_status_text
    ), unsafe_allow_html=True)


def render_breaking_news(breaking_card: Optional[IntelligenceCard]):
    """渲染突发情报横幅 - Followin 风格"""
    if breaking_card:
        sentiment_emoji = "🚀" if breaking_card.score > 0 else "⚠️"
        st.markdown(f"""
        <div class="breaking-banner">
            <div style="display: flex; align-items: center; gap: 1rem; color: #fff;">
                <span style="font-size: 1.5rem;">🚨</span>
                <div>
                    <div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 0.2rem;">
                        特发情报 | {breaking_card.sentiment}
                    </div>
                    <div style="font-size: 0.85rem; opacity: 0.95;">
                        {breaking_card.impact}
                    </div>
                </div>
                <a href="{breaking_card.url}" target="_blank" style="color: #fff; margin-left: auto; text-decoration: none; font-size: 0.85rem; font-weight: 500;">
                    查看详情 →
                </a>
            </div>
        </div>
        """, unsafe_allow_html=True)


def strip_html_tags(text: str) -> str:
    """清理 HTML 标签，只保留纯文本

    Args:
        text: 可能包含 HTML 标签的文本

    Returns:
        str: 清理后的纯文本
    """
    # 解转义 HTML 实体
    text = html.unescape(text)
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    return text


def highlight_keywords(text: str) -> str:
    """高亮关键词（在纯文本上进行）

    Args:
        text: 纯文本内容

    Returns:
        str: 带高亮标记的 HTML
    """
    # 先清理 HTML 标签
    text = strip_html_tags(text)

    keywords = ["PHMSA", "Approval", "Restart", "Sable"]
    for kw in keywords:
        text = text.replace(kw, f'<span class="keyword">{kw}</span>')
    return text


def safe_html(text) -> str:
    """确保文本安全用于 HTML 渲染

    Args:
        text: 原始文本（可以是 str、dict 等）

    Returns:
        str: 安全的 HTML 文本
    """
    # 处理非字符串类型
    if not isinstance(text, str):
        if isinstance(text, dict):
            # 尝试从字典中提取内容
            if "message_summary" in text and "impact_analysis" in text:
                summary = text.get("message_summary", "")
                analysis = text.get("impact_analysis", "")
                text = f"消息总结：{summary}\n\n影响分析：{analysis}"
            else:
                text = str(text)
        else:
            text = str(text)

    # 先解转义，再清理 HTML 标签
    text = html.unescape(text)
    text = strip_html_tags(text)
    return text


def render_intelligence_card(card: IntelligenceCard):
    """渲染单条情报卡片 - Followin 浅色风格"""
    # 确定情绪样式 - Followin 配色
    # 特别利好标识（评分 >= 9）
    is_breaking = card.score >= 9

    if card.score >= 7:
        # 利好 - 绿色
        sentiment_bg = "#10B981"
        sentiment_text = "利多"
        sentiment_emoji = "🚀"
        sentiment_text_color = "#fff"
        impact_border = "#10B981"
        star_color = "#10B981"
    elif card.score <= 4:
        # 利空 - 红色
        sentiment_bg = "#EF4444"
        sentiment_text = "利空"
        sentiment_emoji = "⚠️"
        sentiment_text_color = "#fff"
        impact_border = "#EF4444"
        star_color = "#EF4444"
    else:
        # 中性 - 灰色
        sentiment_bg = "#F3F4F6"
        sentiment_text = "中性"
        sentiment_emoji = "➡️"
        sentiment_text_color = "#6B7280"
        impact_border = "#6B7280"
        star_color = "#6B7280"

    # 计算星级（1-5星）
    score_abs = abs(card.score)
    stars = min(5, max(1, round(score_abs / 2)))  # 将 -10~+10 转换为 1~5 星

    # 格式化发布时间 - Followin 风格: MM-DD HH:MM
    if not card.published_date or card.published_date == "":
        time_display = "时间未知"
    else:
        try:
            pub_time = datetime.fromisoformat(card.published_date.replace("Z", "+00:00"))
            time_display = pub_time.strftime("%m-%d %H:%M")
        except:
            time_display = card.published_date[:16] if len(card.published_date) > 16 else card.published_date

    # 清理所有文本字段（HTML 安全）
    impact = safe_html(card.impact)

    # 生成星级显示 - 实心星 + 空心星
    star_display = "⭐" * stars + "☆" * (5 - stars)

    # 构建 HTML（直接拼接，不用 f-string 避免转义问题）
    html_parts = []

    # 卡片容器 - Followin 白色卡片风格
    html_parts.append('<div style="')
    html_parts.append('    background: #FFFFFF;')
    html_parts.append('    border-radius: 8px;')
    html_parts.append('    padding: 1rem 1rem 0.8rem 1rem;')
    html_parts.append('    margin-bottom: 1rem;')
    html_parts.append('    box-shadow: 0 1px 3px rgba(0,0,0,0.1);')
    html_parts.append('    border-left: 3px solid ' + impact_border + ';')
    html_parts.append('">')

    # 1. 顶部：情绪标签（左）+ 时间戳（右）
    html_parts.append('    <div style="')
    html_parts.append('        display: flex;')
    html_parts.append('        justify-content: space-between;')
    html_parts.append('        align-items: center;')
    html_parts.append('        margin-bottom: 0.8rem;')
    html_parts.append('    ">')

    # 左侧：特别利好标识 + 情绪标签（组合）
    html_parts.append('        <div style="')
    html_parts.append('            display: flex;')
    html_parts.append('            align-items: center;')
    html_parts.append('            gap: 0.5rem;')
    html_parts.append('        "\">')

    # 特别利好标识（仅评分 >= 9 时显示）
    if is_breaking:
        html_parts.append('            <div style="')
        html_parts.append('                background: linear-gradient(135deg, #F59E0B, #EF4444);')
        html_parts.append('                color: #fff;')
        html_parts.append('                padding: 0.25rem 0.6rem;')
        html_parts.append('                border-radius: 6px;')
        html_parts.append('                font-size: 11px;')
        html_parts.append('                font-weight: 700;')
        html_parts.append('                display: inline-flex;')
        html_parts.append('                align-items: center;')
        html_parts.append('                gap: 0.2rem;')
        html_parts.append('            ">&#128293; 特别利好</div>')

    # 情绪标签
    html_parts.append('            <div style="')
    html_parts.append('                background: ' + sentiment_bg + ';')
    html_parts.append('                color: ' + sentiment_text_color + ';')
    html_parts.append('                padding: 0.25rem 0.75rem;')
    html_parts.append('                border-radius: 6px;')
    html_parts.append('                font-size: 12px;')
    html_parts.append('                font-weight: 600;')
    html_parts.append('                display: inline-flex;')
    html_parts.append('                align-items: center;')
    html_parts.append('                gap: 0.25rem;')
    html_parts.append('        ">' + sentiment_emoji + ' ' + sentiment_text + '</div>')

    html_parts.append('        </div>')

    # 右侧：时间戳
    html_parts.append('        <div style="')
    html_parts.append('            color: #6B7280;')
    html_parts.append('            font-size: 12px;')
    html_parts.append('            font-weight: 500;')
    html_parts.append('        ">' + time_display + '</div>')

    html_parts.append('    </div>')

    # 2. 中间：智能解读区域（主要内容）
    html_parts.append('    <div style="')
    html_parts.append('        background: #F9FAFB;')
    html_parts.append('        border-radius: 8px;')
    html_parts.append('        padding: 0.8rem 1rem;')
    html_parts.append('        margin-bottom: 1rem;')
    html_parts.append('    ">')

    # 智能解读内容（单段显示）
    html_parts.append('        <div style="')
    html_parts.append('            color: #111827;')
    html_parts.append('            font-size: 13px;')
    html_parts.append('            line-height: 1.7;')
    html_parts.append('        ">' + impact + '</div>')

    html_parts.append('    </div>')

    # 3. 底部：影响程度评分 + 股价反应 + 消息链接
    html_parts.append('    <div style="')
    html_parts.append('        display: flex;')
    html_parts.append('        justify-content: space-between;')
    html_parts.append('        align-items: center;')
    html_parts.append('        padding-top: 0.6rem;')
    html_parts.append('        border-top: 1px solid #F3F4F6;')
    html_parts.append('        gap: 1rem;')
    html_parts.append('    ">')

    # 左侧：影响程度评分
    html_parts.append('        <div style="')
    html_parts.append('            display: flex;')
    html_parts.append('            align-items: center;')
    html_parts.append('            gap: 0.4rem;')
    html_parts.append('        ">')
    html_parts.append('            <span style="color: #6B7280; font-size: 12px;">影响程度：</span>')
    html_parts.append('            <span style="color: ' + star_color + '; font-size: 14px;">' + star_display + '</span>')
    html_parts.append('            <span style="color: ' + star_color + '; font-weight: 600; font-size: 12px;">(' + str(card.score) + ')</span>')
    html_parts.append('        </div>')

    # 中间：股价反应（如果有数据）
    if card.stock_impact and card.stock_impact.get('available'):
        stock = card.stock_impact
        change = stock.get('change', 0)
        change_percent = stock.get('change_percent', 0)
        price_before = stock.get('price_before')
        price_after = stock.get('price_after')

        if price_before and price_after:
            # 确定涨跌颜色
            if change_percent > 0:
                price_color = "#10B981"  # 绿色 - 上涨
                arrow = "📈"
            elif change_percent < 0:
                price_color = "#EF4444"  # 红色 - 下跌
                arrow = "📉"
            else:
                price_color = "#6B7280"  # 灰色 - 平盘
                arrow = "➡️"

            html_parts.append('        <div style="')
            html_parts.append('            display: flex;')
            html_parts.append('            align-items: center;')
            html_parts.append('            gap: 0.5rem;')
            html_parts.append('            background: #F3F4F6;')
            html_parts.append('            padding: 0.3rem 0.75rem;')
            html_parts.append('            border-radius: 6px;')
            html_parts.append('        ">')
            html_parts.append('            <span style="color: #6B7280; font-size: 11px;">股价：</span>')
            html_parts.append('            <span style="color: ' + price_color + '; font-size: 13px; font-weight: 600;">')
            html_parts.append('                ' + arrow + ' ' + ("+" if change_percent > 0 else "") + str(change_percent) + '%')
            html_parts.append('            </span>')
            html_parts.append('        </div>')

    # 右侧：消息链接
    html_parts.append('        <a href="' + card.url + '" target="_blank" style="')
    html_parts.append('            color: #6B7280;')
    html_parts.append('            text-decoration: none;')
    html_parts.append('            font-size: 12px;')
    html_parts.append('            display: flex;')
    html_parts.append('            align-items: center;')
    html_parts.append('            gap: 0.25rem;')
    html_parts.append('            white-space: nowrap;')
    html_parts.append('        ">')
    html_parts.append('            📎 消息来源 →')
    html_parts.append('        </a>')

    html_parts.append('    </div>')

    html_parts.append('</div>')

    html_content = '\n'.join(html_parts)

    # 使用 st.markdown 渲染
    st.markdown(html_content, unsafe_allow_html=True)


def render_intelligence_stream():
    """渲染情报流 - 直接显示所有获取的情报"""
    # 渲染情报卡片
    if not st.session_state.intelligence_cards:
        st.info("📭 暂无情报，请等待系统自动刷新...")
    else:
        # 直接显示所有情报（每次只获取3条）
        for card in st.session_state.intelligence_cards:
            render_intelligence_card(card)

        # 显示统计信息
        st.caption(f"📊 共 {len(st.session_state.intelligence_cards)} 条情报（每次最多显示5条，每5分钟自动更新）")


def fetch_intelligence():
    """获取最新情报（使用 session_state 锁防止重复调用）"""
    # 如果正在获取中，直接返回
    if st.session_state.is_fetching:
        logger.info("Already fetching, skipping...")
        return

    try:
        st.session_state.is_fetching = True
        logger.info("Starting fetch_intelligence()...")

        with st.spinner("正在获取最新情报..."):
            analyzer = IntelligenceAnalyzer()
            logger.info("Calling get_intelligence_stream()...")
            cards = analyzer.get_intelligence_stream(max_results=10)  # 增加到10条以确保过滤后有5条
            logger.info(f"get_intelligence_stream() returned {len(cards)} cards")

        logger.info("Updating session_state...")
        # 只显示前 5 条情报（去重后）
        st.session_state.intelligence_cards = cards[:5]
        # 使用 UTC 时间戳，避免时区问题
        st.session_state.last_refresh = datetime.now(timezone.utc)
        logger.info(f"Session state updated: {len(st.session_state.intelligence_cards)} cards, last_refresh={st.session_state.last_refresh}")

        st.success(f"✅ 已更新 {len(cards[:5])} 条情报（共获取 {len(cards)} 条，已去重）")

        logger.info("fetch_intelligence() completed successfully")

    except Exception as e:
        st.error(f"❌ 获取情报失败: {e}")
        logger.error(f"Failed to fetch intelligence: {e}", exc_info=True)
    finally:
        st.session_state.is_fetching = False
        logger.info("is_fetching flag cleared")


def render_auto_refresh():
    """刷新控制区域"""
    col1, col2 = st.columns([1, 2])

    with col1:
        if st.button("🔄 刷新情报"):
            fetch_intelligence()
            # 刷新页面以显示更新后的数据
            try:
                st.rerun()
            except AttributeError:
                st.experimental_rerun()

    with col2:
        if st.session_state.last_refresh:
            # 确保使用 UTC 时间计算差异
            now_utc = datetime.now(timezone.utc)
            # 处理可能无时区信息的历史数据
            last_refresh = st.session_state.last_refresh
            if last_refresh.tzinfo is None:
                # 如果是无时区的 datetime，假设它是 UTC
                last_refresh = last_refresh.replace(tzinfo=timezone.utc)

            time_since = (now_utc - last_refresh).total_seconds()

            # 防止显示负数或异常大的值
            if time_since < 0:
                time_since = 0

            if time_since < 60:
                st.caption(f"⏱️ {int(time_since)} 秒前更新")
            else:
                minutes = int(time_since // 60)
                if minutes < 60:
                    st.caption(f"⏱️ {minutes} 分钟前更新")
                else:
                    hours = minutes // 60
                    st.caption(f"⏱️ {hours} 小时前更新")
        else:
            st.caption("⏱️ 等待更新...")


def main():
    """主函数"""
    init_session_state()

    # 首次加载时自动获取数据（在渲染任何UI之前）
    if not st.session_state.has_auto_loaded:
        logger.info("First load - fetching intelligence automatically...")
        fetch_intelligence()
        st.session_state.has_auto_loaded = True
        # 刷新页面以显示数据
        try:
            st.rerun()
        except AttributeError:
            st.experimental_rerun()
        return  # 退出，等待 rerun

    # 渲染顶部导航
    render_header()

    # 渲染三维因果链状态
    render_causal_chain_status()

    # 渲染情报流
    render_intelligence_stream()

    # 渲染刷新控制
    render_auto_refresh()

    # 如果没有数据，显示提示
    if not st.session_state.intelligence_cards:
        st.info("👆 点击上方「刷新情报」按钮获取最新数据")


if __name__ == "__main__":
    main()

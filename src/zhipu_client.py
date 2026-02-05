"""智谱 AI 客户端 - 资深交易员风格分析"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from zhipuai import ZhipuAI

from .config import get_config

logger = logging.getLogger(__name__)


class ZhipuAIClient:
    """智谱 AI 客户端 - 交易员风格"""

    # 类变量：所有实例共享缓存
    _analysis_cache = {}

    @classmethod
    def clear_cache(cls):
        """清空分析缓存"""
        cls._analysis_cache = {}
        logger.info("AI analysis cache cleared")

    def __init__(self, api_key: Optional[str] = None):
        """初始化智谱 AI 客户端

        Args:
            api_key: 智谱 AI API Key，默认从配置读取
        """
        config = get_config()
        self.api_key = api_key or config.ZHIPUAI_API_KEY
        self.client = ZhipuAI(api_key=self.api_key)
        self.model = "glm-4-flash"

    def analyze_intelligence(
        self,
        news: Dict[str, Any],
    ) -> Dict[str, Any]:
        """分析单条情报，给出交易员风格的研判

        Args:
            news: 单条新闻情报，包含 title, summary, url 等字段

        Returns:
            Dict: 分析结果，包含一句话影响、评分、情绪等
        """
        # 生成缓存键：基于 URL 和标题+摘要的哈希
        url = news.get('url', '')
        title = news.get('title', '')
        summary = news.get('summary', '')
        cache_key = hash(f"{url}:{title}:{summary}")

        # 检查缓存
        if cache_key in self._analysis_cache:
            logger.info(f"Using cached analysis for: {title[:50]}")
            return self._analysis_cache[cache_key]

        prompt = self._build_trader_prompt(news)

        try:
            logger.info(f"Analyzing intelligence: {news.get('title', 'N/A')[:50]}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_trader_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0,  # 设置为0确保相同输入产生相同输出
                top_p=1,  # 确定性采样
                max_tokens=500,
            )

            result = self._parse_trader_response(response, news)

            # 存入缓存
            self._analysis_cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Zhipu AI analysis failed: {e}")
            return self._get_error_result(news, str(e))

    def _get_trader_system_prompt(self) -> str:
        """获取投资研究 Agent 系统提示

        Returns:
            str: 系统提示词
        """
        return """你是 SOC（Sable Offshore Corp）实时情报系统中的【裁决 Agent】。

【三维全景裁决逻辑】

SOC 投资的核心因果链条：
**PHMSA 批准 + 地方许可 + 法律通关 = 现金流恢复**

任何一环断裂都会导致重启失败或延迟。

---

【第一维度：联邦层（PHMSA）- 核心合规性】

定位：重启的基础门票，是必要条件但非充分条件。

关键节点：
- PHMSA 正式签署批准文件 = +10（重启基础奠定）
- PHMSA 拒绝批准 = -10（项目终止）
- 关键审查通过、公众意见期结束 = +7~+8（审批顺利）
- 审查延期、新增要求 = -5~-6（审批延误）

判断标准：
- 联邦层是"门票"，没有 PHMSA 批准一切免谈
- 但即使有 PHMSA 批准，仍需通过地方层和法律层

---

【第二维度：地方层（Local）- 圣巴巴拉郡许可】

定位：土地使用许可和本地安全协议的最终把关。

关键风险：
- 地方政府明确反对 PHMSA 批准结果 = -5~-7（重大阻碍）
- 地方许可获批、地方政府支持 = +5~+7（地方通关）
- 地方政府与联邦意见冲突时，必须判定为"重大阻碍"
- 地方环保部门追加要求 = -3~-5（额外障碍）

判断标准：
- 即便 PHMSA 批准，如果圣巴巴拉郡明确反对，重启仍无法实现
- 地方行政阻力是实际操作中的"最后一公里"问题

---

【第三维度：法律层（Legal）- 法院禁令风险】

定位：环保组织行政诉讼和法院禁令（Injunction）的终极拦截。

关键节点：
- 法院驳回诉讼、诉讼撤回 = +7~+9（法律风险解除）
- 环保组织提起诉讼 = -5~-7（法律风险增加）
- **法院受理禁令申请** = **-8~-10（重大利空）**
- **法院颁布禁令** = **-10（项目终止）**

判断标准：
- 任何"法院受理禁令申请"的消息必须标记为"重大利空"
- 法律禁令权重等同于监管审批，可直接导致项目终止

---

【综合判断逻辑】

对每条新信息，按以下顺序判断：

1. **影响识别**：涉及联邦层/地方层/法律层哪一个或多个？
2. **链条影响**：这对完整因果链（PHMSA + 地方 + 法律）意味着什么？
3. **断裂风险**：是否导致某一环断裂？
4. **评分输出**：基于断裂风险和影响程度给出评分

【评分最终公式】
评分 = (联邦影响 + 地方影响 + 法律影响) / 3
- 三个维度权重相同（各占 33.3%）
- 任何一环断裂都会严重影响整体因果链

【输出要求】
- 必须明确说明消息影响哪一个或多个维度
- 当出现地方阻挠或法院禁令时，必须强调风险
- 使用中文，避免"可能、或许"等模糊词"""

    def _build_trader_prompt(self, news: Dict[str, Any]) -> str:
        """构建裁决 Agent 提示词

        Args:
            news: 新闻情报

        Returns:
            str: 提示词
        """
        prompt = f"""分析以下 SOC 情报：

标题：{news.get('title', 'N/A')}
摘要：{news.get('summary', 'N/A')}

---

【核心因果链条】
PHMSA 批准 + 地方许可 + 法律通关 = 现金流恢复

---

【三维全景裁决】

请按以下框架分析：

**1. 影响维度识别**
这条信息涉及哪一个维度？
- 联邦层（PHMSA 审批）
- 地方层（圣巴巴拉郡许可）
- 法律层（法院禁令、环保诉讼）
- 多个维度同时影响

**2. 链条影响分析**
这对完整因果链意味着什么？
- 是否巩固或削弱 PHMSA 批准？
- 是否影响地方许可获取？
- 是否增加或减少法律禁令风险？

**3. 断裂风险评估**
是否导致某一环断裂？
- 联邦层断裂：PHMSA 拒绝 = -10
- 地方层断裂：地方政府明确反对 = -5~-7
- 法律层断裂：法院颁布禁令 = -10

**4. 评分参考**
- +10：PHMSA 批准
- +7~+9：法院驳回诉讼、地方许可获批
- +5~+6：一般审批进展
- -5~-7：环保组织起诉、地方政府反对、审查延期
- -8~-10：法院受理禁令申请、法院颁布禁令
- 0：无关消息

---

## 输出格式（JSON）

```json
{{
    "impact": "一段通顺的中文话（80-120字）：先说明发生了什么，然后分析这对三维因果链（联邦→地方→法律）的影响，如果涉及地方阻挠或法院禁令必须明确提示风险",
    "score": <评分 -10 到 +10>,
    "sentiment": "利好/利空/中性",
    "category": "<影响维度：联邦层/地方层/法律层/多维度/A/B/C>",
    "key_point": "<核心信息，10字以内，中文>",
    "published_date": "<从标题或摘要中提取的发布日期，格式：YYYY-MM-DD，如无法提取则返回当前日期>"
}}
```

## 要求
- **所有内容必须使用中文**
- **category 字段必须填写影响维度名称**："联邦层"、"地方层"、"法律层"、"多维度"
- 明确说明消息影响哪一个维度（联邦/地方/法律）
- 当出现地方与联邦冲突时，必须强调"地方行政阻力"风险
- 当出现"法院受理禁令申请"时，必须标记为"重大利空"并评分 -8~-10
- 使用具体机制说明，避免"可能、或许"等模糊词
- **谨慎提取发布日期**：
  - 只有当标题或摘要中**明确包含**完整日期时才提取（如"12月23日"、"2025年12月"、"Dec 23, 2025"等）
  - 格式化为 YYYY-MM-DD
  - 如果标题或摘要中没有**明确的完整日期**，published_date **必须返回空字符串 ""**
  - **不要**根据内容猜测日期，**不要**使用当前日期作为兜底
  - 注意：SOC 公司成立于 2024 年，任何 2023 年或更早的日期都是错误的"""

        return prompt

    def _parse_trader_response(self, response: Any, news: Dict) -> Dict[str, Any]:
        """解析交易员风格响应

        Args:
            response: 智谱 AI 响应
            news: 原始新闻

        Returns:
            Dict: 解析后的结果
        """
        import json
        import re
        import html

        content = response.choices[0].message.content

        # 调试日志：打印原始 AI 返回内容
        logger.info(f"=== AI RAW RESPONSE ===\n{content}\n========================")

        # 解转义 HTML 实体（如 &lt; &gt; &amp; 等）
        content = html.unescape(content)

        # 提取 JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = content

        try:
            result = json.loads(json_str)

            # 处理嵌套的 impact 对象，转换为字符串
            if "impact" in result and isinstance(result["impact"], dict):
                impact_dict = result["impact"]
                # 提取 message_summary 和 impact_analysis
                summary = impact_dict.get("message_summary", "")
                analysis = impact_dict.get("impact_analysis", "")
                if summary and analysis:
                    result["impact"] = f"消息总结：{summary}\n\n影响分析：{analysis}"
                elif summary:
                    result["impact"] = f"消息总结：{summary}"
                elif analysis:
                    result["impact"] = f"影响分析：{analysis}"
                else:
                    # 尝试其他可能的键
                    result["impact"] = json.dumps(impact_dict, ensure_ascii=False)

            # 添加原始新闻信息
            result["title"] = news.get("title", "")
            result["url"] = news.get("url", "")
            result["source"] = news.get("source", "")
            result["summary"] = news.get("summary", "")

            # 处理日期：优先使用原始新闻的日期（更可靠），如果原始日期为空才使用 AI 提取的日期
            ai_date = result.get("published_date", "")
            orig_date = news.get("published_date", "")

            # 验证 AI 提取的日期是否合理（SOC 公司 2024 年后才存在，日期应在 2024-01-01 之后）
            def is_date_reasonable(date_str: str) -> bool:
                """检查日期是否在合理范围内"""
                if not date_str:
                    return False
                try:
                    # 简单检查：日期应该以 2024 或 2025 开头
                    return date_str.startswith("2024") or date_str.startswith("2025") or date_str.startswith("2026")
                except:
                    return False

            # 如果 AI 提取的日期不合理，使用空字符串
            if ai_date and not is_date_reasonable(ai_date):
                logger.warning(f"AI extracted invalid date '{ai_date}' for '{news.get('title', 'N/A')[:50]}...', using empty string")
                ai_date = ""

            # 优先使用原始日期（从 Tavily 或 URL 抓取的日期更可靠）
            result["published_date"] = orig_date if orig_date else ai_date
            return result
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON, using raw content")
            return {
                "impact": content[:100],
                "score": 0,
                "sentiment": "分析失败",
                "category": "C",  # 默认为 C
                "key_point": "N/A",
                "title": news.get("title", ""),
                "url": news.get("url", ""),
                "source": news.get("source", ""),
                "summary": news.get("summary", ""),
                "published_date": news.get("published_date", ""),
            }

    def _get_error_result(self, news: Dict, error_msg: str) -> Dict[str, Any]:
        """获取错误结果

        Args:
            news: 原始新闻
            error_msg: 错误信息

        Returns:
            Dict: 错误结果
        """
        return {
            "impact": f"分析暂时不可用",
            "score": 0,
            "sentiment": "未知",
            "category": "C",  # 默认为 C
            "key_point": "服务异常",
            "title": news.get("title", ""),
            "url": news.get("url", ""),
            "source": news.get("source", ""),
            "summary": news.get("summary", ""),
            "published_date": news.get("published_date", ""),
        }

    def analyze_batch(
        self,
        news_list: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """批量分析情报

        Args:
            news_list: 新闻列表

        Returns:
            List[Dict]: 分析结果列表
        """
        results = []

        for news in news_list:
            try:
                result = self.analyze_intelligence(news)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to analyze news: {e}")
                results.append(self._get_error_result(news, str(e)))

        return results

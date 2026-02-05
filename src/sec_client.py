"""SEC EDGAR API 客户端 - 官方公司数据源

SEC EDGAR 提供美国上市公司的官方文件，包括：
- 10-K: 年度报告
- 10-Q: 季度报告
- 8-K: 当前报告
- 6-K: 外国公司报告
"""

import logging
import html
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import requests

logger = logging.getLogger(__name__)


class SECEDGARClient:
    """SEC EDGAR 官方 API 客户端

    优势：
    - 官方数据，权威可信
    - 完全免费，无需 API Key
    - 提供公司财报/公告原始数据

    注意：
    - 需要提供 User-Agent（SEC 要求）
    - 有请求频率限制（10次/秒）
    """

    # Sable Offshore Corp. 的 CIK (Central Index Key)
    # 可以通过 https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=SABLE 查询
    SABLE_CIK = "0001962178"

    def __init__(self, user_agent: str = None):
        """初始化客户端

        Args:
            user_agent: SEC 要求提供 User-Agent，格式：邮箱或公司名
        """
        self.base_url = "https://data.sec.gov"

        # SEC 要求提供 User-Agent
        if user_agent is None:
            user_agent = "investment-research-tool@example.com"
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        }

    def get_company_filings(
        self,
        cik: str = None,
        form_types: List[str] = None,
        days_back: int = 90,
    ) -> List[Dict[str, Any]]:
        """获取公司最新文件

        Args:
            cik: 公司 CIK 号，默认使用 Sable
            form_types: 文件类型列表，如 ['10-K', '10-Q', '8-K', '6-K']
            days_back: 获取最近 N 天的文件

        Returns:
            List[Dict]: 文件列表，格式与其他客户端兼容
        """
        if cik is None:
            cik = self.SABLE_CIK

        if form_types is None:
            # 默认获取主要文件类型
            form_types = ['10-K', '10-Q', '8-K', '6-K', 'S-1', '424B2']

        logger.info(f"Fetching SEC filings for CIK {cik}, forms: {form_types}")

        try:
            # 获取公司提交文件索引
            url = f"{self.base_url}/submissions/CIK{cik}.json"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            recent_filings = data['filings']['recent']

            # 解析文件
            filings = []
            cutoff_date = datetime.now() - timedelta(days=days_back)

            for i in range(len(recent_filings['form'])):
                form_type = recent_filings['form'][i]

                # 只返回指定类型的文件
                if form_type not in form_types:
                    continue

                # 检查日期
                filing_date_str = recent_filings['filingDate'][i]
                try:
                    filing_date = datetime.fromisoformat(filing_date_str)
                    if filing_date < cutoff_date:
                        continue
                except:
                    pass

                # 提取文件信息
                accession_number = recent_filings['accessionNumber'][i]
                accession_clean = accession_number.replace('-', '')

                filing = {
                    "title": f"Sable {form_type} Filing",
                    "summary": self._generate_filing_summary(recent_filings, i),
                    "url": self._build_filing_url(cik, accession_clean),
                    "source": "SEC EDGAR",
                    "published_date": filing_date_str,
                    "form_type": form_type,
                    "filing_date": filing_date_str,
                    "accession": accession_number,
                    "score": 0,  # 待 AI 评分
                }

                filings.append(filing)

            logger.info(f"Found {len(filings)} SEC filings")
            return filings

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch SEC filings: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching SEC filings: {e}")
            return []

    def _generate_filing_summary(self, filings: Dict, index: int) -> str:
        """生成文件摘要

        Args:
            filings: SEC 文件数据
            index: 索引

        Returns:
            str: 摘要文本
        """
        form_type = filings['form'][index]

        # 获取文件描述
        if 'act' in filings and len(filings['act']) > index:
            act = filings['act'][index]
            if act and act != '':
                return f"{form_type}: {act}"

        # 获取主要业务
        if 'primaryDoc' in filings and len(filings['primaryDoc']) > index:
            primary_doc = filings['primaryDoc'][index]
            return f"{form_type}: {primary_doc}"

        return f"{form_type} filing - SEC official document"

    def _build_filing_url(self, cik: str, accession: str) -> str:
        """构建文件详情页 URL

        Args:
            cik: 公司 CIK
            accession: 清理后的 accession 号

        Returns:
            str: 文件 URL
        """
        # SEC 文档页面
        return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{cik}-{accession}-index.htm"

    def search_filings_by_keyword(
        self,
        keyword: str = "PHMSA",
        cik: str = None,
        days_back: int = 365,
    ) -> List[Dict[str, Any]]:
        """搜索包含特定关键词的文件

        Args:
            keyword: 搜索关键词
            cik: 公司 CIK
            days_back: 搜索最近 N 天

        Returns:
            List[Dict]: 匹配的文件列表
        """
        logger.info(f"Searching SEC filings for keyword: {keyword}")

        # 获取所有文件
        all_filings = self.get_company_filings(cik=cik, days_back=days_back)

        # 过滤包含关键词的文件
        # 注意：这里只检查文件元数据，实际内容需要进一步爬取
        matching_filings = []
        keyword_lower = keyword.lower()

        for filing in all_filings:
            title_lower = filing['title'].lower()
            summary_lower = filing['summary'].lower()

            if keyword_lower in title_lower or keyword_lower in summary_lower:
                matching_filings.append(filing)

        logger.info(f"Found {len(matching_filings)} filings matching '{keyword}'")
        return matching_filings

    def get_latest_intelligence(self, max_results: int = 5) -> List[Dict[str, Any]]:
        """获取最新情报（与其他客户端接口兼容）

        优先返回：
        1. 8-K（当前报告，最及时）
        2. 6-K（外国公司报告）
        3. 10-Q（季度报告）
        4. 10-K（年度报告）

        Args:
            max_results: 最大结果数

        Returns:
            List[Dict]: 情报列表
        """
        # 按优先级排序的文件类型
        priority_forms = ['8-K', '6-K', '10-Q', '10-K', 'S-1', '424B2']

        filings = self.get_company_filings(form_types=priority_forms, days_back=180)

        # 按文件类型优先级排序
        def form_priority(filing):
            form = filing.get('form_type', '')
            try:
                return priority_forms.index(form)
            except ValueError:
                return len(priority_forms)

        filings.sort(key=form_priority)

        return filings[:max_results]

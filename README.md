# SOC 投资分析系统

基于 PHMSA 审批研判的智能投研工具，实时追踪 Sable Offshore Corp. (SOC) 的投资情报。

## 功能特点

- 实时情报聚合（SEC EDGAR + Tavily + Google News）
- AI 驱动的影响分析（智谱 GLM）
- 三维因果链状态追踪（联邦层/地方层/法律层，权重各占 33.3%）
- 股价反应模拟

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Keys
```

### 3. 启动应用

```bash
streamlit run app.py
```

应用将在 http://localhost:8501 启动

## 技术栈

- **Streamlit**: Web 应用框架
- **智谱 AI**: GLM 大语言模型
- **SEC EDGAR**: 官方权威数据源（最优优先级）
- **Tavily**: 实时网络搜索（次优）
- **Google News RSS**: 新闻源（最低优先级）

## 项目结构

```
soc-investment-system/
├── app.py                 # Streamlit 主应用
├── requirements.txt       # Python 依赖
├── .streamlit/
│   └── config.toml        # Streamlit 配置
└── src/
    ├── config.py          # 配置管理
    ├── sec_client.py      # SEC 数据源（官方最优）
    ├── tavily_client.py   # Tavily 搜索（次优）
    ├── rss_client.py      # RSS 数据源（最低）
    ├── analyzer.py        # 投资分析逻辑
    ├── zhipu_client.py    # 智谱 AI 封装
    ├── stock_client.py    # 股票数据
    └── hybrid_client.py   # 混合数据源
```

## API Keys 配置

| 变量名 | 获取地址 |
|--------|----------|
| `TAVILY_API_KEY` | https://app.tavily.com |
| `ZHIPUAI_API_KEY` | https://open.bigmodel.cn/usercenter/apikeys |

## Streamlit Cloud 部署

1. 访问 [streamlit.io/cloud](https://streamlit.io/cloud)
2. 点击 "New app"
3. 连接 GitHub 仓库
4. 配置环境变量
5. 点击 "Deploy"

## 注意事项

- `.env` 文件包含敏感信息，不会被提交到 Git
- Tavily API 有速率限制
- 部署时在 Secrets 中配置环境变量

## License

MIT

# Claude 项目操作指南

## 项目概述
SOC 实时情报系统 - 基于 PHMSA 审批研判的智能投研工具

## 技术栈
- **Streamlit**: Web 应用框架
- **SEC EDGAR**: 官方权威数据源（最优优先级）
- **Tavily**: 实时网络搜索 API（次优）
- **智谱 AI (Zhipu AI)**: GLM 大语言模型
- **Python**: 3.10+

## 代码风格

### 命名约定
```python
# 文件名: 小写下划线 (e.g., investment_analyzer.py)
# 类名: 大驼峰 (e.g., TavilySearchClient)
# 函数名: 小写下划线 (e.g., fetch_phmsa_data)
# 常量: 全大写下划线 (e.g., API_TIMEOUT)
```

### 代码结构
```python
# 标准文件模板
"""模块描述"""

import os
from typing import Optional

# 常量定义
CONSTANT_VALUE = "value"

# 类定义
class ClassName:
    """类描述"""

    def __init__(self):
        pass

# 函数定义
def function_name(param: str) -> dict:
    """函数描述

    Args:
        param: 参数说明

    Returns:
        返回值说明
    """
    pass

# 主程序入口
if __name__ == "__main__":
    pass
```

### 类型注解
- 所有函数必须使用类型注解
- 使用 `typing` 模块中的类型

## 核心准则

### 1. 环境配置
- 敏感信息使用 `.env` 文件管理
- API Key 通过环境变量获取
- `.env` 文件不提交到版本控制

### 2. 错误处理
```python
# 标准错误处理模式
try:
    result = api_call()
except APIError as e:
    st.error(f"API 调用失败: {e}")
    return None
```

### 3. 日志规范
```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("操作成功")
logger.error(f"操作失败: {error}")
```

### 4. Streamlit 最佳实践
- 使用 `st.cache_data` 缓存数据
- 使用 `st.spinner` 显示加载状态
- 合理使用 `st.columns` 布局
- 图表使用 `st.plotly_chart` 或 `st.line_chart`

### 5. 开发规范（重要）

#### 5.1 修改前先更新文档
**每次修改代码前，必须先更新以下文档**：
1. `PRD.md` - 产品需求文档（如有需求变更）
2. `CHANGELOG.md` - 更新日志（记录每次修改）
3. `CLAUDE.md` - 本文件（如有架构变更）

#### 5.2 文档更新检查清单
- [ ] PRD.md - 需求是否变更？
- [ ] CHANGELOG.md - 是否添加了新条目？
- [ ] CLAUDE.md - 是否需要更新架构说明？
- [ ] 是否需要添加/更新测试用例？

#### 5.3 代码修改流程
```
1. 更新文档 (PRD/CHANGELOG/CLAUDE.md)
   ↓
2. 编写/更新测试用例
   ↓
3. 修改代码
   ↓
4. 运行测试验证
   ↓
5. 更新 requirements.txt (如有新依赖)
```

## 项目结构
```
.
├── PRD.md                 # 产品需求文档
├── CLAUDE.md              # 本文件 - 项目操作指南
├── CHANGELOG.md           # 更新日志
├── requirements.txt       # Python 依赖
├── .env                   # 环境变量 (不提交)
├── .env.example           # 环境变量模板
├── app.py                 # Streamlit 主应用
├── src/
│   ├── __init__.py
│   ├── config.py          # 配置管理
│   ├── sec_client.py      # SEC 文件获取客户端（官方最优优先级）
│   ├── tavily_client.py   # Tavily API 封装（次优）
│   ├── rss_client.py      # RSS 订阅源客户端（最低优先级）
│   ├── zhipu_client.py    # 智谱 AI API 封装
│   ├── hybrid_client.py   # 混合数据源客户端
│   ├── stock_client.py    # 股票数据客户端
│   └── analyzer.py        # 投资分析逻辑
└── tests/
    ├── test_analyzer.py
    └── test_clients.py
```

## 常用命令

### 依赖管理
```bash
# 安装依赖
pip install -r requirements.txt

# 添加新依赖
pip install package-name
pip freeze > requirements.txt
```

### 运行应用
```bash
# 启动 Streamlit
streamlit run app.py

# 指定端口
streamlit run app.py --server.port 8501
```

### 代码检查
```bash
# 代码格式化
black .

# 类型检查
mypy .

# 运行测试
pytest tests/
```

## API 配置

### Tavily
- 官网: https://tavily.com
- 获取 API Key: https://app.tavily.com

### 智谱 AI
- 官网: https://open.bigmodel.cn
- 获取 API Key: https://open.bigmodel.cn/usercenter/apikeys

## 开发工作流

### 功能开发流程
1. **需求分析**
   - 阅读 PRD.md 了解当前需求
   - 与用户确认需求细节

2. **文档更新**
   - 更新 PRD.md（如有需求变更）
   - 在 CHANGELOG.md 添加新条目
   - 更新 CLAUDE.md（如有架构变更）

3. **测试用例**
   - 编写/更新测试用例
   - 确保测试覆盖新功能

4. **代码实现**
   - 遵循代码风格规范
   - 添加类型注解
   - 添加日志记录

5. **测试验证**
   - 运行测试用例
   - 手动测试新功能
   - 检查日志输出

6. **部署**
   - 更新 requirements.txt（如有新依赖）
   - 测试 Streamlit 应用
   - 提交代码和文档

### 代码审查
- 自查代码风格
- 运行测试确保通过
- 检查文档是否同步更新

## 注意事项
1. **API 调用注意速率限制**
2. **搜索结果需要去重**
3. **AI 生成内容需要标注来源**
4. **定期更新依赖版本**
5. **修改代码前必须先更新文档**

## 常见问题

### Q: 为什么修改代码前要先更新文档？
A: 文档是项目的"记忆"。如果不先更新文档，下次修改时会遗忘之前的决策和背景，导致重复工作或不一致。

### Q: CHANGELOG.md 应该记录什么？
A: 记录所有功能变更、bug 修复、配置变更等，格式：
```markdown
## [日期] - [版本]

### 新增
- 功能描述

### 修复
- Bug 描述

### 变更
- 变更描述
```

### Q: 什么时候需要写测试用例？
A: 所有核心功能、复杂逻辑、公共函数都需要测试用例。

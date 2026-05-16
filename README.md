# Buffett Stock Dashboard

巴菲特价值投资理念的个人股票筛选与分析工具，支持 A 股 + 美股 + 港股。

## 功能特性

- **选股**：基于 DCF 现金流折现、ROIC、护城河评分的综合筛选
- **追踪**：持仓组合实时监控，支持贵州茅台、苹果等主流股票
- **决策信号**：价值低估/高估提示，结合巴菲特骨灰级评分体系
- **数据来源**：yfinance（美股）+ akshare（A 股/港股）

## 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite
- **前端**：React 18（createElement）+ Babel inline
- **数据**：免费 API，无付费数据源依赖

## 快速启动

```bash
# 安装依赖
pip install fastapi uvicorn akshare yfinance sqlalchemy aiosqlite

# 启动后端（端口 5000）
cd D:/buffett-dashboard
uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload

# 打开浏览器
start chrome http://localhost:5000
```

## 项目结构

```
buffett-dashboard/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── database.py           # SQLAlchemy 配置
│   ├── scheduler.py         # 定时刷新任务
│   ├── api/
│   │   └── stocks.py        # 股票 API 路由
│   ├── data/
│   │   ├── yfinance_client.py  # 美股数据
│   │   └── akshare_client.py   # A 股/港股数据
│   ├── models/
│   │   ├── stock.py         # Stock 模型
│   │   └── daily_metric.py  # DailyMetric 模型
│   └── services/
│       ├── dcf_engine.py    # DCF 现金流折现引擎
│       └── scoring.py       # 评分系统
└── frontend/
    └── index.html           # React 单页应用
```

## 评分体系

| 指标 | 说明 |
|------|------|
| ROIC | 资本回报率，>15% 为优秀 |
| DCF | 三阶段现金流折现估值 |
| 护城河 | 5 维度规则评分 + AI 辅助 |
| 综合评分 | ROIC×0.4 + 护城河×0.3 + 成长性×0.2 + 估值×0.1 |

## License

MIT

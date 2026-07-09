<p align="center">
  <h1 align="center">🏆 WorldCup Agent Predictor</h1>
  <p align="center">
    <strong>Agent-native 世界杯冠军预测系统</strong><br/>
    Qwen 作为决策核心 · 自主调用工具链 · 逐场推理 · 可解释输出
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-2.0.0-blue" alt="version">
  <img src="https://img.shields.io/badge/python-3.11+-green" alt="python">
  <img src="https://img.shields.io/badge/React-19-61dafb" alt="react">
  <img src="https://img.shields.io/badge/TypeScript-6.0-3178c6" alt="typescript">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="license">
</p>

---

## 项目简介

WorldCup Agent Predictor 是一个 **Agent-native** 的 2026 世界杯冠军预测系统。与传统的"Python 模型计算 + LLM 写文案"不同，本系统将 **Qwen (通义千问) 作为决策核心**，Python 统计模型降级为 Agent 的工具箱。

Qwen 自主决定调用哪些工具（ELO 评分、历史交锋、泊松模型、伤病事件等），综合多维度数据做出独立判断，输出包含完整推理链的结构化预测。

> 本项目参与 **阿里云天池 · Qoder 码力星期四 · 世界杯挑战赛**。

## 核心设计理念

```
传统架构                          Agent-native 架构 (本项目)
┌──────────────────┐           ┌──────────────────────────┐
│ Python 模型做决策  │           │ Qwen Agent 做决策         │
│       ↓           │           │      ↓                   │
│ LLM 润色文案      │           │ 自主调用 Python 工具获取数据│
│                  │           │      ↓                   │
│ AI = 翻译官       │           │ 综合多维度自主分析          │
└──────────────────┘           │      ↓                   │
                                │ 输出结构化预测 + 完整推理链  │
                                │                          │
                                │ Python = 工具箱           │
                                └──────────────────────────┘
```

**三层容错防线**：Function Calling 格式约束 → Pydantic 输出校验 → CircuitBreaker 降级到泊松统计模型，确保 API 故障不破坏用户体验。

**双通道事件注入**：静态基线（ELO / FIFA / 泊松）与动态事件（伤病、换帅、战术调整）并存，Qwen 动态解释事件权重，而非依赖固定公式。

## 技术栈

| 层级 | 技术 |
|------|------|
| **后端框架** | FastAPI + Uvicorn (异步) |
| **数据库** | SQLite + SQLAlchemy 2.0 (异步) |
| **数据处理** | Pandas + NumPy + SciPy |
| **Agent 决策** | Qwen Max (阿里云 DashScope Function Calling) |
| **容错** | Tenacity 重试 + CircuitBreaker 熔断 |
| **前端** | React 19 + TypeScript 6 + Vite 8 |
| **样式** | TailwindCSS 4 + Framer Motion 12 |
| **图表** | Recharts 2 |
| **状态管理** | TanStack Query 5 |
| **部署** | Docker + Nginx (目标阿里云 ECS) |

## 项目结构

```
WorldCup-Agent-Qoder/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config.py                # 配置管理 (环境变量)
│   │   ├── models/                  # 数据库模型
│   │   │   ├── team.py              # 球队 (48队)
│   │   │   ├── match.py             # 比赛
│   │   │   ├── event.py             # 动态事件 (伤病/换帅)
│   │   │   ├── prediction.py        # Agent 预测记录
│   │   │   ├── seed.py              # 种子数据 (启动时自动装载)
│   │   │   └── database.py          # 数据库连接
│   │   ├── routers/                 # API 路由
│   │   │   ├── teams.py             # ✅ 球队接口
│   │   │   ├── events.py            # ✅ 事件管理接口
│   │   │   ├── predictions.py       # 🔧 Agent 预测接口
│   │   │   └── bracket.py           # 🔧 对阵树接口
│   │   ├── services/                # 业务逻辑
│   │   │   ├── elo_engine.py        # ✅ ELO 评分引擎
│   │   │   ├── data_collector.py    # ✅ 多源数据采集
│   │   │   ├── data_processor.py    # ✅ 数据清洗校验
│   │   │   ├── event_injector.py    # ✅ 事件注入服务
│   │   │   ├── agent_service.py     # 🔜 Qwen Agent 编排
│   │   │   ├── qwen_client.py       # 🔜 DashScope API
│   │   │   ├── tool_registry.py     # 🔜 工具注册 (7个)
│   │   │   ├── circuit_breaker.py   # 🔜 熔断器
│   │   │   └── poisson_predictor.py # 🔜 泊松预测兜底
│   │   ├── schema/                  # Pydantic 校验
│   │   └── utils/
│   ├── tests/
│   │   └── test_data_pipeline.py    # ✅ 15条数据管道测试
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # 路由 + 全局配置
│   │   ├── pages/
│   │   │   ├── HomePage.tsx         # ✅ 冠军预测总览
│   │   │   ├── TeamPage.tsx         # ✅ 球队详情
│   │   │   ├── AdminEventsPage.tsx  # ✅ 事件管理面板
│   │   │   └── BracketSandboxPage.tsx # 🔧 交互沙盘
│   │   ├── components/
│   │   │   ├── ChampionHero.tsx     # ✅ 冠军卡片 (动画)
│   │   │   └── ProbabilityBar.tsx   # ✅ 概率柱状图 (动画)
│   │   ├── services/api.ts          # API 调用层
│   │   └── types/index.ts           # TypeScript 类型
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   └── architecture.md              # 完整架构设计文档
├── docker-compose.yml
├── nginx.conf
└── README.md
```

> ✅ = 已实现  🔧 = 桩代码 (待开发)  🔜 = 下一阶段

## 开发进度

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 0 | 项目骨架 + 48队种子数据 + React前端框架 + Docker配置 | ✅ 完成 |
| Phase 1 | ELO引擎 + 数据采集清洗 + 事件注入 + 15条测试 | ✅ 完成 |
| Phase 2 | Qwen Agent 编排 + 7工具注册 + 熔断器 + 泊松兜底 | 🔜 进行中 |
| Phase 3 | 后端 API 补全 + 容错层 | ⬜ 待开始 |
| Phase 4 | Bracket Sandbox 交互沙盘 + 可视化 | ⬜ 待开始 |
| Phase 5 | 集成测试 + 性能优化 | ⬜ 待开始 |
| Phase 6 | 阿里云 ECS 部署 | ⬜ 待开始 |
| Phase 7 | 天池论坛发布 + 文档 | ⬜ 待开始 |

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- npm 10+

### 后端启动

```bash
cd backend

# 安装依赖
pip install -r requirements.txt --break-system-packages

# 启动 (首次启动会自动创建数据库并装载48队种子数据)
uvicorn app.main:app --reload
```

访问 http://localhost:8000/docs 查看自动生成的 API 文档。

### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 http://localhost:5173 查看前端页面。

### 验证

```bash
# 后端健康检查
curl http://localhost:8000/api/v1/health
# → {"status":"healthy","version":"2.0.0","agent":"qwen-max"}

# 查看全部 48 支球队
curl http://localhost:8000/api/v1/teams

# 运行测试
cd backend && python -m pytest tests/test_data_pipeline.py -v
# → 15 passed
```

## API 概览

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/v1/health` | 健康检查 | ✅ |
| GET | `/api/v1/teams` | 全部 48 支球队 | ✅ |
| GET | `/api/v1/teams/{id}` | 球队详情 | ✅ |
| GET | `/api/v1/events` | 活跃事件列表 | ✅ |
| POST | `/api/v1/events` | 添加事件 | ✅ |
| GET | `/api/v1/predictions/champion` | 冠军预测 | 🔧 |
| GET | `/api/v1/predictions/bracket` | 完整对阵树 | 🔧 |
| POST | `/api/v1/predictions/recalculate` | 情景重算 | 🔧 |

## 架构亮点

### Agent-native 决策链

每场比赛 Qwen 自主决定调用 3-5 个工具（ELO、近期状态、历史交锋、泊松模型、伤病事件），综合多维度数据后输出独立判断。Python 模型只提供数据，不做最终决策。

### 三层容错

```
Layer 1: Function Calling 格式约束 → 确保 Qwen 输出结构化
Layer 2: Pydantic 输出校验 → winner 必须在48队列表中
Layer 3: CircuitBreaker → 连续失败3次 → 熔断30s → 自动降级到泊松统计模型
```

前端通过 `is_agent` 字段感知降级状态，Agent 预测失败时自动展示"统计模型预测"标识。

### 双通道事件注入

静态基线（ELO 评分、FIFA 排名、近期战绩）与动态事件（姆巴佩伤病、巴西换帅、梅西最后一届等）同时在 Qwen 的上下文中呈现。Qwen 根据自己的分析动态调整事件的权重，而非使用固定公式。

### Bracket Sandbox (WOW 页面)

Phase 4 核心页面——不是静态对阵图，而是支持情景切换、实时重算的交互式沙盘。评委可以切换"如果姆巴佩缺阵会怎样？"等预设情景，整个对阵树通过 Framer Motion 动画重绘。

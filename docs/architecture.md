# 世界杯冠军预测 Agent — 企业级架构设计与项目规划 v2.0

> **项目名称**: WorldCup Predictor Agent
> **版本**: v2.0.0 (Agent-native 架构重构)
> **创建日期**: 2026-07-07
> **修订日期**: 2026-07-07
> **目标赛事**: 2026 FIFA World Cup (USA/Mexico/Canada)

### 修订记录

| 版本 | 日期 | 修订内容 |
|------|------|----------|
| v1.0 | 2026-07-07 | 初版：混合预测引擎 + 7 页前端 |
| v2.0 | 2026-07-07 | 架构重构：Agent-native、三层容错、事件注入、沙盘交互；修正 13 个问题 |

---

## 目录

1. [项目背景与目标](#1-项目背景与目标)
2. [系统架构设计 (Agent-native)](#2-系统架构设计-agent-native)
3. [技术选型评估](#3-技术选型评估)
4. [数据策略设计](#4-数据策略设计)
5. [预测引擎设计 (Agent-native)](#5-预测引擎设计-agent-native)
6. [可视化方案设计](#6-可视化方案设计)
7. [开发阶段规划](#7-开发阶段规划)
8. [部署方案（阿里云）](#8-部署方案阿里云)
9. [Qwen 模型集成策略（核心决策引擎）](#9-qwen-模型集成策略核心决策引擎)
10. [风险识别与缓解](#10-风险识别与缓解)
11. [质量保障计划](#11-质量保障计划)
12. [附录](#12-附录)

---

## 1. 项目背景与目标

### 1.1 核心任务

开发一个具备数据采集、分析决策、结果输出、可视化呈现能力的世界杯冠军预测 **Agent**。
其中 **Agent 自身（Qwen）是决策核心**，而非事后文案工具。Python 统计模型降级为 Agent 的工具箱。

### 1.2 成功标准

| 维度 | 标准 | 量化指标 |
|------|------|----------|
| Agent 决策能力 | Qwen 主导每场比赛预测决策 | 每场 ≥1 次 Qwen function call 调用工具链 |
| 推理可解释性 | 推理过程可追溯 | 每场预测附带完整 reasoning_chain |
| 系统鲁棒性 | API 故障不破坏用户体验 | 3s 内自动降级到统计模型，前端感知到 is_agent 标记 |
| 可视化质量 | 交互深度 > 静态展示 | Bracket Sandbox 支持情景切换 + 实时重算 |
| 工具链完整 | 全流程 AI 工具开发 | Qoder/Qwen 截图 ≥20 张，覆盖全阶段 |

### 1.3 项目范围

- **包含**: 2026 世界杯 48 队完整预测、Agent 主导的小组赛→决赛全链路推演、Bracket Sandbox 可视化交互、三层容错降级
- **不包含**: 实时比赛数据更新、用户登录系统、多语言支持

---

## 2. 系统架构设计 (Agent-native)

### 2.1 核心设计原则：LLM-as-Decision-Maker

```
         传统架构 (v1.0)                    Agent-native 架构 (v2.0)
    ┌──────────────────────┐         ┌──────────────────────────┐
    │  Python 模型做决策    │         │  Qwen Agent 做决策        │
    │         ↓            │         │       ↓                  │
    │  LLM 写文案          │         │  调用 Python 工具获取数据  │
    │                      │         │       ↓                  │
    │  AI = 翻译官         │         │  综合多维度自主分析        │
    └──────────────────────┘         │       ↓                  │
                                      │  输出结构化预测 + 推理链   │
                                      │                          │
                                      │  Python = 工具箱          │
                                      └──────────────────────────┘
```

### 2.2 整体架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                       前端展示层 (React + TS)                       │
│  ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌─────────────────┐ │
│  │ 冠军总览  │ │ Bracket      │ │ 球队详情  │ │ 事件管理面板     │ │
│  │ (Home)   │ │ Sandbox ★WOW │ │ (Team)   │ │ (Admin/Events)  │ │
│  └────┬─────┘ └──────┬───────┘ └────┬─────┘ └────────┬────────┘ │
│       └──────────────┴──────────────┴───────────────┘           │
│                            │ HTTP/REST                           │
└────────────────────────────┼────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────┐
│                      API 网关层 (FastAPI)                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  /api/v1/predictions/*     /api/v1/bracket/*             │    │
│  │  /api/v1/teams/*           /api/v1/events/*              │    │
│  │  /api/v1/health                                          │    │
│  └──────────────────────────┬──────────────────────────────┘    │
└─────────────────────────────┼───────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────┐
│                      业务逻辑层                                   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │                AgentService (核心编排)                    │     │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────────┐   │     │
│  │  │ Qwen     │  │ Tool     │  │ CircuitBreaker     │   │     │
│  │  │ Client   │  │ Registry │  │ (Qwen 故障→降级)    │   │     │
│  │  └────┬─────┘  └────┬─────┘  └─────────┬──────────┘   │     │
│  │       │             │                  │                │     │
│  │       │    ┌────────┴────────┐         │                │     │
│  │       │    │  Tool 工具集     │         │                │     │
│  │       │    │                 │         │                │     │
│  │       │    │ get_elo_rating  │         │                │     │
│  │       │    │ get_recent_form │         │                │     │
│  │       │    │ get_h2h_record  │         │                │     │
│  │       │    │ get_poisson_pred│         │                │     │
│  │       │    │ get_team_events │ ← 动态事件(伤病/换帅)    │     │
│  │       │    │ get_group_stand │         │                │     │
│  │       └────┴────────┬────────┘         │                │     │
│  └─────────────────────┼──────────────────┼────────────────┘     │
│                        │                  │                      │
│  ┌─────────────────────┼──────────────────┼────────────────┐     │
│  │               PredictionService (容错降级层)              │     │
│  │  ┌──────────────────┴──────────────────┐                │     │
│  │  │  try: AgentService.predict()        │                │     │
│  │  │  except (Timeout, ValidationError): │                │     │
│  │  │      fallback → PoissonPredictor    │                │     │
│  │  └─────────────────────────────────────┘                │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌──────────────┐ ┌─────────────┐ ┌──────────────────────────┐  │
│  │ DataCollector │ │ EventInjector│ │ BracketSimulator(蒙特卡洛)│  │
│  │ (多源采集)     │ │ (事件注入)    │ │ (n=10,000 可选Agent模式) │  │
│  └───────┬───────┘ └──────┬──────┘ └────────────┬─────────────┘  │
└──────────┼────────────────┼────────────────────┼─────────────────┘
           │                │                    │
┌──────────┼────────────────┼────────────────────┼─────────────────┐
│                       数据层                                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │ SQLite   │ │ 文件存储  │ │ 种子数据  │ │ Qwen API (外部)     │  │
│  │ Team     │ │ CSV/JSON │ │ Seed SQL │ │ 通过 DashScope     │  │
│  │ Match    │ │          │ │ (预置48队)│ │                    │  │
│  │ Event    │ │          │ │          │ │                    │  │
│  │ Predict  │ │          │ │          │ │                    │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 架构决策记录 (ADR)

| ADR # | 决策 | 备选方案 | 选择理由 |
|-------|------|----------|----------|
| ADR-001 | FastAPI 后端 | Django REST / Flask | 异步性能、自动 OpenAPI 文档、Pydantic 类型安全 |
| ADR-002 | SQLite 主存储 | PostgreSQL / MySQL | 零运维、便携、数据量 <10万条 |
| ADR-003 | React + Vite + TS | Next.js / Vue | Vite 构建最快、React 生态最丰富 |
| ADR-004 | **Agent-native 架构** | 纯规则 / 纯ML / 混合 | Qwen 主导决策，Python 降级为工具；决策过程可解释、可审查 |
| ADR-005 | Function Calling 约束输出 | Free-text / JSON mode | 结构化输出保证前端渲染可靠性 |
| ADR-006 | Circuit Breaker 降级 | 无降级 / 纯规则 | Qwen 故障时自动切到 Poisson 统计模型，3s 内完成 |
| ADR-007 | 双通道事件注入 | 纯静态权重 | 伤病/换帅等事件由 Qwen 动态解释权重，不依赖固定公式 |
| ADR-008 | Bracket Sandbox 交互 | 静态对阵图 | 评委可亲自操作情景切换，路演演示效果远超静态页面 |

### 2.4 核心模块职责

| 模块 | 角色 | 职责 | 关键接口 |
|------|------|------|----------|
| **AgentService** | 决策核心 | 编排 Qwen 调用、工具链、结果解析 | `predict_match(home, away) → AgentDecision` |
| QwenClient | LLM 网关 | 封装 DashScope API，函数调用 | `chat_with_tools(messages, tools) → Response` |
| ToolRegistry | 工具注册 | 提供 Agent 可调用的 7 个工具 | `register_all() → List[Tool]` |
| CircuitBreaker | 容错防护 | Qwen 故障检测、熔断、半开恢复 | `is_open() → bool`, `record_failure()` |
| PredictionService | 容错编排 | Agent 优先，失败 → 统计模型兜底 | `predict_with_fallback(match) → Prediction` |
| EloEngine | 数据工具 | 计算 ELO 评分 | `get_elo(team) → float` |
| PoissonPredictor | 数据工具+兜底 | 泊松比分预测 | `predict(home, away) → ScorePrediction` |
| EventInjector | 动态因素 | 注入伤病/换帅等实时事件 | `get_active_events(team) → List[Event]` |
| BracketSimulator | 统计验证 | 蒙特卡洛模拟整体赛程 | `simulate(n=10000, agent_mode=bool)` |
| DataCollector | 数据采集 | 多源采集、清洗、归一化 | `collect_all() → Dataset` |
| PredictionSchema | 输出校验 | Pydantic 验证 Agent 输出结构 | `model_validate(raw) → ValidatedPrediction` |

---

## 3. 技术选型评估

### 3.1 后端技术栈

```
Python 3.11+
├── FastAPI 0.111+          # Web 框架 (ASGI)
├── Uvicorn                 # ASGI 服务器
├── SQLAlchemy 2.0+         # ORM
├── Pandas 2.0+             # 数据处理
├── NumPy + SciPy           # 数值计算 + 泊松分布
├── Pydantic 2.0+           # 数据验证 + Agent 输出校验
├── dashscope               # 阿里云 Qwen API SDK
├── tenacity                # 重试策略 (Agent 调用)
└── structlog               # 结构化日志
```

### 3.2 前端技术栈

```
React 18+ / TypeScript 5+
├── Vite                    # 构建工具
├── React Router 6+         # 路由 (4 页)
├── TailwindCSS 3.4+        # 样式框架
├── Framer Motion 10+       # 动画 (Bracket Sandbox 核心)
├── Recharts 2.10+          # 图表 (夺冠概率柱状图)
└── TanStack Query 5+       # 异步状态 + 缓存
```

### 3.3 部署与 DevOps

```
Docker + docker-compose
├── Nginx                   # 反向代理 + 静态文件
├── 阿里云 ECS              # 云服务器
└── 阿里云函数计算 (备选)   # Serverless
```

### 3.4 技术决策对比矩阵

| 维度 | 选择 | 对比项 | 理由 |
|------|------|--------|------|
| 后端框架 | FastAPI | Django | 异步性能 + 自动文档 + Pydantic 校验 |
| 前端框架 | React | Vue | 生态丰富，Framer Motion 支持最优 |
| 样式方案 | Tailwind | Ant Design | 定制化强，不依赖组件库 |
| 数据库 | SQLite | PostgreSQL | 零运维，数据量小，单文件部署 |
| 图表库 | Recharts | ECharts | React 原生，TS 类型安全 |
| Agent 编排 | Function Calling | LangChain | 更轻量，无需额外依赖 |
| 动画库 | Framer Motion | CSS Transition | 沙盘复杂交互必需声明式动画 |

---

## 4. 数据策略设计

### 4.1 数据源矩阵

| 数据源 | 内容 | 获取方式 | 优先级 | 备注 |
|--------|------|----------|--------|------|
| Kaggle FIFA Dataset | 1930-2022 历史比赛 | CSV 下载 | P0 | 训练泊松模型参数 |
| ELO Ratings DB | 球队 ELO 评分历史 | 开源数据集 | P0 | 核心实力指标 |
| FIFA 官方排名 | 最新国家队排名 | 网页爬虫 | P0 | 官方权威参考 |
| 2026 分组数据 | 48 队分组信息 | 手动整理 JSON | P0 | 如未公布则基于排名模拟 |
| 球队新闻/事件 | 伤病、换帅等 | 手动录入 JSON | P1 | 事件注入通道 |
| 球员阵容 | 各队大名单 | API/爬虫 | P2 | V1 可选 |

### 4.2 种子数据策略（关键新增）

**问题**: 48 支球队 + 12 个小组 + 淘汰赛对阵模板是基线数据，不能依赖运行时采集。

**方案**: 预置 Seed SQL 脚本，应用启动时自动装载：

```sql
-- 种子数据包含:
-- 1. 48 支参赛球队 (name, fifa_code, confederation, elo_rating, fifa_ranking)
-- 2. 12 个小组分配 (group A-L → 4 teams each)
-- 3. 淘汰赛对阵模板 (R32/R16/QF/SF/Final 的槽位定义)
-- 4. 初始事件 (已知伤病/换帅等)
```

### 4.3 数据模型设计（修订）

```
Team (球队)
├── id: int
├── name: str
├── fifa_code: str
├── confederation: str
├── fifa_ranking: int
├── elo_rating: float
├── group: str
├── pot: int (1-4)
├── stats: JSON (历史统计)
└── events: relationship → [Event]        ← 新增: 动态事件关联

Match (比赛)
├── id: int
├── stage: enum (GROUP/R32/R16/QF/SF/THIRD/FINAL)
├── home_team_id: FK → Team
├── away_team_id: FK → Team
├── home_score: int | None
├── away_score: int | None
├── is_simulated: bool
└── round: str (分组轮次/淘汰赛轮次)

Event (动态事件) ← 新增模型
├── id: int
├── team_id: FK → Team
├── type: enum (INJURY/COACHING/TACTICAL/MORALE/OTHER)
├── title: str
├── description: str
├── severity: enum (CRITICAL/MAJOR/MINOR)
├── impact: JSON ({"attack": -0.20, "defense": 0, "cohesion": -0.10})
├── source: str
├── active: bool
└── created_at: datetime

AgentPrediction (预测) ← 重构
├── id: int
├── match_id: FK → Match
├── winner: str (球队名 or "draw")
├── predicted_score: str ("2-1" or "1-1 (4-2 pens)")
├── confidence: float (0-1)
├── key_factors: JSON (["姆巴佩缺阵", "英格兰防守反击克制"])
├── reasoning_chain: JSON ([step1, step2, ...])  ← 完整推理链
├── is_agent: bool              ← 新增: Agent决策 vs 统计兜底
├── model_used: str             ← 新增: "qwen-max" / "poisson-statistical"
├── tool_calls_log: JSON        ← 新增: 记录Qwen调用了哪些工具
└── created_at: datetime
```

### 4.4 数据流向（修订）

```
[种子数据 (Seed SQL)] ──────────────────────────────┐
                                                      ▼
[外部数据源] → DataCollector → DataProcessor → [SQLite]
                                                      │
[事件录入] → EventInjector ──────────────────────────┤
                                                      │
                                                      ▼
              ┌───────────────────────────────────────────┐
              │          AgentService (Qwen 决策)           │
              │                                            │
              │  Qwen 自主决定调用工具链:                    │
              │  get_elo(team) → get_form(team)             │
              │  → get_h2h(t1,t2) → get_poisson(t1,t2)     │
              │  → get_events(team) → 综合分析 → 决策       │
              │                                            │
              │  ↓ 成功             ↓ 失败(超时/格式错)      │
              │  AgentPrediction    PoissonPredictor 兜底   │
              │  is_agent=true      is_agent=false          │
              └──────────────────┬────────────────────────┘
                                 │
                                 ▼
              [API Router] → [JSON] → [React Frontend]
```

---

## 5. 预测引擎设计 (Agent-native)

### 5.1 核心架构：Agent 决策链

```
┌─────────────────────────────────────────────────────────────────┐
│               Agent 决策链 (Qwen 主导，每场比赛 1 次调用)          │
│                                                                  │
│  Layer 1: 工具调用 (Function Calling)                             │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Qwen 收到 System Prompt + 比赛上下文后，自主决定调用:      │     │
│  │                                                          │     │
│  │ Tool 1: get_elo_rating(team) → {"FRA": 2050, "ENG": 1980}│    │
│  │ Tool 2: get_recent_form(team) → 近10场战绩统计            │     │
│  │ Tool 3: get_h2h_record(t1, t2) → 历史交锋记录             │     │
│  │ Tool 4: get_poisson_pred(t1, t2) → 泊松模型预测           │     │
│  │ Tool 5: get_team_events(team) → 活跃事件列表              │     │
│  │                                                          │     │
│  │ Qwen 根据数据完整性决定调用哪些工具（最少 3 个，最多 5 个）  │     │
│  └──────────────────────┬───────────────────────────────────┘     │
│                         ▼                                         │
│  Layer 2: 决策推理 (Qwen 自主分析)                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Qwen 综合所有工具返回的数据，进行多维度分析并做出判断:       │     │
│  │                                                          │     │
│  │ "基于以上数据:                                            │     │
│  │  - ELO 差 +70 (法国占优)                                  │     │
│  │  - 但伤病报告: 姆巴佩出战成疑 (攻击力估值下降约 20%)       │     │
│  │  - 历史交锋: 近 3 场英格兰 2 胜 1 平不败                  │     │
│  │  - 泊松模型: 法国期望进球 1.8 vs 1.2                      │     │
│  │                                                          │     │
│  │  我的判断: 姆巴佩的缺阵对法国进攻端是结构性打击，           │     │
│  │  他贡献了球队近 40% 的进攻威胁。英格兰的防守反击策略        │     │
│  │  在近 3 次交手中对法国有明显克制效果。                     │     │
│  │  虽然绝对实力法国更优，但综合临场因素，                    │     │
│  │  我倾向于英格兰不败，预测比分 1:1，加时赛后英格兰胜。"     │     │
│  └──────────────────────┬───────────────────────────────────┘     │
│                         ▼                                         │
│  Layer 3: 结构化输出 (Function Call Response)                      │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ {                                                        │     │
│  │   "winner": "England",                                   │     │
│  │   "score": "1-1 (4-2 pens)",                             │     │
│  │   "confidence": 0.62,                                    │     │
│  │   "key_factors": [                                       │     │
│  │     "姆巴佩缺阵导致法国进攻效率下降约35%",                  │     │
│  │     "英格兰近3次交锋2胜1平保持不败",                       │     │
│  │     "英格兰防守反击体系对法国有明显克制"                    │     │
│  │   ],                                                     │     │
│  │   "reasoning_chain": [                                   │     │
│  │     {"step": 1, "tool": "get_elo_rating", "finding": "..."},│   │
│  │     {"step": 2, "tool": "get_team_events", "finding": "..."},│  │
│  │     {"step": 3, "tool": "get_h2h_record", "finding": "..."}, │  │
│  │     {"step": 4, "analysis": "综合判断...", "conclusion": "..."}│  │
│  │   ]                                                      │     │
│  │ }                                                        │     │
│  └─────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 工具注册表 (7 个工具)

```python
# ToolRegistry — Qwen 可调用的全部工具
TOOLS = [
    {
        "name": "get_elo_rating",
        "description": "获取指定球队的 ELO 评分（反映长期竞技实力，最稳定的实力指标）",
        "parameters": {"team_name": "string"}
    },
    {
        "name": "get_fifa_ranking",
        "description": "获取指定球队的最新 FIFA 世界排名和积分",
        "parameters": {"team_name": "string"}
    },
    {
        "name": "get_recent_form",
        "description": "获取球队近 10 场比赛战绩（胜/平/负 + 对手强度）",
        "parameters": {"team_name": "string", "n_matches": "int = 10"}
    },
    {
        "name": "get_h2h_record",
        "description": "获取两队历史交锋记录（最近 5 场）",
        "parameters": {"team_a": "string", "team_b": "string"}
    },
    {
        "name": "get_poisson_prediction",
        "description": "基于泊松模型的比分预测（统计参考，不一定是最终答案）",
        "parameters": {"home_team": "string", "away_team": "string"}
    },
    {
        "name": "get_team_events",
        "description": "获取球队当前的活跃事件（伤病、换帅、战术调整等）",
        "parameters": {"team_name": "string"}
    },
    {
        "name": "get_group_standings",
        "description": "获取指定小组的当前积分排名",
        "parameters": {"group": "string"}
    }
]
```

### 5.3 System Prompt 设计（关键）

```python
AGENT_SYSTEM_PROMPT = """你是一个资深足球分析师 AI Agent，负责预测 2026 世界杯比赛结果。

## 你的角色
你是决策者，不是翻译官。你需要主动调用工具获取数据，然后基于数据做出独立的分析判断。
Python 模型给出的预测（如泊松模型）只是参考，你可以选择采纳、调整或推翻它。

## 决策流程
1. 先调用 get_elo_rating 和 get_fifa_ranking 了解双方实力基线
2. 调用 get_recent_form 了解近期状态
3. 调用 get_h2h_record 了解历史对阵
4. 调用 get_team_events 检查是否有伤病/换帅等突发事件
5. （可选）调用 get_poisson_prediction 获取统计模型参考
6. 综合所有数据，给出你的独立判断

## 输出格式要求
你必须通过 submit_prediction 函数返回结果，格式:
- winner: 胜出球队名称（或 "draw" 表示平局）
- score: 预测比分，如 "2-1" 或 "1-1 (4-2 pens)"
- confidence: 0-1 之间的置信度
- key_factors: 3-5 个影响预测的关键因素
- reasoning_chain: 完整的逐步推理过程
"""
```

### 5.4 三层容错防线

```
┌──────────────────────────────────────────────────────────────┐
│                   PredictionService 容错流程                     │
│                                                                │
│  ┌─────────────────┐                                          │
│  │ 请求预测           │                                          │
│  └────────┬────────┘                                          │
│           │                                                    │
│           ▼                                                    │
│  ┌─────────────────┐     ┌──────────────────────────────┐    │
│  │ CircuitBreaker   │────▶│ OPEN → 跳过 Agent，直接降级    │    │
│  │ 检查状态          │     │ (连续 3 次失败则熔断 30s)       │    │
│  └────────┬────────┘     └──────────────────────────────┘    │
│           │ CLOSED / HALF_OPEN                                 │
│           ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ Layer 1: 调用 Qwen Agent (timeout=15s, retries=2)    │     │
│  │                                                       │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │     │
│  │  │ 超时?    │  │ API错误? │  │ 返回格式错乱?     │   │     │
│  │  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │     │
│  │       │             │                 │               │     │
│  │       └─────────────┴─────────────────┘               │     │
│  │                       │ 任一触发                       │     │
│  └───────────────────────┼───────────────────────────────┘     │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ Layer 2: Pydantic 校验                                │     │
│  │                                                       │     │
│  │  if not PredictionSchema.model_validate(raw):          │     │
│  │      → winner 不在 48 队列表? → 拒绝 + 重试            │     │
│  │      → confidence 超出 [0,1]? → clamp                  │     │
│  │      → reasoning_chain 为空? → 标记 incomplete         │     │
│  │      → JSON 解析失败? → 记录 + 降级                    │     │
│  └───────────────────────┬───────────────────────────────┘     │
│                          │ 校验失败                             │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ Layer 3: 降级到 PoissonPredictor                      │     │
│  │                                                       │     │
│  │  result = PoissonPredictor.predict(home, away)         │     │
│  │  result.is_agent = False                              │     │
│  │  result.model_used = "poisson-statistical"            │     │
│  │  → 记录降级事件到 CircuitBreaker                       │     │
│  │  → 前端渲染降级标识 "⚠️ 统计模型预测"                   │     │
│  └─────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

### 5.5 双通道动态事件注入

```
通道 A: 静态基线（Python 计算）      通道 B: 动态事件（Qwen 解释）
┌──────────────────────────┐      ┌──────────────────────────┐
│ ELO 评分: 2050 vs 1980   │      │ Event: 姆巴佩 伤病       │
│ FIFA 排名: #2 vs #5      │      │ Event: 法国 换帅         │
│ 近期状态: 7W 2D 1L        │      │ Event: 英格兰 新战术体系  │
│ 泊松预测: 1.8 vs 1.2      │      │                         │
│                          │      │ (JSON stored in DB,      │
│ (计算的确定性数值)         │      │  Qwen 动态解释权重)      │
└───────────┬──────────────┘      └───────────┬──────────────┘
            │                                  │
            └────────────┬─────────────────────┘
                         ▼
              ┌─────────────────────┐
              │  Qwen Agent 综合决策  │
              │                      │
              │  "虽然绝对实力法国占优，│
              │   但姆巴佩缺阵使进攻端 │
              │   估值下降约35%，      │
              │   我将法国胜率从 65%   │
              │   下调至 48%。"        │
              └──────────┬──────────┘
                         ▼
                   最终预测结果
```

Event 数据结构使得 Qwen 能读取到"发生了什么"而不仅仅是"数值是多少"：

```json
{
  "team": "France",
  "type": "INJURY",
  "title": "姆巴佩疑似肌肉拉伤",
  "severity": "CRITICAL",
  "description": "赛前训练中左腿肌肉不适，队医评估出战概率约 40%",
  "impact_hint": {"attack": -0.20, "team_morale": -0.05},
  "source": "队医赛前发布会 (2026-07-06)"
}
```

`impact_hint` 是建议值，Qwen 可以根据自己的分析调整甚至覆盖它。

### 5.6 蒙特卡洛模拟（支持 Agent 模式）

```python
def monte_carlo_simulation(n=10000, agent_mode=True):
    """
    两种模式:
    - agent_mode=True: 每场淘汰赛调用 Qwen Agent 决策 (高质量，慢)
    - agent_mode=False: 使用泊松概率随机抽样 (快，用于大量模拟时的基线)
    
    实际策略: agent_mode=True 跑 1 次得到"最佳推演路径"
             agent_mode=False 跑 10,000 次得到"概率分布"
             两者结合展示：最可能路径 + 概率分布
    """
    # Agent 模式: 1 次完整推演（展示用）
    best_path = agent_driven_simulation()  # 每场调用 Qwen
    
    # 统计模式: 10,000 次（概率用）
    champion_counts = defaultdict(int)
    for _ in range(n):
        bracket = simulate_knockout_probabilistic()
        champion_counts[bracket.champion] += 1
    
    return {
        "best_path": best_path,          # Agent 推演的最佳路径
        "champion_probs": champion_counts,  # 概率分布
        "iterations": n
    }
```

---

## 6. 可视化方案设计

### 6.1 页面架构（精简 4 页）

```
Web App (SPA)
├── /                    # 首页 - 冠军预测总览 + AI 推理摘要
├── /bracket             # ★ Bracket Sandbox (核心 WOW 页面)
├── /team/:id            # 球队详情 + Agent 晋级路径分析
└── /admin/events        # 事件管理面板 (展示动态调整能力)
```

### 6.2 Bracket Sandbox — WOW 交互设计

这是路演的核心差异化页面。不做静态对阵图，做能回答"如果……"的交互式推演沙盘：

```
┌──────────────────────────────────────────────────────────────┐
│                      Bracket Sandbox                           │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  情景选择: [默认] [法国: 姆巴佩缺阵] [巴西: 战术调整]     │    │
│  │           [阿根廷: 梅西状态巅峰] [+ 自定义情景]         │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                                                       │    │
│  │   R32      R16       QF        SF       Final       │    │
│  │  ┌──┐     ┌──┐      ┌──┐     ┌──┐     ┌──────┐     │    │
│  │  │🇫🇷│─┐   │🇫🇷│──┐   │🇫🇷│─┐   │🇫🇷│─┐   │  🇫🇷  │     │    │
│  │  └──┘ │   └──┘  │   └──┘ │   └──┘ │   │ 1-1   │     │    │
│  │       ├───┤      ├───┤      ├───┤      │ (4-2) │     │    │
│  │  ┌──┐ │   ┌──┐  │   ┌──┐ │   ┌──┐ │   │  🏆   │     │    │
│  │  │🇺🇸│─┘   │🏴󠁧󠁢󠁥󠁮󠁧󠁿│──┘   │🏴󠁧󠁢󠁥󠁮󠁧󠁿│─┘   │🏴󠁧󠁢󠁥󠁮󠁧󠁿│─┘   └──────┘     │    │
│  │  └──┘     └──┘      └──┘     └──┘                 │    │
│  │                                                       │    │
│  │  (Framer Motion 动画: 点击任一节点展开/折叠子树)        │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  🗣️ AI Pundit 分析面板                                  │    │
│  │  ┌────────────────────────────────────────────────┐   │    │
│  │  │ Qwen: "在当前情景下（法国缺少姆巴佩），我认为     │   │    │
│  │  │  英格兰在半决赛中有明显优势。英格兰的防守反击    │   │    │
│  │  │  体系在过去 3 次对阵法国时均保持不败..."        │   │    │
│  │  │                                                  │   │    │
│  │  │ [显示完整推理链] [查看数据来源]                    │   │    │
│  │  └────────────────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  夺冠概率分布 (10,000 次蒙特卡洛模拟)                    │    │
│  │  ████████████████████ 法国 22.3%                       │    │
│  │  ████████████████     巴西 18.1%                       │    │
│  │  ████████████         英格兰 14.5%                     │    │
│  │  ██████████           阿根廷 12.8%                     │    │
│  │  ██████               西班牙 8.2%                       │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 6.3 核心可视化组件

| 组件 | 功能 | 技术栈 | WOW 因素 |
|------|------|--------|----------|
| **BracketSandbox** | 交互式对阵树 + 情景切换 | SVG + Framer Motion | 拖拽调整事件 → 实时重算整个 bracket |
| **AIPunditPanel** | Qwen 实时推理对话 | 流式文本渲染 | 模拟"专家点评"，可追问 |
| **ScenarioSlider** | 情景预设切换 | Framer AnimatePresence | 切换情景时整个树动画过渡 |
| **MatchNode** | 单场比赛节点 | SVG + hover 动画 | 点击展开 Matc​​hCard + 推理链 |
| **ChampionHero** | 冠军大卡片 | Framer Motion layout | 情景切换时冠军丝滑变换 |
| **ProbabilityBar** | 夺冠概率柱状图 | Recharts | 支持钻取到具体模拟路径 |

### 6.4 设计系统

```css
:root {
  /* 颜色 - 世界杯主题 */
  --color-bg: #0a0a1a;
  --color-surface: #141428;
  --color-primary: #1a56db;
  --color-accent: #e94560;
  --color-gold: #f5c518;
  --color-silver: #c0c0c0;
  --color-bronze: #cd7f32;
  --color-text: #e8e8f0;
  --color-text-muted: #8888a0;

  /* 字体 */
  --font-display: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  /* 动画 */
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --duration-normal: 300ms;
}
```

### 6.5 交互设计原则

1. **可玩性优先**: 评委能亲手操作情景切换，不只是看静态数据
2. **渐进式信息披露**: 冠军 → 对阵树 → 单场详情 → 推理链 → 数据来源
3. **每场可追问**: 任意比赛节点点击展开 AI Pundit 分析
4. **动画叙事**: Framer Motion 让情景切换、冠军变化有"故事感"
5. **降级可视化**: 当 `is_agent=false` 时，节点边缘显示虚线（表示统计模型），而非 Agent 模式的实线

---

## 7. 开发阶段规划

### 7.1 整体时间线

```
Phase 0: 项目初始化 + 种子数据      [Day 1 上午]
Phase 1: 数据采集与事件系统          [Day 1 下午]
Phase 2: Agent 预测引擎开发          [Day 2]
Phase 3: 后端 API + 容错层          [Day 3]
Phase 4: 前端可视化 + Bracket Sandbox [Day 4-5]
Phase 5: 集成测试 + 性能优化         [Day 5-6]
Phase 6: 阿里云部署                 [Day 6]
Phase 7: 文档 + 路演材料            [Day 6-7]
```

### 7.2 各阶段详细任务

#### Phase 0: 项目初始化 + 种子数据 (0.5 day)

```
⬜ 初始化 Python 虚拟环境 + requirements.txt
⬜ 初始化 React + Vite + TypeScript 项目
⬜ 编写 Dockerfile + docker-compose.yml
⬜ 编写种子数据 SQL (48 队 + 12 组 + 淘汰赛模板)
⬜ 种子数据加载脚本 (app 启动时自动执行)
⬜ 初始化 Git 仓库
```

#### Phase 1: 数据采集与事件系统 (0.5 day)

```
⬜ 下载 Kaggle 历史数据集 → data/raw/
⬜ 整理 2026 分组数据 JSON
⬜ 采集/录入 ELO 评分数据
⬜ 实现 DataCollector + DataProcessor
⬜ 实现 Event 数据模型 + EventInjector
⬜ 预置 5-8 个初始事件（伤病/换帅等）
⬜ 数据质量验证
```

#### Phase 2: Agent 预测引擎 (1 day) — 核心

```
⬜ 实现 ToolRegistry (7 个工具)
⬜ 实现 QwenClient (DashScope function calling)
⬜ 实现 AgentService (System Prompt + 编排逻辑)
⬜ 实现 PredictionSchema (Pydantic 校验)
⬜ 实现 CircuitBreaker
⬜ 实现 PoissonPredictor (兜底)
⬜ 实现 EventInjector (动态事件)
⬜ 实现 BracketSimulator (Agent 模式 + 统计模式)
⬜ 编写单元测试 (Agent mock + 降级 + 校验)
```

#### Phase 3: 后端 API (1 day)

```
⬜ FastAPI 项目结构 + SQLAlchemy 模型
⬜ API 路由:
    - GET  /api/v1/predictions/match/{id}     ← Agent 实时预测
    - GET  /api/v1/predictions/champion       ← 冠军预测总览
    - GET  /api/v1/predictions/bracket        ← 完整对阵树
    - POST /api/v1/predictions/recalculate    ← 情景重算 (触发 Agent)
    - GET  /api/v1/teams/{id}                 ← 球队详情
    - GET  /api/v1/events                     ← 事件列表
    - POST /api/v1/events                     ← 添加事件 (Admin)
    - GET  /api/v1/health                     ← 健康检查
⬜ CORS + 错误处理中间件
⬜ Agent 响应缓存 (同场比赛同情景 5min 内不重复调用)
```

#### Phase 4: 前端可视化 (1.5 days) — 最关键

```
⬜ React Router + TailwindCSS 配置
⬜ 首页 ChampionHero + ProbabilityBar
⬜ ★ BracketSandbox 页面 (Framer Motion + SVG)
    - 五层嵌套对阵树 (R32→R16→QF→SF→Final)
    - 节点: 国旗 + 队名 + 比分 + 置信度
    - 点击展开 MatchCard + ReasoningChain
    - 水平/垂直滚动（支持 32 个 R32 节点）
⬜ ScenarioSlider 情景切换
    - 预设情景列表
    - 切换触发全树动画重绘
    - AnimatePresence 处理过渡
⬜ AIPunditPanel (流式推理展示)
⬜ 球队详情页 (晋级路径 + 实力雷达)
⬜ 事件管理面板 (展示动态调整)
⬜ Loading / Error / Empty / is_agent 标识 四态处理
```

#### Phase 5: 集成测试 (1 day)

```
⬜ pytest 后端单元测试 (>80% coverage)
⬜ Agent mock 测试 (模拟 Qwen 返回 → 校验 → 降级)
⬜ CircuitBreaker 行为测试
⬜ API 集成测试 (httpx)
⬜ 前端组件测试 (Vitest)
⬜ E2E: Playwright 3 条核心路径
⬜ Lighthouse 性能优化 (>90)
```

#### Phase 6: 部署 (0.5 day)

```
⬜ Docker 镜像构建 + 多阶段优化
⬜ 阿里云 ECS 实例配置
⬜ Nginx 反向代理 + 静态文件
⬜ HTTPS (Let's Encrypt)
⬜ 健康检查 + 自动重启
⬜ 环境变量: QWEN_API_KEY, ALLOWED_ORIGINS
```

#### Phase 7: 文档与路演 (0.5 day)

```
⬜ 系统架构图 (draw.io/Excalidraw)
⬜ Qoder/Qwen 开发截图 >20 张
⬜ 路演 PPT（强调: Agent 决策、Bracket Sandbox、容错设计）
⬜ 天池论坛发布文稿
⬜ 功能演示视频录制 (30-60s)
```

### 7.3 MVP 优先级

```
P0 (必须 — 核心不可裁剪):
  AgentService (Qwen 决策)
  ToolRegistry (7 tools)
  PredictionService (容错降级)
  BracketSandbox (WOW 交互)
  冠军结果页面
  API 核心接口

P1 (应该 — 重要):
  小组赛积分表
  球队详情页
  事件管理面板
  Docker + 阿里云部署

P2 (最好 — 锦上添花):
  流式推理文本
  模拟参数可调
  移动端适配
```

### 7.4 Qwen API 成本优化策略

**问题**: 104 场比赛 × 每次 Agent 调用 ~2K tokens × ¥0.004/1K tokens ≈ ¥0.83/次，全量约 ¥87。情景重算可能显著增加成本。

**策略**:
1. **预计算 + 缓存**: 默认情景的预测结果预计算并缓存（5min TTL）
2. **懒加载**: 前端只请求当前可见的 MatchNode，不可见节点懒加载
3. **批量预计算**: 后台一次性调用 Qwen 预测所有 104 场比赛，存入 DB
4. **情景重算限流**: /recalculate 接口加 rate limit（每分钟 5 次）
5. **统计模式优先**: 蒙特卡洛 10,000 次使用统计模式（不调用 Qwen），仅 BracketSandbox 的"最佳推演路径"使用 Agent 模式

---

## 8. 部署方案（阿里云）

### 8.1 部署架构

```
┌──────────────────────────────────────────┐
│              阿里云 ECS (2C4G)             │
│  ┌────────────────────────────────────┐  │
│  │          Docker Host               │  │
│  │  ┌──────────┐  ┌───────────────┐   │  │
│  │  │  Nginx   │  │  FastAPI App  │   │  │
│  │  │  :80/443 │──│  :8000        │   │  │
│  │  └────┬─────┘  └───────────────┘   │  │
│  │       │                             │  │
│  │       ├── /api/* → FastAPI:8000     │  │
│  │       └── /* → Static Files (dist)  │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

### 8.2 环境变量

```bash
QWEN_API_KEY=dashscope-api-key
QWEN_MODEL=qwen-max
AGENT_TIMEOUT=15
AGENT_MAX_RETRIES=2
CIRCUIT_BREAKER_THRESHOLD=3
CIRCUIT_BREAKER_RECOVERY=30
CORS_ORIGINS=https://your-domain.com
```

---

## 9. Qwen 模型集成策略（核心决策引擎）

### 9.1 角色转变

| 维度 | v1.0 (辅助模式) | v2.0 (核心引擎模式) |
|------|-----------------|---------------------|
| Qwen 角色 | 文案润色 | **决策核心** |
| Python 角色 | 决策引擎 | **数据工具箱** |
| 调用方式 | 单向传递结果 | **双向: Qwen 主动调用工具** |
| 创新点 | 无 | **LLM-as-Decision-Maker Agent Architecture** |

### 9.2 全链路 Qwen 使用计划

| 开发阶段 | Qwen 使用 | 方法 | 证据 |
|----------|----------|------|------|
| 架构设计 | Qwen Max 评审架构方案 | 提交架构 → Qwen 分析 → 修正 | 截图 |
| 数据处理 | Qwen Coder 写清洗逻辑 | pandas 代码生成 | 截图 |
| Agent 开发 | Qwen Coder 写 ToolRegistry | Function calling 代码 | 截图 |
| 后端开发 | Qwen Coder 写 FastAPI 路由 | API 代码生成 | 截图 |
| 前端开发 | Qwen Coder 写 BracketSandbox | TSX + Framer Motion | 截图 |
| **决策推理** | **Qwen Max 做每场比赛决策** | **Function calling → 分析 → submit_prediction** | 截图 + 日志 |
| 推理文案 | Qwen 生成推理链文本 | Agent 输出 reasoning_chain | 截图 |
| Debug | Qwen 分析错误日志 | 贴错误 → 分析原因 → 修复 | 截图 |
| 文档 | Qwen Long 写路演文稿 | 长文生成 | 截图 |

### 9.3 使用原则

1. **决策可追溯**: reasoning_chain 完整记录每一步推理
2. **输出可校验**: PredictionSchema 在入库前强制校验
3. **失败有兜底**: CircuitBreaker 确保 Qwen 故障不破坏用户体验
4. **证据完整**: 每个 Qwen 使用环节截图 + 对话记录保存

---

## 10. 风险识别与缓解

| # | 风险 | 影响 | 概率 | 缓解措施 |
|---|------|------|------|----------|
| 1 | Qwen API 不稳定 | Agent 决策不可用 | 中 | CircuitBreaker → Poisson 统计模型降级 (3s 内) |
| 2 | Qwen 输出格式错乱 | 前端渲染崩溃 | 中 | **Layer 1** function call 约束 + **Layer 2** Pydantic 校验 + **Layer 3** 降级 |
| 3 | Agent 决策质量差 | 预测不合理 | 中 | 数据源覆盖 ELO+FIFA+历史+事件，System Prompt 引导严格分析 |
| 4 | 数据源不可用 | 工具返回空 | 中 | 种子数据预设基线；工具返回空时 Qwen 可感知并调整 |
| 5 | 2026 分组未公布 | 小组赛无法模拟 | 低 | 基于 FIFA 排名生成模拟分组，页面标注「基于排名模拟」 |
| 6 | Qwen API 成本过高 | 演示时超额 | 低 | 预计算 + 缓存 + 限流 (见 7.4) |
| 7 | 阿里云部署失败 | 损失加分项 | 中 | 提前准备 Dockerfile；备选 Vercel |
| 8 | BracketSandbox 性能 | 32 节点渲染卡顿 | 低 | SVG 虚拟化；Framer Motion layoutId 优化 |
| 9 | 评委不理解 Agent 角色 | 误以为是传统模型 | 低 | 首页大标题 + `/admin/events` 展示动态调整能力 |

---

## 11. 质量保障计划

### 11.1 代码质量

- ESLint + Prettier (前端)
- Black + isort + mypy (后端)
- Pre-commit hooks

### 11.2 测试策略（新增 Agent 专项）

| 层级 | 工具 | 内容 | 覆盖率 |
|------|------|------|--------|
| Python 工具测试 | pytest | EloEngine, PoissonPredictor, EventInjector | >90% |
| Agent mock 测试 | pytest + unittest.mock | 模拟 Qwen 返回 → 校验通过/失败 → 降级 | 核心路径 100% |
| CircuitBreaker 测试 | pytest | 熔断 → 半开 → 恢复行为 | 100% |
| API 集成测试 | pytest + httpx | 所有端点 + Agent/降级双模式 | >90% |
| 前端组件测试 | Vitest + Testing Library | BracketSandbox + 状态转换 | 核心组件 |
| E2E | Playwright | 首页 → Sandbox → 情景切换 → 查看推理 | 3 条路径 |
| Agent 决策质量 | 人工评审 | 抽查 20 场 Agent 预测，评估推理合理性 | 抽查 |

### 11.3 性能指标

| 指标 | 目标 | 备注 |
|------|------|------|
| 首屏加载 | <2s | 冠军预测为预计算结果 |
| Agent 预测 API | <5s | Qwen 调用 + 工具链 |
| 降级预测 API | <500ms | 纯 Poisson 计算 |
| BracketSandbox 渲染 | <1s (32 节点) | SVG + Framer Motion |
| 情景切换动画 | 300ms | AnimatePresence |
| Lighthouse | >90 | P0 页面 |

---

## 12. 附录

### A. 文件结构规划（修订）

```
WorldCup-Agent-Qoder/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── config.py                # 配置 (含 Qwen API key, timeout 等)
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── team.py
│   │   │   ├── match.py
│   │   │   ├── event.py             # ← 新增: 动态事件
│   │   │   └── prediction.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── teams.py
│   │   │   ├── predictions.py
│   │   │   ├── bracket.py
│   │   │   └── events.py            # ← 新增: 事件 CRUD
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── agent_service.py     # ← 新增: Qwen Agent 编排 (核心)
│   │   │   ├── qwen_client.py       # ← 新增: DashScope 封装
│   │   │   ├── tool_registry.py     # ← 新增: 7 个工具注册
│   │   │   ├── circuit_breaker.py   # ← 新增: 熔断器
│   │   │   ├── prediction_service.py# ← 新增: 容错编排层
│   │   │   ├── event_injector.py    # ← 新增: 事件注入
│   │   │   ├── data_collector.py
│   │   │   ├── data_processor.py
│   │   │   ├── elo_engine.py
│   │   │   ├── poisson_predictor.py
│   │   │   └── bracket_simulator.py
│   │   ├── schema/
│   │   │   ├── __init__.py
│   │   │   └── prediction_schema.py # ← 新增: Agent 输出校验
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── helpers.py
│   ├── tests/
│   │   ├── test_agent_service.py    # ← 新增: Agent 决策测试
│   │   ├── test_tool_registry.py    # ← 新增: 工具注册测试
│   │   ├── test_circuit_breaker.py  # ← 新增: 熔断器测试
│   │   ├── test_prediction_service.py# ← 新增: 容错编排测试
│   │   ├── test_elo.py
│   │   ├── test_poisson.py
│   │   ├── test_simulator.py
│   │   └── test_api.py
│   ├── seed_data/
│   │   ├── seed_teams.sql           # ← 新增: 48 队种子数据
│   │   ├── seed_groups.json         # ← 新增: 12 组分组
│   │   └── seed_events.json         # ← 新增: 初始事件
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── index.css
│   │   ├── pages/
│   │   │   ├── HomePage.tsx
│   │   │   ├── BracketSandboxPage.tsx  # ← 重构: WOW 核心页面
│   │   │   ├── TeamPage.tsx
│   │   │   └── AdminEventsPage.tsx     # ← 新增: 事件管理
│   │   ├── components/
│   │   │   ├── ChampionHero.tsx
│   │   │   ├── BracketSandbox.tsx      # ← 新增: 沙盘主组件
│   │   │   ├── MatchNode.tsx           # ← 新增: 比赛节点
│   │   │   ├── ScenarioSlider.tsx      # ← 新增: 情景切换
│   │   │   ├── AIPunditPanel.tsx       # ← 新增: AI 推理面板
│   │   │   ├── ProbabilityBar.tsx
│   │   │   ├── GroupTable.tsx
│   │   │   └── ReasoningPanel.tsx
│   │   ├── hooks/
│   │   │   ├── usePredictions.ts
│   │   │   ├── useBracket.ts           # ← 新增: 对阵树状态
│   │   │   └── useTeams.ts
│   │   ├── services/
│   │   │   └── api.ts
│   │   └── types/
│   │       └── index.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── Dockerfile
│
├── data/
│   ├── raw/
│   │   ├── kaggle_worldcup.csv
│   │   ├── elo_ratings.csv
│   │   └── fifa_rankings.json
│   ├── processed/
│   └── fixtures/
│       ├── tournament_structure.json
│       └── groups_2026.json
│
├── docs/
│   ├── architecture.md            # ← 本文档 (v2.0)
│   ├── prediction_logic.md        # 预测逻辑详解
│   ├── api_spec.md                # API 规范
│   └── deployment_guide.md        # 部署指南
│
├── screenshots/                   # Qoder/Qwen 截图
├── docker-compose.yml
├── nginx.conf
├── .gitignore
└── README.md
```

### B. 2026 世界杯赛制

- **48 支球队**，**12 个小组** (A-L)，每组 **4 队**
- 小组前 2 名 + 8 个成绩最好的小组第 3 → 32 强
- 淘汰赛: R32 → R16 → QF → SF → Third Place → Final
- 总场次: 104 场 (72 小组赛 + 32 淘汰赛)
- 举办国: 美国 / 墨西哥 / 加拿大

### C. v1.0 → v2.0 全部修正清单

| # | 问题 | v1.0 状态 | v2.0 修正 |
|---|------|-----------|-----------|
| 1 | AI 是翻译官不是决策者 | LLM 润色 Python 结果 | Qwen 做决策核心，Python 降级为工具 |
| 2 | 无 API 失败防护 | 假设 Qwen 始终可用 | 三层容错: func call 约束 → Pydantic 校验 → CircuitBreaker 降级 |
| 3 | 静态权重无法应对事件 | ELO 40%+FIFA 30% 固定公式 | 双通道事件注入 + Qwen 动态解释权重 |
| 4 | 前端缺少 WOW 交互 | 7 页静态仪表盘 | 4 页 + BracketSandbox 交互沙盘 |
| 5 | 数据流无 Agent 循环 | 线性 Pipeline | Agent 工具调用循环 |
| 6 | 缺 Event 数据模型 | 无 | Event 模型 + EventInjector |
| 7 | 蒙特卡洛不集成 Agent | 纯统计抽样 | Agent 模式推演 + 统计模式概率分布 |
| 8 | 无 AI Pundit 组件 | 无 | AIPunditPanel 实时推理 |
| 9 | Qwen 定位为"辅助" | 辅助代码生成 | 核心决策引擎 + 辅助开发 |
| 10 | 缺 Agent 决策质量测试 | 纯统计测试 | Agent mock 测试 + 人工评审 |
| 11 | Qwen API 成本无预算 | 未考虑 | 预计算 + 缓存 + 限流策略 |
| 12 | 缺种子数据策略 | 运行时采集 | Seed SQL 预置 48 队基线 |
| 13 | 分组数据来源未处理 | "待采集" | 模拟分组 + 标注不确认性 |

---

> **文档状态**: ✅ v2.0 已完成 (修正全部 13 个问题)
> **下一步**: Phase 0 — 项目初始化 + 种子数据
> **负责人**: Cowork 3P + Claude Agent

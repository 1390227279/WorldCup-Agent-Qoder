# 世界杯情景预测系统

这是一个把“统计基线、事件情景、完整淘汰赛路径和单场 AI 解读”分开处理的世界杯预测应用。

系统中的比赛结果由后端数学模型生成：ELO 表示球队基础实力，泊松分布生成比分，蒙特卡洛模拟统计各轮晋级与夺冠概率。Qwen 不决定比分、胜者或概率，只在用户点击一场比赛后，解释已经确定的数学结果。

> 数据声明：当前 48 队阵容来自用户提供的非官方情景数据，赛事状态为 `SCENARIO`，不是 FIFA 官方参赛名单。中国等球队是否进入模拟，只取决于当前赛事的 `TournamentTeam` 参赛关系。

## 四个业务模块

| 模块 | 定位 | 数据来源 | AI 参与 |
|---|---|---|---|
| 首页 | 无事件基础实力大盘 | 同一批 ELO/泊松蒙特卡洛基线 | 不参与 |
| 淘汰赛推演 | 事件修正后的平行情景 | 基线参数加事件对进球期望值的修正 | 不参与 |
| 单场比赛详情 | 数学结果与战术解释 | 当前模拟中的比赛、比分、概率、期望进球和事件 | 只生成解释 |
| 赛事事件管理 | 情景变量池 | 后台 CRUD 与 CSV/JSON 导入 | 不参与 |

首页与未选择事件的淘汰赛页面复用同一个 `simulation_id`。选择事件后，系统沿用基线主种子进行控制变量模拟，不会污染首页基线，也不会修改球队原始 ELO。

## 模拟规则

- 每次迭代完整模拟 12 个小组，再按“小组前两名 + 8 个最佳第三名”产生 32 强。
- 当前非官方阵容使用产品固定规则 `scenario-fixed-v1` 生成 32 强对位。
- 淘汰赛固定返回 32 强、16 强、八强、半决赛和决赛，共 `16/8/4/2/1` 场。
- 每场比赛具有稳定的 `match_key`、来源槽位、比分、胜者和晋级关系。
- 概率榜来自全部迭代的统计结果，不等同于某一次随机赛程。
- 代表路径是在“夺冠概率第一球队最终夺冠”的真实模拟样本中，选择对数似然最高的一届完整赛事；模拟期间每支冠军球队只保留一个候选，最终仅重放一次，不全量保存或二次扫描 1000 棵对阵树。

## 技术栈

- 后端：FastAPI、SQLAlchemy、SQLite、NumPy、SciPy、Pydantic
- AI 解读：阿里云 DashScope Qwen、重试与熔断保护
- 前端：React 19、TypeScript、Vite、Tailwind CSS、TanStack Query、Framer Motion、Recharts
- 测试：Pytest、HTTPX、Oxlint、TypeScript/Vite 构建

## 快速开始

环境要求：Python 3.11+、Node.js 20+、npm 10+。

### 后端

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

可在 `backend/.env` 或启动进程的环境变量中配置：

```dotenv
QWEN_API_KEY=你的密钥
QWEN_MODEL=qwen-max
AGENT_TIMEOUT=15
AGENT_MAX_RETRIES=2
CIRCUIT_BREAKER_THRESHOLD=3
CIRCUIT_BREAKER_RECOVERY=30
DATABASE_URL=sqlite+aiosqlite:///./worldcup.db
```

未配置 Qwen、调用超时或熔断时，模拟和数学比赛结果仍正常返回，单场详情只会显示“AI 暂时不可用”。

### 前端

```powershell
cd frontend
npm install
npm run dev
```

前端默认访问 `http://localhost:5173`。API 文档属于后端开发工具，不在用户页面提供入口。

## 当前 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 服务健康检查 |
| GET | `/api/v1/teams` | 球队及当前赛事参赛信息 |
| GET | `/api/v1/teams/{team_id}` | 球队详情与有效事件 |
| GET | `/api/v1/bracket/simulation` | 基线或事件情景模拟 |
| POST | `/api/v1/predictions/match` | 按 `simulation_id + match_key` 获取数学上下文和可选 AI 解读 |
| GET/POST/PUT/DELETE | `/api/v1/events` | 赛事事件管理 |
| GET/POST | `/api/v1/events/import/*` | 导入模板与批量导入 |

模拟标准响应只保留：

```text
simulation_id
baseline_simulation_id
scenario
tournament
model
summary
representative_path
```

旧的冠军、对阵树、重新计算和按球队查询等演示接口已移除。

## 验证

```powershell
cd backend
pytest -q

cd ../frontend
npm run build
npm run lint
```

当前回归基线为后端 98 项测试通过，前端构建和静态检查通过。

## SQLite 升级策略

应用启动迁移采用有序版本注册表，并坚持“扩展、回填、切换读取、逻辑停用”：

- 只进行建表、加列、加索引和数据回填。
- 不在启动过程中删除列、修改列约束或重建大表。
- 旧数据库中的 `teams.group_name`、`teams.pot` 物理列可以继续保留，但业务代码不再读取它们。
- 新数据库直接把分组和档位写入 `tournament_teams`。
- 如果未来需要物理清理旧列，应使用带备份、行数核对、外键检查和回滚能力的独立离线工具。

详细设计见 [架构说明](docs/architecture.md)。

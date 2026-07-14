# 世界杯情景预测系统架构说明

## 1. 核心边界

系统采用“数学模型决定结果，AI 解释结果”的职责划分。

```text
赛事参赛关系 + 球队 ELO + 赛事规则
                 │
                 ▼
       ELO/泊松完整赛事模拟 ──────► 首页基线概率
                 │
        事件修正本次情景 λ
                 │
                 ▼
       情景概率 + 完整代表路径 ───► 淘汰赛推演
                 │
          用户点击具体比赛
                 │
                 ▼
       固定数学上下文 + Qwen 解读 ─► 单场详情
```

四个模块的职责如下：

1. 首页只展示无事件基线的夺冠概率，不调用 Qwen。
2. 淘汰赛页面展示基线或事件情景的完整代表路径，不调用 Qwen。
3. 单场详情读取当前模拟的数学结果，Qwen 只能补充关键因素、风险和解释步骤。
4. 事件管理维护影响情景进球期望值的变量，不直接改动 ELO。

## 2. 赛事与数据模型

`Team` 是可跨赛事复用的全局球队实体，只保存球队身份和长期基础数据。`Tournament` 保存赛事版本和规则版本，`TournamentTeam` 保存本届赛事特有的分组、档位、参赛状态和启用状态。

因此，球队存在于 `teams` 表不代表它会进入当前世界杯模拟。模拟只加载当前赛事中有效的 `TournamentTeam`。中国等球队是否出现完全由参赛关系决定。

当前资源 `backend/app/resources/tournaments/world_cup_2026.json` 的关键元数据为：

```text
status: SCENARIO
is_official: false
data_version: user-scenario-20260713-v1
rules_version: scenario-fixed-v1
source: manual_mock_data
```

这组 48 队数据是用户提供的非官方情景阵容。接口必须持续返回上述状态，界面和文档不得将它描述为 FIFA 官方名单。

## 3. 完整赛事模拟

### 3.1 输入

纯数据模拟输入包含：

- 赛事 ID、数据版本和规则版本；
- 48 支有效参赛球队及其 ELO、分组和档位；
- 主种子和迭代次数；
- 当前情景中每支球队的事件修正；
- 模型版本。

相同输入和种子必须产生相同统计结果与完整路径。每次迭代的子种子由主种子稳定派生，基线与事件情景复用相同随机序列，便于控制变量比较。

### 3.2 小组赛和淘汰赛

每次迭代都会完整模拟小组赛。小组排名至少比较积分、净胜球、进球数，并使用稳定决胜规则消除不可复现的并列。随后产生 12 个小组第一、12 个小组第二和 8 个最佳第三名。

由于当前名单不是官方抽签结果，32 强采用产品自定义的固定 `scenario-fixed-v1` 映射。后续轮次通过固定 feeder 关系连接，返回 `R32/R16/QF/SF/FINAL` 的 `16/8/4/2/1` 场比赛。每个节点都包含：

- 稳定 `match_key`；
- 主客队真实 ID 和球队信息；
- 比分与晋级球队；
- 常规时间或点球决胜标记；
- `source_slots` 和比赛顺序。

### 3.3 事件语义

事件只在泊松抽样前修改本次情景的期望进球：

- `attack_lambda_delta`：修正本队进球期望；
- `concede_lambda_delta`：修正对手面对本队时的进球期望。

修正值按比例合并并限制在安全范围内。停用、未生效、已过期或不属于当前赛事的事件会进入 `ignored_events`，不会影响模拟。旧 `attack/defense` 字段只在事件兼容解析层转换，标准接口和管理页面使用新字段。

事件解析不得更新 `Team.elo_rating`，所以情景模拟不会污染首页基线。

## 4. 概率与代表路径

同一批完整赛事迭代同时产生：

- 各队进入 32 强、16 强、八强、四强、决赛和夺冠的概率；
- `probability_leader`；
- `top3`；
- 按球队 ID 键控的夺冠概率；
- 一条完整代表路径。

概率第一名由累计夺冠次数确定。代表路径不是另外随机生成的一届比赛，也不是前端按概率拼装，而是“概率第一冠军约束下的最高似然真实样本”。

为了避免保存和全盘扫描 1000 棵完整树，模拟过程中只为每个冠军球队保存当前最高似然样本的迭代索引、子种子和对数似然，空间复杂度为 O(球队数)。统计完成后找到概率第一球队，再用其候选子种子重放一届赛事生成完整路径。

因此代表路径冠军与 `probability_leader` 一致，但这条路径仍只是一个可复现、合理的展示样本，不是唯一可能结果。

## 5. 基线、情景与缓存

`GET /api/v1/bracket/simulation` 同时服务首页和淘汰赛页面。

- 无 `event_ids`：返回当前基线。
- 带 `event_ids`：返回事件情景，并要求引用现有 `baseline_simulation_id`。
- 普通访问：复用相同上下文的当前缓存结果。
- `refresh=true`：生成新主种子并整体刷新统计和路径。

缓存上下文包含赛事、数据版本、规则版本、模型版本、迭代次数和球队输入。情景缓存还包含基线 ID 与事件内容指纹。事件 CRUD 只使相关情景缓存失效；基线不因事件管理操作而变化。

标准模拟响应为：

```text
SimulationResponse
├── simulation_id
├── baseline_simulation_id
├── scenario
│   ├── requested_event_ids
│   ├── applied_events
│   ├── ignored_events
│   └── team_impacts
├── tournament
├── model
│   ├── version
│   ├── iterations
│   ├── seed
│   └── input_fingerprint
├── summary
│   ├── probability_leader
│   ├── top3
│   ├── advancement_probs
│   └── champion_probs_by_team_id
└── representative_path
    ├── path_type
    ├── champion
    └── stages
```

Pydantic 模型禁止额外字段，旧的 `predicted_champion`、英文队名概率键、`top3_teams` 和旧顶层 `stages` 不再兼容。

## 6. 单场数学上下文与 AI 解读

用户点击比赛后，前端只提交：

```json
{
  "simulation_id": "当前模拟编号",
  "match_key": "当前比赛稳定键"
}
```

后端从缓存的模拟中解析比赛，返回两部分：

- `math`：比分、胜者、晋级方式、主客队期望进球、胜平负/晋级概率和已应用事件；
- `agent`：可选的 Qwen 解释报告。

Qwen 提示词和工具契约不允许提交比分、胜者、概率或期望进球，只允许输出关键因素、风险、连续的解释步骤和工具调用摘要。后端将步骤强制重排为 1、2、3……，不会展示步骤 0。

当密钥缺失、请求失败、超时或熔断器开启时，`agent.status` 为 `agent_unavailable`，但 `math` 必须继续完整返回。首页和赛事模拟本身不会触发 Qwen。

## 7. 前端职责

- 首页顶部冠军、Top 3 第一名和概率榜第一名都读取 `summary.probability_leader` 与同一概率集合。
- 淘汰赛树只渲染后端 `representative_path.stages`，不生成假球队、假比分或随机晋级关系。
- 对阵树使用固定自适应画布，不依赖滚轮缩放组件。
- 事件选择器使用搜索筛选抽屉和临时选择状态，只有“应用并重新模拟”触发一次情景请求。
- API 文档没有用户界面入口；开发者可直接使用 FastAPI 的开发文档地址。
- 用户可见业务文案使用中文，协议枚举和 FIFA/ELO/AI 等通用缩写只在必要处保留。

## 8. SQLite 迁移策略

SQLite 启动迁移通过 `MIGRATIONS` 有序注册表逐个执行，版本写入 `schema_migrations`。迁移遵循：

1. 扩展：建新表、加可兼容列和索引；
2. 回填：把旧数据复制到新领域结构；
3. 切换读取：业务代码改读新表；
4. 逻辑停用：停止使用旧字段，但暂不删除物理列。

旧数据库升级时，迁移会读取 `teams.group_name/pot` 回填 `tournament_teams`。新数据库的 `teams` 表不再创建这两列。应用启动期间禁止删列、修改列约束或大规模重建表；未来如需物理清理，应提供独立离线工具，并执行数据库备份、行数核对、索引重建、`foreign_key_check` 和失败回滚。

## 9. 回归要求

每次架构改动至少验证：

```powershell
cd backend
pytest -q

cd ../frontend
npm run build
npm run lint
```

关键回归覆盖基线稳定性、事件控制变量、合法晋级链、代表路径选择、缓存失效、AI 熔断、旧数据库升级和新数据库结构。

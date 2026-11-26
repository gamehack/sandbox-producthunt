# Sandbox Product Hunt｜InstaBox + DSH Agent Harness

`gamehack/sandbox-producthunt` 是原 `gamehack/producthunt` 的沙盒部署适配项目。它负责把现有 Product Hunt 研究生产流程迁移到 InstaBox，并使用 DSH Agent Harness 执行模型推理。

**原仓库 `gamehack/producthunt` 不修改。** 本项目通过固定 Git commit 的 Python package dependency 复用原仓库的业务代码，不复制、不分叉业务流程。

## 1. 架构

```text
n8n（北京时间每天 17:15）
        │
        ▼
InstaBox qjai-dsh-01（按需启动一次性 Job）
        │
        ▼
/data/opt/sandbox-producthunt/scripts/run.sh run
        │
        ├── Python：原 producthunt 项目提供的确定性业务流程
        │     ├── Product Hunt 官方 GraphQL API Top 20
        │     ├── AI 相关性筛选与 ID 完整性校验
        │     ├── 创业机会评分与候选排序
        │     ├── 官网证据收集、robots.txt 与公网 IP 校验
        │     ├── SQLite 分阶段检查点与失败续跑
        │     ├── 中文文章、标题与引用校验
        │     └── Notion 幂等写入、全文回读、READY + SHA-256
        │
        └── DSH Headless：只负责每个模型步骤
              ├── AI 相关性判断
              ├── 创业机会评分
              ├── 单产品事实调研
              ├── 文章生成
              └── 标题改写（仅在原始标题不合格时）
        │
        ▼
Notion「08 · 潜界 AI｜产品猎人日报」READY
        │
        ├── mp-publisher：继续负责微信公众号草稿
        └── cms-publisher：继续负责 CMS 草稿
```

### 职责边界

| 层 | 负责什么 | 不负责什么 |
|---|---|---|
| n8n | 17:15 定时、触发 InstaBox Job、轮询结果、失败告警 | 不执行产品研究和文章生成 |
| InstaBox | 提供隔离的按需执行环境 | 不驻留业务常驻服务 |
| DSH Headless | Agent 生命周期、模型调用、结构化推理结果 | 不负责 Product Hunt API、Notion 写入或业务状态机 |
| Python 上游包 | 所有确定性业务逻辑、校验、检查点、Notion READY 合约 | 不直接调用 DSH Web UI 或 OmniRoute |
| Notion | READY 原稿的权威交付位置 | 不负责公众号/CMS 发布 |

DSH 使用 Headless 一次性模式，不需要启动 Web 服务，也不需要发布 3080 端口。每个模型步骤由一次 `dsh --profile headless` 进程完成；进程退出后，外层 Python 流程继续执行。

## 2. 原业务逻辑保持不变

本项目将 `qjai-producthunt` 固定依赖到原仓库 commit：

`c5b354aacdfb9bee25be235c02217df76469e279`

原仓库后续提交不会自动进入本项目。需要升级时，先审查原项目变更，再单独更新本项目 `pyproject.toml` 中的 commit SHA。

保留原项目当前行为和约束：

- Product Hunt 日期按 `America/Los_Angeles` 计算，默认使用最近一个已完成的自然日。
- 通过 Product Hunt 官方 GraphQL API 获取 Top 20，不抓取 Product Hunt 网页。
- AI 相关产品类别为核心 AI、AI 增强、AI 生态；置信度至少 `0.60` 才进入后续机会评分。
- 机会评分总分 100，默认阈值 60、调研上限 5。超过阈值的产品多于 5 个时，调研全部超过阈值者；否则按分数排序调研前 5 名（因此可能包含分数不超过 60 的产品）。
- 官网证据收集遵循 HTTPS、公网 IP、robots.txt、响应大小与不跟随重定向等限制；Product Hunt API 上架信息必须明确归因，不能冒充独立核验。
- 文章引用只能使用已采集证据中的 URL；标题不超过 64 个 UTF-8 字节。
- Notion 唯一键为 `producthunt:YYYY-MM-DD`，只允许写入既定的 Notion 08 父页面。创建后必须完整回读，校验正文并追加 READY 标记和 SHA-256；已存在但不完整或被修改的页面一律 fail closed，不覆盖。
- 本项目不包含微信公众号或 CMS 发布代码。下游 `mp-publisher` 和 `cms-publisher` 继续按原约定读取 Notion READY。

## 3. InstaBox 部署目录

统一部署到：

```text
/data/opt/sandbox-producthunt/
├── .venv/                 # Python 虚拟环境
├── .env                   # 私有凭证，不进入 Git
├── data/
│   ├── producthunt.sqlite # 持久化分阶段检查点
│   └── producthunt.lock   # 单实例执行锁
├── output/YYYY-MM-DD/     # 文章 JSON / Markdown 恢复文件
├── logs/                  # 预留运行日志目录
├── scripts/
├── src/sandbox_producthunt/
└── tests/
```

使用现有 DSH HOME，不另建或覆盖 DSH 配置：

- `HOME=/data/home`
- `DSH_HOME=/data/home/.dsh`
- DSH 配置和凭证继续由现有 DSH 安装管理。

`/data` 是持久化盘。应用、虚拟环境、SQLite、文章和日志均放在 `/data/opt/sandbox-producthunt`，不写入 `/tmp`，不创建 `/data/apps`。

## 4. 部署

先确认 InstaBox 终端能够找到 `dsh`、`git` 和 Python 3.12。按当前实例环境加载路径：

```bash
export HOME=/data/home
export DSH_HOME=/data/home/.dsh
export PATH="/data/opt/npm/bin:/data/opt/bin:/data/home/.nvm/versions/node/v24.22.3/bin:$PATH"
```

首次部署：

```bash
mkdir -p /data/opt
cd /data/opt
git clone https://github.com/gamehack/sandbox-producthunt.git
cd /data/opt/sandbox-producthunt
./scripts/bootstrap.sh
```

`bootstrap.sh` 会创建 `.venv`、安装本项目及固定版本的原始业务包，并在 `.env` 不存在时从 `.env.example` 创建权限为 `600` 的模板。它不会安装或修改 DSH，不会启动常驻服务。

编辑 `/data/opt/sandbox-producthunt/.env`，至少配置：

| 环境变量 | 要求 |
|---|---|
| `PRODUCT_HUNT_TOKEN` | Product Hunt 官方 API Token |
| `PRODUCT_HUNT_COMMERCIAL_AUTHORIZED` | 明确授权后设置为 `true` |
| `NOTION_API_KEY` | 有权访问 Notion 08 父页面的 Integration Secret |
| `NOTION_PARENT_PAGE_ID` | 固定为 `4109e605-ccf8-81c4-accd-c19386b4a38d` |
| `NOTION_ENABLE_SYNC` | `true` |
| `NOTION_AUTOSYNC_AFTER_GENERATION` | `true` |

默认数据路径已经指向 `/data/opt/sandbox-producthunt`，一般不需要修改。

### DSH 模型配置

本项目不再使用原项目的 `OMNIROUTE_BASE_URL` / `OMNIROUTE_API_KEY`。模型和 Provider 由 DSH 管理，调用入口固定为 `dsh --profile headless`。

运行：

```bash
./scripts/run.sh doctor
```

`doctor` 会实际发起一次很小的 DSH Headless 模型请求，并验证 JSON 结构。它不会打印模型密钥。通过后才建议进行真实生产运行。

**凭证注意：** DSH 官方 Headless 配置默认不启用 Web 管理的本地凭证存储。Headless API Key 路由按启动环境、调用目录 `.env`、`$DSH_HOME/.env` 的顺序读取环境变量；Provider 的 `apiKeyEnv` 必须指向对应变量名。因此，Web UI 中已保存的第三方模型凭证不一定会自动被 Headless 使用。若 `doctor` 的模型连通性检查失败，应检查 Headless profile 的 Provider / model 选择，以及该 Provider 对应的 `apiKeyEnv` 环境变量；不需要登录 DeepSeek 官网账号。

本项目针对 DSH `0.2.2-rc.5` 的 Headless 协议，每次调用都显式指定 `--permission-mode read-only --approval-policy never`，并要求模型只返回结构化 JSON、不调用工具。同时应用 `config/no-tools.patch.yml` 关闭该版本内置业务无关工具与官方会话日志上传。DSH 子进程不继承 Product Hunt Token 或 Notion Secret，使用独立临时工作目录。该配置要求 Headless profile 不安装其他工具插件；read-only 并非网络隔离，事后事件校验也不能撤销已经执行的工具操作，因此生产前必须验证有效配置。运行时会检查 DSH JSON 事件流：进程退出码必须为 0、最终 `reason.kind` 必须为 `completed`，且不允许出现工具调用事件。

## 5. 手动运行

```bash
cd /data/opt/sandbox-producthunt

# 检查 DSH + 第三方模型
./scripts/run.sh doctor

# 最近一个已完成的洛杉矶自然日
./scripts/run.sh run

# 指定 Product Hunt 日期
./scripts/run.sh run --date 2026-11-25

# 只读核验 Notion READY
./scripts/run.sh check-ready --date 2026-11-25

# 从本地已校验的文章恢复 Notion 写入
./scripts/run.sh sync-notion --date 2026-11-25
```

同一时刻只允许一个生产任务持有 SQLite 目录下的 `producthunt.lock`。同一期 Notion 已经 READY 时，`run` 会返回 `already_ready`，不再重复调用模型或创建页面。

失败后可使用同一个日期重新执行 `run --date YYYY-MM-DD`。SQLite 按日期和步骤保存检查点，已完成的有效步骤会复用。若 Notion 创建结果不明确，程序 fail closed；先执行 `check-ready`，不要盲目重复 POST。`sync-notion` 只读取上游包保存并校验过的 JSON/Markdown，不会覆盖已有 Notion 页面。

## 6. n8n 调度与 InstaBox 执行

生产调度放在现有 n8n，不放在 GitHub Actions，也不在 InstaBox 创建 cron 或 systemd 服务。

建议 n8n 工作流：

1. Schedule Trigger：每天北京时间 17:15。
2. 通过 InstaBox 执行接口启动 `qjai-dsh-01` 的后台 Job。
3. Job 命令在沙盒内加载 `/data/home` 和 DSH PATH，进入 `/data/opt/sandbox-producthunt`，执行 `./scripts/run.sh run`。
4. 保存 Job ID，轮询 Job 状态；完成后读取 JSON 结果和日志。
5. 只有 `status=notion_ready` 或 `status=already_ready` 才视为本期交付成功；非零退出、超时、模型错误或 Notion 校验失败均告警。

从已配置好 InstaBox CLI 的终端进行一次性手工触发，命令形式如下：

```bash
npx instabox@latest exec --background qjai-dsh-01 -- bash -lc '
  export HOME=/data/home
  export DSH_HOME=/data/home/.dsh
  export PATH="/data/opt/npm/bin:/data/opt/bin:/data/home/.nvm/versions/node/v24.22.3/bin:$PATH"
  cd /data/opt/sandbox-producthunt
  exec ./scripts/run.sh run
'
```

该命令返回 InstaBox Job ID。n8n 应使用同一执行入口，并负责跟踪 Job ID；不应通过启动 `dsh web` 或检查 3080 端口来判断生产任务状态。

## 7. 不在本仓库实现的内容

- 不修改原 `gamehack/producthunt`。
- 不复制 Product Hunt 业务代码或改变评分、证据、文章、Notion READY 规则。
- 不启动 DSH Web 服务，不发布 3080 端口。
- 不在 InstaBox 配置常驻 systemd、cron 或 n8n。
- 不在本项目实现微信公众号/CMS 发布。
- 不把 `.env`、Token、Notion Secret、DSH Provider Key、SQLite 或真实文章产物提交到 Git。

## 8. 原版对照执行

若仅需验证原 Python 项目能否在 InstaBox 原样运行，可在私有 `.env` 配置 `OMNIROUTE_BASE_URL`、`OMNIROUTE_API_KEY` 和 `OMNIROUTE_MODEL`，然后执行：

```bash
./scripts/run.sh --runtime openai doctor
./scripts/run.sh --runtime openai check-ready --date 2026-11-25
# 以下命令会写入生产 Notion，确认原调度未并发执行后才运行：
./scripts/run.sh --runtime openai run --date 2026-11-25
```

默认仍是 DSH；原版对照模式直接使用上游 OpenAI Agents SDK，检查点使用独立 `.openai.sqlite` 文件，产物存放于 `output/openai/`。两种模式共享单实例锁和同一个 Notion READY 合约。锁仅保护本沙箱，不能协调原 GitHub Actions 或其他机器；实际生产切换必须先确认旧生产任务已结束并停止原生产调度。本项目没有自动定时生产任务。

DSH 适配器继承固定版本上游 `OpenAIAgentRuntime` 以通过其现有类型检查，覆盖全部推理方法；没有修改上游包。上游内部 run ID 仍含 `openai`，不代表 DSH 调用了 OpenAI SDK。

## 9. 验证

```bash
python -m pip install -e '.[dev]'
pytest -q
python -m compileall -q src tests
```

CI 只运行离线测试，不访问 Product Hunt API、DSH Provider 或真实 Notion。

## References

- [原 Product Hunt 业务项目](https://github.com/gamehack/producthunt)
- [DeepSeek Harness Headless 文档](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/bundle/headless)
- [DeepSeek Harness CLI 文档](https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/cli/README.md)

# Sales Agent for Feishu

飞书销售情报 Agent 的可运行 MVP。当前版本提供飞书机器人入口、线索查询、今日优先线索、来源证据展示和有效性反馈，可用 Docker 部署。

> 当前仓库没有接入自动网页研究、企业数据源或评分学习模型。线索由 CSV 导入；请勿将演示数据当作已核验的真实商机。后续可按 `LeadSource` 接口接入经过授权的数据源。

## 功能

- 飞书事件回调：`/help`、`/today`、`/company <企业名>`、`/valid <线索ID>`、`/invalid <线索ID>`
- SQLite 保存线索、信号来源、证据链接、更新时间及人工判断
- 按分数排序展示今日线索
- 可配置飞书事件校验 token；回调仅接受配置了 token 的事件
- CSV 导入，字段见 `data/leads.example.csv`

## 本地运行

需要 Python 3.11+。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --host 0.0.0.0 --port 8000
```

配置 `.env` 中的飞书应用凭证与回调校验 token。公网 HTTPS 地址设为飞书应用的事件订阅地址，路径为 `/feishu/events`。在飞书开放平台启用机器人并订阅消息接收事件。应用需具备发送消息权限，并发布到目标可见范围。

## Docker

```bash
docker build -t sales-agent-feishu .
docker run --env-file .env -p 8000:8000 -v sales-agent-data:/app/data sales-agent-feishu
```

健康检查：`GET /health`。添加线索：`POST /leads`，JSON 字段包括 `company`、`signal`、`source_name`、`source_url`、`score`、`updated_at`。初始分值需由使用者或后续评分器提供。

## CSV 导入

```bash
python import_csv.py data/leads.csv
```

## 安全与限制

- 不要提交真实凭证；使用环境变量或部署平台 Secret。
- 生产环境应使用 HTTPS、限制机器人可用群/用户，并部署可靠数据库及日志告警。
- 目前事件校验采用飞书 verification token；生产部署前应按飞书平台要求启用并验证请求签名/加密配置。
- `/today` 展示的是已录入数据库的线索，不代表系统已自动完成每日扫描。
- 人工反馈会被记录，但当前不会自动训练或调整评分模型。

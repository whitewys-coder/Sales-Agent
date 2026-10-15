# Agate Sales Agent · V3.3

每日流程：LeadContact关键词/行业及当地岗位筛选 → 按公司聚合 → 企业研究和业务判断 → 现任身份二次核验 → LeadContact邮箱补充 → 100分评分和个性化开发信 → **用户人工发送**。

本程序、ChatGPT Work云端任务和原飞书MVP是三个独立运行面，不会自动共享凭据或数据库。保持一个付费执行主体；切换前迁移完整历史和当日预算。

## 启动

Python 3.11+，标准库，无第三方依赖。复制`.env.example`为私有`.env`，设置随机`APP_TOKEN`（至少24字符）。

```bash
python3 -m sales_agent
```

默认demo模式仅用虚构数据。服务器独立研究模式需配置：

```dotenv
APP_MODE=live
LEADCONTACT_TOKEN=在本机私有环境中配置
OPENAI_API_KEY=在本机私有环境中配置
OPENAI_MODEL=账号可用且支持Responses与web_search的模型
SCHEDULE_ENABLED=true
SCHEDULE_HOUR=9
APP_TIMEZONE=Asia/Shanghai
MAIL_SYNC_ENABLED=false
```

独立OpenAI模式缺OpenAI或LeadContact配置时，真实运行明确失败，不降级为演示成功。ChatGPT订阅和会话搜索权限不等于独立OpenAI API授权。邮箱发送不需要SMTP或邮件密码。可选IMAP同步需要单独配置，默认不读取邮件；未同步的业务邮箱历史必须另行核对。

## 配置搜索

通过已鉴权的`POST /api/search-config`提交`{"payload":{...}}`。参数必须按API实际支持字段填写；不假定存在公司自由关键词接口。员工结果按公司聚合，不把返回20人当20家公司。

示例payload：

```json
{"currentTitlesOnly":true,"includeRelatedJobTitles":true,"industry":["Machinery"],"companySize":["11_50","51_200","201_500"],"location":["France"],"jobTitle":["Directeur Technique","Responsable Qualité","Directeur de Production"]}
```

本版保存单国搜索配置；轮转由运营方显式更新，不会假称已经实现完整LRU国家/行业轮转。只允许欧洲10国或东南亚6国。中国出海账户需有欧洲/美国/南美项目证据，不将个人所在国家视为项目市场。

## 核验与评分

- 公司研究不要求已知目标人、邮箱、预算或近90天新闻；合适产品/工序及具体切口才值得补联络。
- 现任核验独立于API：官网团队/任命或原始个人职业资料必须有可追溯URL、核验日期、姓名、公司和职位。API `isCurrent`仅为线索；与官网冲突保留两者，无法消除实质冲突不补邮箱。
- 100分：Trigger25、技术25、时效15、决策人15、邮箱10、人数5、战略5；分项证据、子项上限及未知0。85以上且近期Trigger合格为优先；适配但无近期Trigger可进入探索通道。
- 直客池、欧洲渠道池、东南亚渠道池分开；同质视觉/嵌入式AI原厂排除；机构不当普通直销客户。
- 企业研究先保存，补联络失败可恢复，不丢弃已经付费获取的事实。
- 个人免费邮箱、invalid、unknown/catch-all、域名冲突不列人工可发送。valid不等于送达。

## 预算与去重

日计划100积分，日硬上限200，搜索最多一页；搜索、邮箱全部计入同一SQLite账本。数据库事务在外部请求前预留；付费超时不自动重试，未决请求保留预算，同日同请求重用成功结果；免费余额失败停止付费。真实余额受充值/并发影响时费用待核，不记0。

**边界**：外部进程/ChatGPT直接调用不经过本数据库时，无法自动合并预算；必须导入其请求记录，且只保留一个付费执行主体。历史集团归属和别名仍依赖证据；使用前导入已发送/转发、拒绝、退信记录。没有历史不等于历史重复为0。

## 人工发送

工作台提供复制邮件和“登记人工已发送”。HTTP发送接口固定403，Engine发送方法固定拒绝；后台不会调用SMTP。登记保留用户说明及时间，状态`reported_sent`/`reported_forwarded`，不是邮箱送达事实，不生成虚假message_id。无回复不统一四连追信，拒绝/退信保持冻结。

接口除`/health`及静态页面外须`Authorization: Bearer <APP_TOKEN>`：

|接口|用途|
|---|---|
|GET /api/state、/api/export|账户、草稿、请求账本摘要与运行记录|
|POST /api/run|立即开始真实或演示工作流|
|POST /api/search-config|保存已审核的单国搜索参数|
|POST /api/scope|保存业务研究范围|
|POST /api/drafts/edit、/approve|人工编辑与证据复核|
|POST /api/drafts/report-sent|登记人工发送/转发及凭据说明|
|POST /api/drafts/send|始终403，禁止代发|

## 调度与后续腾讯迁移

服务每20秒检查北京时间，每天9点后最多运行一次，重启保留日期键；失败记录不冒充成功。同一DATA_DIR只允许一个服务。当前容器生命周期不保证永久在线，不能把本地进程存活当成24小时托管承诺。

腾讯部署暂不执行。以后使用本目录Dockerfile/compose.yaml，迁移完整私有数据库与当日预算、配置密钥、HTTPS及鉴权，确认唯一调度主体后切换；先停旧执行器再启新调度。不要把私有`.env`或客户数据库提交到GitHub。

## 验证

```bash
python3 -m unittest discover -s tests -v
```

覆盖：全流程串联（替代网络）、现任API冲突与官网消歧、同名公司冲突、预算预留/超时/重启/缓存、85分与探索通道、HTTP鉴权、硬禁代发、人工发送登记、拒绝冻结、调度重启幂等。测试替身不代表独立OpenAI真实付费端点已验收。

## 当前ChatGPT环境协同研究（native backend）

`RESEARCH_BACKEND=native`可复用当前ChatGPT Work的研究与文案能力，不要求独立OpenAI Key。程序完成LeadContact发现后只保存`native_research_queue`，状态为`awaiting_native_research`，**不冒称已完成企业研究**。当前Work任务读取此队列，用其可用研究工具核验官网、场景、现任身份和评分依据，准备正文，再通过`sales_agent.native_bridge.complete`写回。

桥接函数要求`evidence_reviewed=True`、实际检索URL、结构化企业资料和现任证据；它重新执行企业门槛、历史去重、现任校验，再用同一LeadContact预算客户端查询邮箱、评分和保存人工发送草稿。调用方对实际阅读来源、业务假设及文案真实性负责。它不是把任意JSON当作自动核实结果的公共端点。

native模式必须有可访问同一文件/数据库环境的Work任务持续接力；没有接力时只停留在队列，不会独立完成整轮。当前实例禁用第二套本地定时器，沿用既有Work日任务，避免两套调度同时扣费。腾讯独立部署时可选择OpenAI后端，或另行实现经过验证的研究服务接力。

## 中断恢复（当前Work运行方式）

Work为唯一09:00调度，本地SCHEDULE_ENABLED=false。每轮先执行只读恢复检查：

```bash
python -m sales_agent.recovery --database /absolute/private/live.sqlite3 --backup /absolute/private/checkpoints/latest.sqlite3
```

命令不联网、不扣积分，不会创建缺失原账本。SQLite在线备份包含已提交WAL事务，权限0600。先续pending_companies，再复核unresolved_reviews；空队列不等于准入或写回完成。unknown/reserved请求禁止自动重试。逐家公司结论、队列和运行计数同事务提交；付费前保存reviewed_copy与核验来源。

本地备份受会话生命周期影响，每轮还需持久保存客户主库、台账及私有恢复包。私有备份不提交GitHub。重建环境后凭据或账本缺失则停止付费，不创建空库继续。当前方案不保证24小时托管。

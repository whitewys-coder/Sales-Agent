# 运行、持久状态与自动调度

## 部件关系

Skill提供作业规范、参考和可执行核心；Work任务在09:00 Asia/Shanghai触发；LeadContact提供候选/联系路径；Work研究工具负责企业判断和文案；SQLite负责请求预留与结果，Library保留用户长期台账/主库。缺任一环节，报告具体缺口，不用演示替代真实成功。

当前模式为native协同，不要求独立OpenAI Key；独立腾讯部署选择openai后端时需配置自己的模型/key。当前会话环境不保证永远在线，同一运行数据库只留一个付费执行主体。禁止本地与Work双调度。

## 当前实例定位（非凭据）

- 私有环境配置：`/workspace/scratch/4b0c31530046/Sales-Agent/sales-agent-product/.env`。
- 预算/客户运行库：`/workspace/scratch/4b0c31530046/sales-agent-runtime/data/live.sqlite3`。
- 源码已保存：`whitewys-coder/Sales-Agent`，分支`codex/v33-leadcontact-manual-outreach`，当前集成基线提交`9b38ad843940624a6e4311204d95a878438f0872`（后续以仓库实际更新为准）。
- 唯一Work任务ID：`6ab360c30be88191abfe9fad9338c0b5`，每日09:00 Asia/Shanghai。
- 唯一运行台账：`libfile_d6dcd520c1648191b34675dff5ccd1b0`。
- 当前统一主库：`libfile_0d02093a9c948191b0f5ead2f9547203`，标题`Xeroptix_客户资料统一主库_整合SalesAgent_截至2026-10-15.xlsx`；读取当前版本，不凭记忆推断内容。Library项目操作按Library技能执行；Excel字节处理按Spreadsheets技能。

路径仅是定位信息，不是永久托管承诺。若当前环境丢失，先恢复代码、私有凭据、主库历史、当天已扣/未决请求；不能直接生成空库开始付费。不要将.env、客户库或邮件提交Git。

## bundled scripts

`scripts/runtime/sales_agent`包含预算客户端、规则、评分、验证、桥接和存储；源自上述V3.3代码，未包含.env/客户数据/凭据/UI服务。`scripts/run.py`是轻量入口：

```bash
python <skill>/scripts/run.py preflight --env <private-env>
python <skill>/scripts/run.py dry-run
python <skill>/scripts/run.py discover --env <private-env>
python <skill>/scripts/run.py queue --env <private-env>
python <skill>/scripts/run.py finalize --env <private-env> --input <private-review.json>
```

preflight/dry-run不联网、不扣费。discover最多1页且仅使用已审核settings.search_payload，finalize可能查1次邮箱，须在已授权日预算内。余额接口免费，但必须使用统一客户端。`XEROPTIX_RUNTIME_ENV`可指定私有.env，`--env`优先。

## reviewed JSON

由实际完成Work研究与文案的执行者填写，不是自动生成虚假证据的模板。核心：

- account：company、domain、group_domain、country、pool、company_role、employees、in_scope、excluded、technical_fit、fit_reason、trigger、trigger_date、recent_trigger_verified、why_now、sources、score_evidence。
- sources：每项url、kind、claim、publisher；kind可company/product/scene/group/employees/outbound_market/contact/official_trigger。URL必须已实际读取，字段事实须被该URL支持。
- score_evidence：trigger 1项，technical_fit 3项，decision_maker 5项，public_email 4项，strategic 3项；每项points、reason、urls，顺序和上限见scoring。未知0，不虚构来源。邮箱4项由实际API查询后补入。
- person：fullName、companyName、linkedinUrl、title及API experience原记录。
- employment_evidence：name、company、title、current布尔、kind（official_contact/official_appointment/personal_profile）、url、checked_date（实际核验当日）。官网证据必须匹配公司域名；个人资料须匹配同一规范LinkedIn路径。真实离职冲突不能用最新抓取时间掩盖。
- retrieved_urls：实际读取URL数组；不是“想查”的链接。
- copy：subject和body（不含签名），具体事实、任务问题及假设措辞已核。
- evidence_reviewed：必须为true，表示执行者确实完成来源审阅，不是形式按钮。

桥接会重新检查市场、企业角色、官网证据、历史去重、现任、预算和邮箱；程序检查URL/结构不证明网页语义，Work执行者仍须真实阅读来源。当前程序仅接受同公司/已核集团域名邮箱，其他域名需补归属证据后审阅，不能绕过。

## 状态和持久写回

先恢复Library历史到运行库，再付费。按集团/法人业务线/人员LinkedIn/邮箱多层去重，不能仅个人URL当全局键。已发/转发/拒绝/退信/交接优先于旧draft；冲突保留来源及日期，不用新草稿覆盖历史。

完成本地写回后，用Library技能同ID版本保护更新台账/主库。版本冲突重读合并，不移除版本保护硬覆盖。技能和代码是规则载体，不保存完整私人客户列表；客户状态不靠每天把CSV全文贴回聊天维持。

原任务启用且Skill可读后可更新其提示词引用此技能，保持原ID/时区/时间，不新建重复任务。执行结果必须分：触发请求受理、任务启动、发现入队、研究完成、包保存、台账写回、用户收到报告；逐层有证据才声称成功。

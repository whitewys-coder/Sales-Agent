# LeadContact与预算

## 接口和参数

服务根地址`https://api.leadcontact.ai`，Bearer凭据仅从私有环境取。不要将Token写入Skill、任务、日志、报告、仓库或示例。

|动作|方法/路径|计费参考|
|---|---|---|
|余额|GET /api/rest/credits|免费|
|单页人员搜索|POST /api/rest/employess/query/advanced|5/返回条，最多20条，预留100|
|邮箱|POST /api/rest/email/query|10/次|
|单人档案|GET /api/rest/employess/query/linkedin?linkedin_url=…|5/次；当前脚本未封装，勿绕账本直接调用|

`employess`是接口原拼写，不改成employees。参考费用来自已提供说明和当次实测，不保证服务永远不改价；余额/单价异常立即停止新付费并报告。禁止电话接口。

员工请求示例（不含秘密）：
```json
{"currentTitlesOnly":true,"includeRelatedJobTitles":true,"industry":["Machinery"],"companySize":["11_50","51_200","201_500"],"location":["France"],"jobTitle":["Directeur Technique","Responsable Qualité","Directeur de Production"]}
```
只允许实际支持字段：currentTitlesOnly、includeRelatedJobTitles、industry、companySize、location、jobTitle、company、seniority。company是企业名筛选，不假定可任意全文关键词搜索。HTTP200不证明所有筛选生效；核实际返回样本和现任状态。

行业8枚举：Industrial Automation / Machinery / Electrical & Electronic Manufacturing / Automotive / Sporting Goods / Health, Wellness & Fitness / Plastics / Mining & Metals。未经验证枚举不当已支持。
规模枚举：1_10、11_50、51_200、201_500、501_1000、1001_5000、5001_10000、10001。接口区间不等于最终集团人数。
单国轮转建议沿用已记录的成功运行时间；实际运行程序尚未自动实现完整LRU，不声称已自动轮换。无已审核预设则先准备配置，不盲目扣费。仅既定市场内轮换，低产不扩国家救场。

## 返回处理

搜索data.employees里的title、companyName、fullName、linkedinUrl、experience是线索，不能把title当jobTitle字段读取。API现任开关不能代替二次核验；companySize/person location不证明集团规模/工厂地区。
邮箱请求`{"profileUrl":"https://www.linkedin.com/in/..."}`；检查全部data.sources，不假定第一项一定可用；核email、valid、personal及企业归属。当前脚本只自动接受已核官网域名或集团域名；子公司其他域名须先补实际归属证据再审核，不能按猜测接受。

## 每日账本及停止条件

1. 按北京时间自然日合并搜索与补邮箱等费用，计划100、硬限200。1页搜索耗100后可用硬限剩余额度补合格对象，不是每天必须花满。
2. 付费前读取免费余额，SQLite事务预留最坏费用并保存请求键；禁止并发请求和第二页。
3. 超时/业务异常费用可能已发生，不自动重试；保留unknown和预算预留，先人工对账。成功响应先缓存，再读取余额结算；余额后读失败也不重复付费。
4. 前后余额可信差值为实测费用；余额增长/并发干扰则费用待核，估算独立列，不记0。实际费用高于预留或影响硬限就停止。
5. 同日同请求复用成功响应，不新扣费。跨天保留历史而非把旧命中算新增；过期邮箱结果标日期。
6. 不明余额、账本遗失、多个执行器、连接失败、超硬限：停止付费并交具体缺口，不能靠新文件或换进程绕过。

免费余额也只通过统一客户端调用。单人档案未在当前预算客户端封装时，不直接curl；先扩展同一事务预留方法并测试，再使用。

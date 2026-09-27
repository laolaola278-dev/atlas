# Atlas 第一轮交付验收报告

> **当前角色**：交付负责人 / 测试架构师
> **本章产出**：第一轮规划交付的范围、证据、修复记录和下一轮入口
> **依赖的上游产出**：`docs/design/architecture.md`、`docs/adr/ADR-001.md`–`ADR-032.md`、`plan/batches.jsonl`、`plan/milestones.md`、`plan/risks.md`

## 1. 交付结论

第一轮规划交付已完成并通过自动结构门禁；业务代码、目标硬件基准、临床阈值审批和监管原文核验尚未开始，不将本报告误读为项目整体完成。

| 项目 | 结果 | 证据 |
|---|---:|---|
| 架构文档 | 1 份，40 条 FMEA，5 类必需图 | `docs/design/architecture.md` |
| ADR | 32/32 | `docs/adr/ADR-001.md`–`ADR-032.md` |
| 实施批次 | 384 条 | `plan/batches.jsonl` |
| 阶段 LOC | P0–P8 合计 560,000 | `plan/milestones.md` |
| 生产/测试 LOC | 350,000 / 210,000 | `plan/batches.jsonl` |
| 风险登记 | 40 条 | `plan/risks.md` |
| 合规材料 | 等保三级、密评矩阵 | `docs/compliance/` |
| 工具设计 | `locaudit`、`phi-scan` | `tools/` |
| 结构门禁 | PASS | `python plan/verify_first_round.py` |

## 2. 已执行验证

```text
python plan/verify_first_round.py
PASS: Atlas first-round planning verification
ADR files: 32
Batch records: 384
Phase LOC: P0=28000, P1=86000, P2=60000, P3=106000, P4=94000, P5=24000, P6=66000, P7=76000, P8=20000
Total LOC: 560000
```

附加检查：

- 384 条 JSONL 全部 UTF-8 解析成功；ID 连续、依赖只引用更小 ID、DAG 无环。
- 单批 LOC 全部在 800–2,500；`production_loc + test_loc == loc_target`。
- 阶段 LOC 与附件 §9 精确一致；生产/测试分别合计 350,000/210,000。
- 32 个 ADR 主题、必需章节、代码围栏、验证标记和编号通过检查。
- 架构文档包含拓扑、数据流、部署、数据不出院边界和 HITL 状态机；FMEA 40 条。
- 风险条目 40 条；里程碑覆盖 P0–P8 与 MP-01–MP-08。
- 全部文本交付物 UTF-8；Markdown 围栏成对；禁用占位词在正文门禁中为 0。

## 3. 安全复核修正

1. 将架构抢救分支改为 `EMERGENCY_PENDING_CONFIRMATION → EMERGENCY_RECORDED/UNKNOWN → POST_REVIEW_REQUIRED → RECONCILIATION_CONFIRMED/CORRECTION_REQUIRED`，删除回到普通 `APPROVED`/`WRITEBACK_PENDING` 的路径，防止破窗后重复执行普通建议。
2. 在 ADR-001 明确状态机是写回资格投影，并要求抢救状态保持独立；ADR-002 和里程碑同步采用独立紧急链。
3. 修正容量与统计算例：文书容量改为独立的 `10,000 份/小时` 模型，P95 只作为上界而不是 Little 定律均值；多院区设备点频按每台 10 点/秒重算；100 万并发检索按旅程顺序、旅程并发和单个请求三种单位分开计算；FHIR 最低实例数改为 47 台。
4. 外部法规、标准、市场规模、临床参数、SM4-GCM 候选模式和 7 年证据保留均保留 `[待验证]`，没有把附件陈述伪装成已核验事实。
5. 数据不出院边界删除院外模型数据流；签核时延恢复为“加载+提交”端到端 P99；急诊全站故障单独保留 60 秒受保护路径。
6. 批次已从重复模板改写为 384 条语义条目，生产/测试仍精确为 350,000/210,000。形式校验不能替代临床与容量评审。

## 4. 本轮未完成项

- Go 业务服务、数据库迁移、前端和部署清单尚未实现；当前环境没有 Go 工具链。
- 尚未运行官方 FHIR Validator、Testcontainers、Playwright、压测机、混沌、HSM 或目标信创环境。
- 尚未获得临床治理委员会对规则、阈值、模板、评测集和破窗时限的批准。
- 附件中的 2026 政策、标准、处罚数字、市场规模、医保“两库”规模及 MAC 绑定要求仍需法务/合规从正式原文核验。
- `phi-scan` 和 `locaudit` 已有 P0 实现与单元测试，但两个扫描器源文件仍超过 800 行，重复块门禁也尚未全绿；560,000 行手写目标尚未达到。

## 5. 下一轮投喂顺序

按 `plan/batches.jsonl` 和 `plan/p0-execution.md`，先执行：

1. `ATLAS-P0-0001`：公共错误码、资源引用与契约版本。
2. `ATLAS-P0-0002`：HITL protobuf 与审批证明类型边界。
3. `ATLAS-P0-0005`：普通与抢救状态机穷举。
4. `ATLAS-P0-0015`：locaudit 计数口径与批次对账。
5. `ATLAS-P0-0016`：phi-scan 规则、掩码与失败关闭。
6. `ATLAS-P0-0017`：CI 工作流与契约检查入口。

进入业务实现前，必须安装并核验 Go 工具链，且不得用扫描器通过替代临床安全门禁。

# Atlas P0-P8 需求追踪矩阵

> 本矩阵只承认**可在本仓库测量到的证据**。所有数字由 `tools/evidence/traceability.py` 从
> `plan/batches.jsonl` 与磁盘上的真实文件重新计算，产物为
> `docs/requirements/traceability-matrix.json`（生成时间 2026-09-27T10:48:01Z）。
> 计划里的 `production_loc`/`test_loc` 是**目标值**，不是测量值；测量值以矩阵 JSON 为准。

## 状态定义

- **已验证**：实现与自动化测试都存在，并且在本环境实际执行通过（附命令与退出码）。
- **部分验证**：阶段内只有部分能力有可执行证据。
- **未验证**：没有足够证据认定已经完成。
- **外部验收**：需要目标部署环境或临床、合规、法务责任人验收。

## 测量基线（384 个计划批次）

| 阶段 | 批次 | 声明产出齐全 | 部分缺失 | 完全缺失 | 缺失文件数 | 实测 LOC | 计划 LOC |
|---|---|---|---|---|---|---|---|
| P0 | 20 | 20 | 0 | 0 | 0 | 2,752 | 28,000 |
| P1 | 58 | 0 | 0 | 58 | 174 | 0 | 86,000 |
| P2 | 40 | 0 | 0 | 40 | 120 | 0 | 60,000 |
| P3 | 72 | 0 | 0 | 72 | 216 | 0 | 106,000 |
| P4 | 64 | 18 | 8 | 38 | 122 | 19,962 | 94,000 |
| P5 | 16 | 0 | 0 | 16 | 48 | 0 | 24,000 |
| P6 | 44 | 0 | 0 | 44 | 132 | 0 | 66,000 |
| P7 | 50 | 0 | 0 | 50 | 150 | 0 | 76,000 |
| P8 | 20 | 0 | 0 | 20 | 60 | 0 | 20,000 |
| **合计** | **384** | **38** | **8** | **338** | **1,022** | **22,714** | **560,000** |

实测代码量占计划量的 **4.1%**。已有文件的模块只有四个：
`atlas-skeleton`（20 批）、`atlas-forms`（12 批）、`atlas-workflow`（11 批）、`atlas-schedule`（3 批）。

### 撤回的完成声明

以下 8 个批次此前声明 `status=complete`/`verified=true`/`completed=true`，但声明产出未全部落盘，
或声明行数与 `loc_target` 不自洽。已改为 `status=incomplete`、`verified=false`，
删除伪造的 `production_loc`/`test_loc`，并写入实测行数与撤回理由：

| 批次 | 证据状态 | 原声明行数 | 实测行数 / 目标 |
|---|---|---|---|
| ATLAS-P4-0236 | 文件齐全但行数自洽性失败 | 217 + 349 = 566 | 743 / 1,469 |
| ATLAS-P4-0241 | 部分缺失 | 918 + 550 = 1,468 | 696 / 1,469 |
| ATLAS-P4-0242 | 部分缺失 | 918 + 550 = 1,468 | 676 / 1,469 |
| ATLAS-P4-0244 | 部分缺失 | 918 + 550 = 1,468 | 584 / 1,469 |
| ATLAS-P4-0245 | 部分缺失 | 918 + 550 = 1,468 | 696 / 1,469 |
| ATLAS-P4-0246 | 部分缺失 | 918 + 550 = 1,468 | 767 / 1,469 |
| ATLAS-P4-0247 | 部分缺失 | 918 + 550 = 1,468 | 751 / 1,469 |
| ATLAS-P4-0248 | 部分缺失 | 918 + 550 = 1,468 | 850 / 1,469 |

## 阶段追踪矩阵

| 阶段 | 原始范围 | 已执行的可验证证据 | 尚缺证据 | 状态 |
|---|---|---|---|---|
| P0 | 工程、契约、HITL、审计、隐私、PHI 扫描、CI | 规划门禁 `python -B plan/verify_first_round.py` PASS（exit 0）；CI Python 模块清单 291 tests OK（exit 0）；PHI 门禁 `--fail-on blocked` exit 0，blocked=0 / review=948 / files=332；P0 证据索引 5 行校验通过；工作区 164 个临时扫描产物与 11 个临时脚本已移出仓库 | Go 工具链在本环境不可用（`go` 不在 PATH），`go test -race -cover ./...` 未在本环境执行；独立 CI runner 未重跑；制品与回滚未验证 | 部分验证 |
| P1 | FHIR、术语、EMPI | 七阶段纵切可执行：`python -B tools/evidence/fhir_slice_acceptance.py` exit 0，证据见 `docs/evidence/p1/fhir-vertical-slice.json`；`internal.workflow.test_slice` 9 项测试通过 | 官方 HAPI Validator 未真实执行（仓库内无任何 HAPI 二进制/jar）；计划内 58 个 P1 批次产出 0 落盘（`services/atlas-fhir/*.go`、`api/atlas-fhir/*.proto` 全部缺失）；EMPI 未开始 | 部分验证 |
| P2 | HL7、DICOM、实时生理数据 | 设计与里程碑文档 | 接入实现、一致性验证、重放与异常处理证据（40 批次 0 落盘） | 未验证 |
| P3 | CDSS、确定性规则、HITL、证据链 | `internal.hitl` 与状态机测试在 CI 清单内通过；双人复核 + 提交在纵切中实际执行 | 临床规则包、属性测试、模糊测试、专家盲审、破窗演练（72 批次 0 落盘） | 部分验证 |
| P4 | 文书、医保、排班、表单、工作流 | 18 批次产出齐全、8 批次部分落盘，实测 19,962 行；`atlas-workflow` 的 `audit_event_id` 消费方由 `internal/workflow/slice.py` 实现并测试 | Go 测试未在本环境执行；医保接口、跨服务端到端测试；38 批次 0 落盘 | 部分验证 |
| P5 | 临床评测、漂移监控、强制停用、回滚 | 设计与里程碑文档 | 评测集、阈值、漂移告警、停用与回滚演练（16 批次 0 落盘） | 未验证 |
| P6 | 审计、隐私、同意撤回、留存 | 追加式哈希链在纵切中实际写入并校验（5 事件，`log.verify()` 通过）；持久化重载幂等性已回归 | 法律确认、紧急访问与离线凭证演练、WORM 落地（44 批次 0 落盘） | 部分验证 / 外部验收 |
| P7 | 医生工作站、审核台、SDK、信创交付 | 设计与里程碑文档 | 可部署产品、SDK 兼容性、目标环境验收（50 批次 0 落盘） | 未验证 |
| P8 | 性能、安全、混沌、恢复、发布 | 性能与合规规划文档 | P50/P95/P99、越权、PHI 泄漏、混沌、恢复、SBOM、签名与发布包（20 批次 0 落盘） | 未验证 |

## 本轮修复的两个真实缺陷

1. **`internal/contract/errors.py` 语法错误**（第 126、127 行字符串字面量未闭合）。
   该文件是全部契约模块的公共依赖，任何 `import internal.*` 都会失败，
   因此 CI 的 Python 门禁在修复前**不可能通过**。已修复并由 291 项测试覆盖。
2. **`internal/audit/file.py` 的 `_load()` 在回放时挂着持久化 sink**，
   导致每次打开审计文件都把全部历史再写一遍（5 行 → 10 行），
   第二次重启即因 `audit-sequence-invalid` fail-closed 而无法启动。
   已改为回放完成后再挂载 sink，并新增 `test_repeated_reload_does_not_rewrite_history` 回归。

## P1 纵切决策

选择 **FHIR**，暂不先做 EMPI。FHIR 可以复用现有 contract、terminology 和 HITL 基础。

### FHIR 最低验收范围与实测结果

| 验收项 | 实测结果 |
|---|---|
| 接受带 `synthetic=true` 的 transaction Bundle | `stage_bundle` 通过，返回 2 个 entry 引用 |
| 拒绝非法 Bundle 类型 / 空 Bundle | `bundle-type-invalid`、`bundle-empty` |
| 拒绝缺失 profile、非法引用、过期术语 | `profile-not-declared`、`patient-reference-missing`、`terminology-release-expired` |
| 写入前运行官方 FHIR Validator | **未达成**：仓库内没有 HAPI 二进制，`require_official()` 只是对外部官方结果记录的 fail-closed 校验 |
| Validator 不可用/未知结果 fail-closed | `validator-result-unknown`、`validator-not-official`、`validator-digest-mismatch`、`validator-outcome-rejected` |
| 记录 validator 版本、profile 摘要、结果摘要与审计关联 ID | `fhir_validation_result` + `AuditEvent.payload_digest` + `audit_event_id` |
| fixture 覆盖有效样例与各类失败 | `testdata/fhir/synthetic/` 5 个夹具全部被测试引用 |

## P0 收口清单

- [x] 建立 P0-P8 需求追踪矩阵（可重复生成，产物已入库）。
- [x] 分类根目录扫描 JSON：164 个临时产物移入 `E:\hds(js)\look\_scratch\atlas-transient\`，11 个临时脚本移入 `_scratch\atlas-scripts\`，仓库根只保留 8 个正式文件。
- [x] 完善 `.gitignore` 的扫描中间文件规则。
- [x] 规划门禁、PHI 门禁、Python 测试门禁、P0 证据索引在本环境全部 exit 0。
- [x] 建立 Git 基线提交：`535f1aa`（root-commit，339 files，58,560 insertions），提交后 `git status --porcelain` 为空。
- [x] P1 证据索引带 SHA-256 与门禁退出码：`docs/evidence/p1/index.json`（14 个工件，5 条门禁全部 exit 0）。
- [ ] 在独立 CI runner 重跑测试和扫描（本环境无 runner）。
- [ ] 在装有 Go 1.24 工具链的环境执行 `go test -race -cover ./...` 与 `gofmt -l`。
- [ ] 制品签名、部署包与回滚包验证。

## 后续顺序

1. 在具备 Go 工具链的环境补齐 Go 侧回归，并把结果写入本矩阵。
2. 接入真实官方 FHIR Validator（HAPI），替换当前的合成官方结果记录。
3. 按计划补齐 P1 的 58 个批次产出，或修订计划使其与实际交付一致。
4. 建立临床规则评审、属性测试与回归门禁（P3）。
5. 在目标环境执行 P50、P95、P99 基准（P8）。
6. 执行越权、PHI 泄漏、混沌与恢复演练（P6/P8）。
7. 生成 SBOM、签名制品、部署包、回滚包与版本标签（P8）。

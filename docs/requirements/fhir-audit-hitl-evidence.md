# FHIR → Audit → HITL 证据记录

本记录只写**已在本仓库实际执行**的结果。执行命令与退出码见每一节。

## 已确认（有可执行证据）

| 事实 | 证据 |
|---|---|
| FHIR 响应契约包含 `audit_event_id` | `api/proto/atlas/v1/fhir.proto:43-47` |
| HITL Review/Commit 契约包含 `audit_event_id` | `api/proto/atlas/v1/hitl.proto:77`、`:159` |
| HITL 侧真实生成点 | `internal/hitl/audited.py:37`（`_event`）与 `:130`（`append_actor_event`），格式 `{suggestion_id}-{operation}-{sequence}` |
| FHIR 阶段真实生成点 | `internal/workflow/slice.py` 的 `stage_audit()`，格式 `fhir-validate-{resource_id}-{sequence}` |
| Workflow 消费 `audit_event_id` | `internal/workflow/slice.py` 的 `SliceWorkflow.open_task()`：缺失→`workflow-audit-event-missing`，查不到→`workflow-audit-event-unknown`，资源或摘要不符→`workflow-audit-event-mismatch`，随后 `log.verify()` |
| 同一个 ID 贯穿四段 | `FhirResourceResponse` / `WorkflowTask` / `ReviewReceipt` / `CommitResponse` 四处相等，实测值 `fhir-validate-observation-synthetic-1` |
| 审计链保存 `event_hash` 与 `payload_digest` | `internal/audit/chain.py`；纵切实测 5 个事件，`verify()` 通过 |
| `to_fhir_audit_event()` 映射 | 纵切实测投影 `resourceType=AuditEvent`、`id=fhir-validate-observation-synthetic-1`、`entityDigest=1253cd4d...be7b` |
| 端到端路线 Bundle → Gate → Validator → AuditEvent → Workflow → HITL Review → HITL Commit | `python -B tools/evidence/fhir_slice_acceptance.py` → exit 0 |
| 持久化与重启 | `AuditFile` 连续两次重载行数不变（5 → 5 → 5），重启后的 `ReviewService` 恢复 `suggestion-synthetic` 为 `WRITEBACK_COMMITTED` |
| **官方 HAPI Validator 真实执行** | `validator_cli.jar` 6.10.4（Git# 1b90fb13f77b，jar SHA-256 `1106b9d5…d653cc`）在 Temurin JDK 21.0.12.1 上以子进程实际运行，解析其 OperationOutcome 并生成 `require_official()` 接受的官方记录 || **标准合成测试集** | HL7 官方 R4 v4.0.1 示例 6 个，逐文件 SHA-256 固定，许可与来源见 `testdata/fhir/r4-examples/README.md` |
| 官方 Validator 正向结果 | 5 个官方示例 pass（0 error），`require_official()` 接受 || 官方 Validator 负向结果 | `practitioner-example.json` 被官方引擎拒绝（2 error），门禁以 `validator-outcome-failed` 拒绝；派生负向夹具 `r4-observation-invalid-status.json` 同样被拒绝 || 引擎缺失时 fail-closed | 无 jar / 无 JRE / 摘要不符 / 超时 / 输出缺失 / 输出损坏 → `validator-engine-unavailable`、`validator-jar-digest-mismatch`、`validator-engine-timeout`、`validator-output-missing`、`validator-output-corrupt` |
执行产物：`docs/evidence/p1/fhir-vertical-slice.json`、`docs/evidence/p1/fhir-vertical-slice.log`、
`docs/evidence/p1/fhir-official-validation.json`、`docs/evidence/p1/fhir-official-validation.log`、
`docs/evidence/p1/fhir-validator-provenance.json`。
单元回归：`python -B -m unittest internal.workflow.test_slice` → 9 tests OK；
`python -B -m unittest internal.contract.test_hapi_validator` → 无引擎时 7 pass / 3 skipped，
配置真实引擎后 **10 tests OK（97.7s，含官方引擎实跑）**。

## fail-closed 实测（验收脚本逐条执行，均不追加成功事件）

| 分支 | 稳定错误码 |
|---|---|
| 无官方 Validator 结果记录 | `validator-result-unknown` |
| 结果记录不是官方引擎 | `validator-not-official` |
| 结果摘要与资源摘要不符 | `validator-digest-mismatch` |
| Bundle 不是 transaction | `bundle-type-invalid` |
| Gate 发现 purposeCode 缺失 | `purpose-missing` |
| Workflow 未拿到 `audit_event_id` | `workflow-audit-event-missing` |
| `audit_event_id` 不在链上 | `workflow-audit-event-unknown` |
| `audit_event_id` 与资源/摘要不符 | `workflow-audit-event-mismatch` |
| 未评审就提交 | `workflow-task-state-invalid` |

## 仍缺失证据

- **纵切内尚未使用真实引擎**：`run_vertical_slice()` 已支持 `official_engine=True`（调用
  `validate_payload()` 实跑官方引擎），但默认仍使用 `official_record()` 构造的官方形状记录。
  原因是 Atlas 合成夹具把来源证明字段（`synthetic`、`actorId`、`whyCode`、`purposeCode`）放在资源根上，
  并声明 `example.invalid` 的 profile，官方引擎会对其报结构性错误。
  统一两条轨道需要把 FHIR 负载与 Atlas 来源信封分离，这是下一步的第一项。
- **jar 的 GPG 签名未验证**：官方发布了 `validator_cli.jar.asc`，但本环境没有 gpg，
  目前只固定了 jar 的 SHA-256。
- **Proto 服务端实现**：`api/gen` 不存在，`FhirValidationService` 与 `HitlService` 只有 proto 定义，
  没有生成桩，也没有返回 `audit_event_id` 的服务实现。Python 侧的等价物是 `ReviewService` 与 `SliceWorkflow`。
- **Go 侧 Workflow 消费**：`services/atlas-workflow/*.go` 中没有任何 `audit_event_id` 引用；
  当前唯一的消费方是本轮新增的 Python `internal/workflow/slice.py`。
- 本环境无 Go 工具链，Go 测试与 `gofmt` 未执行。

## 下一步

1. 接入真实 HAPI Validator（进程或容器），把官方结果记录落盘并由 `require_official()` 校验其摘要。
2. 生成 proto 桩，让 `FhirValidationService` 与 `HitlService` 返回链上真实的 `audit_event_id`。
3. 让 Go 侧 `atlas-workflow` 消费同一个 `audit_event_id`，并补跨语言一致性测试。

# Atlas API Contract Surface

> **当前角色**：互操作架构师 / 平台契约负责人  
> **本章产出**：P0 protobuf、OpenAPI、AsyncAPI 与 CUE 策略契约索引  
> **依赖的上游产出**：`plan/_contract.md`、ADR-001、ADR-004、ADR-014、ADR-015

| 契约 | 作用 | 关键安全约束 |
|---|---|---|
| `proto/atlas/v1/common.proto` | 资源、用途、来源、错误和分页信封 | ID 不进入普通日志；`why` 来自业务上下文 |
| `proto/atlas/v1/hitl.proto` | 建议、审核、审批证明和受控写回意图 | `ApprovalProof` 单次、短时、绑定患者/动作/版本 |
| `proto/atlas/v1/fhir.proto` | FHIR 资源引用和校验结果 | Profile、术语和资源摘要不可变 |
| `proto/atlas/v1/audit.proto` | 审计事件、链根和第三方验证 | 规范编码、序列和前序哈希必须固定 |
| `proto/atlas/v1/consent.proto` | 同意状态与 ABAC 访问决策 | 未知状态默认拒绝，紧急访问单独留痕 |
| `openapi/atlas-v1.yaml` | 医院内部 HTTP API | 这是交换契约，不是绕过 HITL 的授权入口 |
| `asyncapi/atlas-events.yaml` | 事件信封和 at-least-once 消费约定 | 消费者必须按事件 ID 幂等，不能信任重放 |
| `cue/atlas-policy.cue` | 最小策略词汇 | 缺策略、未知字段和上下文不全时 fail-closed |

当前只冻结契约，不包含生成的 Go/Python/Java stub；生成物必须单独统计。下一轮使用 Buf、CUE、OpenAPI/AsyncAPI 校验器和官方 FHIR Validator 在目标环境执行正式门禁。

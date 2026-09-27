# Atlas P0 执行细化

> **当前角色**：Go 平台负责人 / 测试架构师 / 临床安全负责人
> **本章产出**：把 P0 批次逻辑描述转换为下一轮可执行的文件白名单与验收顺序
> **依赖的上游产出**：`plan/batches.jsonl`、`plan/milestones.md`、`docs/adr/ADR-001.md`、`docs/adr/ADR-014.md`

## 1. P0 交付边界

P0 只建立契约、构建、测试和安全门禁，不实现临床业务规则。所有 P0 文件必须能被干净检出、格式化、静态检查和测试；Go 工具链在当前环境未安装，工具链安装与版本验证列为下一轮环境前置，不伪造编译结果。

```text
api/proto/atlas/v1/
  common.proto
  hitl.proto
  fhir.proto
  audit.proto
  consent.proto
api/openapi/atlas-v1.yaml
api/asyncapi/atlas-events.yaml
api/cue/atlas-policy.cue
cmd/atlas-skeleton/main.go
internal/contract/
internal/hitl/state/
internal/audit/
internal/privacy/
tools/locaudit/
tools/phi-scan/
.github/workflows/ci.yaml
Makefile
go.mod
```

## 2. 批次到文件映射

| 批次 | 文件白名单 | 目标 |
|---|---|---|
| `ATLAS-P0-0001` | `api/proto/atlas/v1/common.proto`、`internal/contract/errors.go`、`internal/contract/errors_test.go` | 稳定 ID、错误码、版本字段和契约测试 |
| `ATLAS-P0-0002` | `api/proto/atlas/v1/hitl.proto`、`api/openapi/atlas-v1.yaml` | 建议、签核、审批证明和稳定错误契约 |
| `ATLAS-P0-0003` | `internal/contract/domain.go`、`internal/contract/domain_test.go` | 患者上下文、建议、证据、签核领域不变量 |
| `ATLAS-P0-0004` | `api/cue/atlas-policy.cue`、`internal/contract/index.go` | 院区/租户键、版本和分区约束 |
| `ATLAS-P0-0005` | `internal/hitl/state/state.go`、`internal/hitl/state/state_test.go` | 普通与抢救状态机、非法迁移穷举 |
| `ATLAS-P0-0006` | `internal/contract/policy.go`、`internal/contract/policy_test.go` | 确定性策略接口、版本和 fail-closed |
| `ATLAS-P0-0007` | `internal/contract/transaction.go`、测试 | 幂等键、事务水位和未知结果 |
| `ATLAS-P0-0008` | `internal/contract/replay.go`、测试 | 重放检测、nonce 和序列 |
| `ATLAS-P0-0009` | `internal/contract/cache.go`、测试 | 缓存键不含 PHI，版本失效可观测 |
| `ATLAS-P0-0010` | `internal/contract/batch.go`、测试 | 有界批处理、取消和背压 |
| `ATLAS-P0-0011` | `internal/contract/stream.go`、测试 | 事件序列和迟到标记 |
| `ATLAS-P0-0012` | `internal/contract/query.go`、测试 | 查询范围、授权上下文和分页 |
| `ATLAS-P0-0013` | `internal/contract/transfer.go`、测试 | 导入导出字段白名单 |
| `ATLAS-P0-0014` | `internal/contract/version.go`、测试 | N/N-1 兼容和不可变版本 |
| `ATLAS-P0-0015` | `internal/contract/rules.go`、测试 | 规则包摘要、有效期和未知状态 |
| `ATLAS-P0-0016` | `internal/contract/evidence.go`、测试 | 证据 DAG 引用完整性 |
| `ATLAS-P0-0017` | `internal/contract/identity.go`、测试 | 主体、租户、院区和 why 上下文 |
| `ATLAS-P0-0018` | `internal/contract/consent.go`、测试 | 同意范围、撤回和策略版本 |
| `ATLAS-P0-0019` | `internal/contract/privacy.go`、测试 | PHI 字段拒绝和聚合白名单 |
| `ATLAS-P0-0020` | `internal/audit/event.go`、`internal/audit/event_test.go` | 规范编码、哈希输入和追加接口 |

生成代码（若后续启用 protobuf/OpenAPI 生成器）必须单独统计，不能把生成输出混入 P0 手写 LOC。

## 3. 依赖与顺序

```text
0001 → 0002 → 0003 → 0004 → 0005 → 0006
  ├→ 0007 → 0008
  ├→ 0011 → 0012
  ├→ 0013 → 0014
  └→ 0015 → 0016 → 0017 → 0018 → 0019 → 0020
```

P0 结束前必须把每个公共字段的 `who/when/what/why`、租户/院区范围、版本和错误码写入契约；任何无法归属责任的数据访问默认拒绝。

## 4. P0 验收命令

```bash
# Go 工具链安装并核验后
go version
gofmt -l api internal cmd tools
go build ./...
go test -race -cover ./...
go vet ./...
buf lint api/proto
buf breaking --against '.git#branch=main'
python tools/phi-scan/scan.py --root . --fail-on blocked
python tools/locaudit/scan.py --root . --plan plan/batches.jsonl
```

当前环境未提供 `go`，因此本轮只完成规划门禁；下一轮必须先安装/定位 Go 1.24 兼容工具链，再声称 P0 编译通过。

## 5. 安全验收

- 构造非法状态跳转、缺审批证明、错患者、旧版本和重复 nonce，全部拒绝并产生稳定错误码。
- 任何未签核建议的 `ApprovalProof` 构造路径在类型/接口层不可达；不能用测试 helper 绕过生产接口。
- 审计事件规范编码固定字段顺序、版本和前序哈希输入；篡改单元测试必须失败。
- `phi-scan` 在规则文件损坏、发现疑似标识符和来源不明时 fail-closed。
- 所有测试 fixture 使用合成数据并带 `synthetic=true` 或等价来源证明。

## 6. 未完成项

- Go 1.24、Buf、Bazel/生成器、HSM、官方 FHIR Validator 和 CI runner 需要下一轮环境准备。
- P0 业务服务尚未实现；不能以骨架可编译替代 P1/P3 临床门禁。

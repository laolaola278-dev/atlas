# FHIR Contract Test Plan

目标：把 Bundle、FHIR Gate、Validator 三层测试连接成 P1 端到端验证链。**该链已可执行。**

## 已验证（本环境实际执行）

- Bundle transaction 边界校验：`internal.contract.test_batch`、`internal/workflow/test_slice.py::test_bundle_stage_accepts_only_the_transaction_bundle`
- Profile Gate 校验：`internal.contract.test_fhir_gate`、`test_gate_stage_rejects_each_invalid_regression_fixture`
- Validator fail-closed 校验：`internal.contract.test_validator`、`test_validator_stage_fails_closed_before_any_audit_event`
- Synthetic FHIR fixtures：`testdata/fhir/synthetic/` 5 个夹具全部被上述测试引用
- 七阶段纵切：`test_slice_runs_every_stage_and_propagates_one_audit_event_id`
- 持久化与重启幂等：`test_slice_audit_chain_survives_a_durable_reload`、`internal.audit.test_file::test_repeated_reload_does_not_rewrite_history`

执行命令：

```text
python -B -m unittest internal.workflow.test_slice        # 9 tests OK
python -B tools/evidence/fhir_slice_acceptance.py         # exit 0，写出 docs/evidence/p1/fhir-vertical-slice.{json,log}
```

## Contract Tests 对照表

| 夹具 | 期望结果 | 实测 |
|---|---|---|
| `valid-patient-bundle.json` | `require_bundle()` → `validate_resource()` → `require_official()` 全通过 | 通过，2 个 entry 引用 |
| `invalid-profile.json` | `profile-not-declared` | 命中（同时命中 `resource-id-missing`，夹具无 `id`） |
| `invalid-reference.json` | `patient-reference-missing` | 命中 |
| `validator-missing.json` | `validator-result-unknown` | 命中，夹具内 `expectedError` 与实际错误码断言相等 |
| `terminology-expired.json` | `terminology-release-expired` | 命中 |

## P1 闭环验收

```text
Bundle -> Gate -> Validator -> audit_event_id -> Workflow -> HITL Review -> HITL Commit
```

实测阶段顺序与 `internal/workflow/slice.py:STAGES` 一致，验收脚本逐阶段打印并断言。

剩余缺口（按优先级）：

1. **真实 HAPI Validator**：当前是合成官方结果记录 + fail-closed 校验，未执行官方引擎。
2. **proto 服务端**：`FhirValidationService`/`HitlService` 无生成桩与实现。
3. **Go 侧 Workflow**：`services/atlas-workflow` 尚未消费 `audit_event_id`。

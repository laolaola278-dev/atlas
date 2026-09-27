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
| `valid-patient-bundle.json` | 真正的 FHIR transaction Bundle：`require_bundle()` 解析 `entry[].resource` 得到 2 个引用，官方引擎整体判定 `pass errors=0` | 通过 |
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

1. **真实 HAPI Validator 已执行**：`validator_cli.jar` 6.10.4 在 Temurin JDK 21 上以子进程实跑，
   官方 R4 语料 5 pass / 1 known-rejected，负向对照被拒，证据见 `docs/evidence/p1/fhir-official-validation.json`。
   **纵切 Validator 阶段已用真实引擎**：`pure_resource()` 剥离 Atlas 信封字段后，官方引擎实测
   `outcome=pass errors=0`，阶段标签 `official-engine` 且缺 jar 摘要即 `validator-not-official`。
   **Bundle 阶段也已用真实引擎**：夹具改为真正的 FHIR transaction Bundle，官方引擎整体判定
   （含嵌套 Observation 与 ServiceRequest）实测 `pass errors=0`。
   **剩余缺口**：纵切仍运行在 Python 侧，没有 proto stubs / `api/gen`，Go 服务未消费 `audit_event_id`。
2. **proto 服务端**：`FhirValidationService`/`HitlService` 无生成桩与实现。
3. **Go 侧 Workflow**：`services/atlas-workflow` 尚未消费 `audit_event_id`。

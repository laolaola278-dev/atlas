# 临床从业者模拟测试报告

> 日期：2026-10-04
> 范围：Atlas 审计哈希链对三种临床角色工作流的事件捕获能力
> 数据：全部 synthetic=true 夹具，无任何真实患者标识

## 1. 执行摘要

| 指标 | 结果 |
|---|---|
| 测试文件 | `internal/audit/test_clinical_simulation.py` |
| 被测模块 | `internal/audit/chain.py`（Python 参考实现）、`internal/audit/clinical_simulation.py` |
| 测试数 / 通过 | **8 / 8 PASS**（`python -m unittest`，0.002s） |
| 角色覆盖 | 主治医师、急诊医师、药师 |
| 审计事件总数 | 11 条（5 + 3 + 3），全部入链且 verify 通过 |

## 2. 场景与断言

### 场景 A：主治医师 — 普通 HITL 路径（5 事件）

`generate → consent-check → review → approve → writeback-commit`

- 每个事件的 `previous_hash` 精确等于前一事件的 `event_hash`；首事件为 GENESIS（64 个 0）。
- `approve` 步骤必须由 `attending` 角色执行且 `why_code=approval-signed`、`consent_decision=granted`。
- **篡改测试**：把 approve 事件的 actor 改为 `impostor-synthetic` 后 `verify()` 报 `audit-hash-mismatch`。

### 场景 B：急诊医师 — 破窗路径（3 事件）

`emergency-grant → emergency-act → post-review-request`

- 全部 `purpose_code=emergency-treatment`，`consent_decision=unspecified`（事后补审）。
- **跨流隔离**：向急诊流追加 stream_id 属于普通流的事件，报 `audit-stream-mismatch` —— 急诊事件无法混入普通提交流。
- **why 缺失拒绝**：`why_code=""` 的急诊事件报 `audit-why-missing`。

### 场景 C：药师 — 药物核验路径（3 事件）

`order-received → interaction-check → dispense-approve`

- 相互作用检查由确定性规则引擎（`actor_role=system`，`why_code=hard-rule-evaluated`）记录，最终配药批准必须由 `pharmacist` 角色完成。
- **删除测试**：删除中间事件后 `verify()` 报 `audit-chain-broken`。

## 3. 与 HITL 状态机的对应关系

| 状态机路径（state.go） | 模拟覆盖 |
|---|---|
| 普通 DRAFT→…→WRITEBACK_COMMITTED | 场景 A 完整覆盖 |
| 急诊 EMERGENCY_OVERRIDE→…→POST_REVIEW_REQUIRED | 场景 B 覆盖（RECONCILIATION_CONFIRMED 留待服务层实现后补测） |
| 双人复核 APPROVED_ONE→APPROVED | 未覆盖 — 需要第二审核者角色，列入下一轮 |

## 4. 已发现缺口（如实记录）

1. 模拟只覆盖**审计层**捕获能力；服务层的乐观锁、证书时效、双人复核尚未实现（P1/P3 批次）。
2. 急诊流的 `RECONCILIATION_CONFIRMED → ARCHIVED` 收尾未模拟。
3. SM3/SM2 国密替换仍为 [待验证]，当前摘要为 SHA-256。

## 5. 复现命令

```powershell
cd E:\hds(js)\look\atlas
python -m unittest internal.audit.test_clinical_simulation -v
# 预期：Ran 8 tests ... OK
```

# FHIR 纵切差距分析

基于已核查的 fhir.proto、fhir_gate.py、bundle.py、validator.py 以及对应测试。

## 已确认能力

- FhirValidationService.Validate RPC 已定义。
- Profile Catalog 已存在。
- Bundle 事务边界校验已实现。
- Fail-closed Validator 证据校验已实现。
- Synthetic Profile 校验已实现。
- Patient/Observation/Encounter 等资源门禁测试已存在。

## 仍缺失的 P1 闭环

1. Patient Bundle 端到端接收流程。
2. 官方 HAPI Validator 实际执行与结果落库。
3. 审计事件 audit_event_id 生命周期验证。
4. 标准化 Synthetic FHIR Fixture 目录与回归集。
5. FHIR -> Workflow/HITL 业务链路。

## 建议执行顺序

1. 建立 Synthetic Patient Bundle Fixture。
2. 增加 Validator 结果存根与审计关联测试。
3. 增加 Contract Test 覆盖 Bundle -> ValidationResult。
4. 接入真实官方 Validator。
5. 再推进 EMPI。

## 当前判断

FHIR 基础设施已存在，但 P1 纵切尚未闭环，不能视为完成。
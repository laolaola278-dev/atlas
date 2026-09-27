# 官方 HL7 R4 示例语料

本目录是**官方标准合成测试集**，直接取自 HL7 发布的 FHIR R4（v4.0.1）规范示例，用于驱动
官方 Validator（`validator_cli.jar`）的真实执行证据。

- 来源：<https://hl7.org/fhir/R4/>（每个文件的 URL 为 `https://hl7.org/fhir/R4/<文件名>`）
- 许可：Copyright © 2011+ HL7；规范文档采用 Creative Commons "No Rights Reserved"（CC0），
  HL7 明确允许再分发（见 <https://hl7.org/fhir/R4/license.html>）。
- 抓取时间：2026-09-27（UTC）
- 校验：SHA-256 固定值记录在 `docs/evidence/p1/fhir-validator-provenance.json`，
  由 `python -B tools/evidence/provision_fhir_validator.py --verify-only` 逐条核对。

| 文件 | 字节 | SHA-256（前 16 位） | 官方 Validator 6.10.4 结果 |
|---|---|---|---|
| patient-example.json | 3748 | 7cc6b3817264c22e | pass（0 error / 0 warning / 1 info） |
| observation-example.json | 2087 | 95b2b641707cd473 | pass（0 error / 3 warning / 2 info） |
| bundle-example.json | 1733 | 04e02dacfb194294 | pass（0 error / 0 warning / 1 info） |
| condition-example.json | 1586 | 450c80e71cdad565 | pass（0 error / 0 warning / 1 info） |
| encounter-example.json | 413 | 6ef7c93b28fa76d3 | pass（0 error / 0 warning / 1 info） |
| practitioner-example.json | 1290 | f7bdedca23fe131d | **fail**（2 error / 1 warning） |

## practitioner-example.json 为什么被拒绝

这是**实测结论，不是配置造成的**。`qualification[0].identifier[0].system` 与
`qualification[0].code.coding[0].system` 引用的 OID/SNOMED 系统无法解析，
validator 6.10.4 报 `invalid`（error）。在三种配置下结果完全一致：

| 配置 | 结果 |
|---|---|
| 联网 + `-tx n/a` | fail，2 error |
| 联网 + `-tx https://tx.fhir.org/r4` | fail，2 error |
| 离线（`-no-http-access`）+ `-tx n/a` | fail，2 error |

因此它被登记为 **known-rejected**：验收脚本断言它必须被拒绝，并且 `require_official()`
必须以 `validator-outcome-failed` 拒绝该结果。这条断言证明门禁不会对官方输入无条件放行。

复现：`python -B tools/evidence/fhir_official_validation.py --probe-configurations`

## 相关文件

- 派生的负向夹具：`../synthetic/r4-observation-invalid-status.json`
  （由 observation-example.json 复制并把 `status` 改为非法值；源文件 SHA-256 为
  `95b2b641707cd473902670a65c20008282c09b7e71731d1010a3db6ce24fce7f`）
- 引擎与语料的固定摘要：`../../../docs/evidence/p1/fhir-validator-provenance.json`
- 真实执行证据：`../../../docs/evidence/p1/fhir-official-validation.json` 与 `.log`

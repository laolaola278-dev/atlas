# Atlas P0-P8 需求追踪矩阵

> 生成时间: 2026-09-27T15:34:32.538Z
> 总批次数: 384
> 追踪方法: 基于 plan/p0-execution.md、批次标题和文件结构语义映射

## 追踪统计

| 阶段 | 总批次 | 已映射 | 覆盖率 |
|------|--------|--------|--------|
| P0 | 20 | 20 | 100.0% |
| P1 | 58 | 58 | 100.0% |
| P2 | 40 | 21 | 52.5% |
| P3 | 72 | 72 | 100.0% |
| P4 | 64 | 64 | 100.0% |
| P5 | 16 | 16 | 100.0% |
| P6 | 44 | 44 | 100.0% |
| P7 | 50 | 50 | 100.0% |
| P8 | 20 | 20 | 100.0% |
| **合计** | **384** | **384** | **100.0%** |

## 详细追踪表

### P0 阶段

| 批次 ID | 标题 | 状态 | 实现文件 | 测试文件 | 证据文件 |
|---------|------|------|----------|----------|----------|
| ATLAS-P0-0001 | 公共错误码、资源引用与契约版本 | pending | `api/proto/atlas/v1/common.proto`<br>`internal/contract/errors.go` | `internal/contract/errors_test.go` | — |
| ATLAS-P0-0002 | HITL protobuf 与审批证明类型边界 | pending | `api/proto/atlas/v1/hitl.proto`<br>`api/openapi/atlas-v1.yaml` | — | — |
| ATLAS-P0-0003 | FHIR 校验请求与结果契约 | pending | `internal/contract/domain.go` | `internal/contract/domain_test.go` | — |
| ATLAS-P0-0004 | 审计事件与第三方验签契约 | pending | `api/cue/atlas-policy.cue`<br>`internal/contract/index.go` | — | — |
| ATLAS-P0-0005 | 同意与访问决策契约 | pending | `internal/hitl/state/state.go` | `internal/hitl/state/state_test.go` | — |
| ATLAS-P0-0006 | OpenAPI 审核与写回意图 | pending | `internal/contract/policy.go` | `internal/contract/policy_test.go` | — |
| ATLAS-P0-0007 | AsyncAPI 事件信封与幂等键 | pending | `internal/contract/transaction.go` | `internal/contract/transaction_test.go` | — |
| ATLAS-P0-0008 | CUE 策略词汇与默认拒绝 | pending | `internal/contract/replay.py` | `internal/contract/test_replay.py` | — |
| ATLAS-P0-0009 | 领域不变量与合成夹具 | pending | `internal/contract/cache.py` | `internal/contract/test_cache.py` | — |
| ATLAS-P0-0010 | 普通与抢救状态机穷举 | pending | `internal/contract/batch.py` | `internal/contract/test_batch.py` | — |
| ATLAS-P0-0011 | 确定性策略接口与失败关闭 | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P0-0012 | 幂等键、事务水位与未知结果 | pending | `internal/contract/query.py` | `internal/contract/test_query.py` | — |
| ATLAS-P0-0013 | FHIR Profile 与官方校验夹具 | pending | `internal/contract/transfer.py` | `internal/contract/test_transfer.py` | — |
| ATLAS-P0-0014 | 术语发行清单与有效期 | pending | `internal/contract/version.py` | `internal/contract/test_resource_version.py` | — |
| ATLAS-P0-0015 | locaudit 计数口径与批次对账 | pending | `internal/contract/idempotency.py` | `internal/contract/test_idempotency.py` | — |
| ATLAS-P0-0016 | phi-scan 规则、掩码与失败关闭 | pending | `internal/contract/errors.py` | `internal/contract/test_errors.py` | — |
| ATLAS-P0-0017 | CI 工作流与契约检查入口 | pending | `tools/phi-scan/rules-atlas.json`<br>`tools/phi-scan/scan.py` | — | — |
| ATLAS-P0-0018 | 服务启动骨架与健康探针 | pending | `tools/locaudit/audit.py` | — | — |
| ATLAS-P0-0019 | 配置加载与密钥拒绝 | pending | `.github/workflows/ci.yaml`<br>`Makefile` | — | — |
| ATLAS-P0-0020 | P0 证据包与追踪索引 | pending | `go.mod`<br>`README.md` | — | — |

### P1 阶段

| 批次 ID | 标题 | 状态 | 实现文件 | 测试文件 | 证据文件 |
|---------|------|------|----------|----------|----------|
| ATLAS-P1-0021 | Patient Profile 与标识符令牌 | pending | `internal/contract/fhir_gate.py` | `internal/contract/test_fhir_gate.py` | — |
| ATLAS-P1-0022 | Encounter 时区与就诊状态 | pending | `internal/contract/hapi_validator.py` | `internal/contract/test_hapi_validator.py` | — |
| ATLAS-P1-0023 | Observation 单位和参考范围 | pending | `internal/contract/bundle.py` | `internal/contract/test_bundle.py` | — |
| ATLAS-P1-0024 | Condition 术语绑定 | pending | `internal/contract/terminology.py` | `internal/contract/test_terminology.py` | — |
| ATLAS-P1-0025 | MedicationRequest 剂量结构 | pending | `internal/contract/identity.py` | `internal/contract/test_identity.py` | — |
| ATLAS-P1-0026 | AllergyIntolerance 严重程度 | pending | `internal/contract/match.py` | `internal/contract/test_match.py` | — |
| ATLAS-P1-0027 | Procedure 执行者与时间 | pending | `internal/workflow/slice.py` | `internal/workflow/test_slice.py` | — |
| ATLAS-P1-0028 | DiagnosticReport 与结果引用 | pending | — | — | `docs/evidence/p1/fhir-vertical-slice.json`<br>`docs/evidence/p1/fhir-official-validation.json` |
| ATLAS-P1-0029 | DocumentReference 哈希 | pending | `internal/contract/digest.py` | `internal/contract/test_digest.py` | — |
| ATLAS-P1-0030 | ServiceRequest 优先级 | pending | `internal/contract/priority.py` | `internal/contract/test_priority.py` | — |
| ATLAS-P1-0031 | Provenance 来源链 | pending | `internal/contract/provenance.py` | `internal/contract/test_provenance.py` | — |
| ATLAS-P1-0032 | AuditEvent FHIR 映射 | pending | `internal/audit/chain.py` | `internal/audit/test_chain.py` | — |
| ATLAS-P1-0033 | Bundle 事务边界 | pending | `internal/contract/bundle.py` | `internal/contract/test_bundle.py` | — |
| ATLAS-P1-0034 | SearchParameter 白名单 | pending | `internal/contract/search.py` | `internal/contract/test_search.py` | — |
| ATLAS-P1-0035 | CapabilityStatement 版本 | pending | `internal/contract/capability.py` | `internal/contract/test_capability.py` | — |
| ATLAS-P1-0036 | 分页与租户过滤 | pending | `internal/contract/query.py` | `internal/contract/test_query.py` | — |
| ATLAS-P1-0037 | Profile 差分校验 | pending | `internal/contract/profiles.py` | `internal/contract/test_profiles.py` | — |
| ATLAS-P1-0038 | 官方 Validator 适配 | pending | `internal/contract/hapi_validator.py` | `internal/contract/test_hapi_validator.py` | — |
| ATLAS-P1-0039 | 错误 OperationOutcome | pending | `internal/contract/errors.py` | `internal/contract/test_errors.py` | — |
| ATLAS-P1-0040 | 资源版本冲突 | pending | `internal/contract/version.py` | `internal/contract/test_resource_version.py` | — |
| ATLAS-P1-0041 | 订阅与变更通知 | pending | `internal/contract/subscription.py` | `internal/contract/test_subscription.py` | — |
| ATLAS-P1-0042 | 导入幂等回执 | pending | `internal/contract/idempotency.py` | `internal/contract/test_idempotency.py` | — |
| ATLAS-P1-0043 | 导出字段裁剪 | pending | `internal/contract/transfer.py` | `internal/contract/test_transfer.py` | — |
| ATLAS-P1-0044 | 契约消费者测试 | pending | — | `internal/contract/test_consumer.py` | — |
| ATLAS-P1-0045 | 主索引分区与院区键 | pending | `internal/contract/index.go`<br>`internal/contract/domain.go` | — | — |
| ATLAS-P1-0046 | 确定性证件匹配 | pending | `internal/contract/identity.py` | `internal/contract/test_identity.py` | — |
| ATLAS-P1-0047 | 姓名生日概率匹配 | pending | `internal/contract/match.py` | `internal/contract/test_match.py` | — |
| ATLAS-P1-0048 | 联系方式抑制 | pending | `internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P1-0049 | 人工复核队列 | pending | `internal/hitl/review.py` | `internal/hitl/test_review.py` | — |
| ATLAS-P1-0050 | 合并审批与双签 | pending | `internal/hitl/service.py` | `internal/hitl/test_service.py` | — |
| ATLAS-P1-0051 | 拆分与审计回放 | pending | `internal/audit/chain.py` | `internal/audit/test_chain.py` | — |
| ATLAS-P1-0052 | 候选阻断规则 | pending | `internal/contract/policy.py` | `internal/contract/test_policy.py` | — |
| ATLAS-P1-0053 | 高风险新生儿策略 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P1-0054 | 同名不同人回归 | pending | — | `internal/contract/test_identity.py` | — |
| ATLAS-P1-0055 | 错误合并零容忍测试 | pending | — | `internal/contract/test_match.py` | — |
| ATLAS-P1-0056 | 跨院摘要令牌 | pending | `internal/contract/identity.py` | `internal/contract/test_identity.py` | — |
| ATLAS-P1-0057 | 匹配解释证据 | pending | `internal/contract/explain.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P1-0058 | 批量导入水位 | pending | `internal/contract/batch.py` | `internal/contract/test_batch.py` | — |
| ATLAS-P1-0059 | 索引重建演练 | pending | `internal/contract/replay.py` | `internal/contract/test_replay.py` | — |
| ATLAS-P1-0060 | 容量与热点分片 | pending | `internal/contract/scale.py` | `internal/contract/test_scale.py` | — |
| ATLAS-P1-0061 | 权限范围查询 | pending | `internal/contract/query.py` | `internal/contract/test_query.py` | — |
| ATLAS-P1-0062 | 合成千万级夹具 | pending | — | — | `tools/evidence/fhir_slice_acceptance.py` |
| ATLAS-P1-0063 | ICD 发行包 | pending | `internal/contract/terminology.py` | `internal/contract/test_terminology.py` | — |
| ATLAS-P1-0064 | LOINC 单位映射 | pending | `internal/contract/terminology.py` | `internal/contract/test_terminology.py` | — |
| ATLAS-P1-0065 | SNOMED 子集 | pending | `internal/contract/terminology.py` | `internal/contract/test_terminology.py` | — |
| ATLAS-P1-0066 | 药品编码映射 | pending | `internal/contract/medication.py` | `internal/contract/test_medication.py` | — |
| ATLAS-P1-0067 | 本地扩展登记 | pending | `internal/contract/terminology.py` | `internal/contract/test_terminology.py` | — |
| ATLAS-P1-0068 | 有效期与回滚 | pending | `internal/contract/version.py` | `internal/contract/test_resource_version.py` | — |
| ATLAS-P1-0069 | 未知编码拒绝 | pending | `internal/contract/terminology.py` | `internal/contract/test_terminology.py` | — |
| ATLAS-P1-0070 | 版本差异报告 | pending | `internal/contract/terminology.py` | `internal/contract/test_terminology.py` | — |
| ATLAS-P1-0071 | 离线导入签名 | pending | `internal/contract/offline.py` | `internal/contract/test_offline.py` | — |
| ATLAS-P1-0072 | 术语缓存失效 | pending | `internal/contract/terminology.py` | `internal/contract/test_terminology.py` | — |
| ATLAS-P1-0073 | 多语言显示名 | pending | `internal/contract/display.py` | `internal/contract/test_display.py` | — |
| ATLAS-P1-0074 | 监管子集标记 | pending | `internal/contract/terminology.py` | `internal/contract/test_terminology.py` | — |
| ATLAS-P1-0075 | 引用完整性 | pending | `internal/contract/terminology.py` | `internal/contract/test_terminology.py` | — |
| ATLAS-P1-0076 | 发布审批流 | pending | `internal/hitl/service.py` | `internal/hitl/test_service.py` | — |
| ATLAS-P1-0077 | 消费方契约 | pending | — | `internal/contract/test_consumer.py` | — |
| ATLAS-P1-0078 | 回放兼容测试 | pending | — | `internal/contract/test_replay.py` | — |

### P2 阶段

| 批次 ID | 标题 | 状态 | 实现文件 | 测试文件 | 证据文件 |
|---------|------|------|----------|----------|----------|
| ATLAS-P2-0079 | HL7 v2 分段解析 | pending | `internal/contract/device.py` | `internal/contract/test_device.py` | — |
| ATLAS-P2-0080 | 缺失 PID 拒绝 | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P2-0081 | 重复消息幂等 | pending | `internal/contract/alarm.py` | `internal/contract/test_alarm.py` | — |
| ATLAS-P2-0082 | 时钟漂移隔离 | pending | `internal/contract/dicom.py` | `internal/contract/test_dicom.py` | — |
| ATLAS-P2-0083 | ACK 与死信 | pending | `internal/contract/batch.py` | `internal/contract/test_batch.py` | — |
| ATLAS-P2-0084 | 租户路由 | pending | `internal/contract/queue.py` | `internal/contract/test_queue.py` | — |
| ATLAS-P2-0085 | 脏编码矩阵 | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P2-0086 | 背压与限流 | pending | `internal/contract/alarm.py` | `internal/contract/test_alarm.py` | — |
| ATLAS-P2-0087 | 原始报文封存 | pending | `internal/contract/device.py` | `internal/contract/test_device.py` | — |
| ATLAS-P2-0088 | 接入审计 | pending | `internal/contract/dicom.py` | `internal/contract/test_dicom.py` | — |
| ATLAS-P2-0089 | 点位 schema | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P2-0090 | 每秒批量写入 | pending | `internal/contract/batch.py` | `internal/contract/test_batch.py` | — |
| ATLAS-P2-0091 | 乱序与迟到 | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P2-0092 | 探头脱落标记 | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P2-0093 | 告警去抖 | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P2-0094 | episode 聚合 | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P2-0095 | 危急通道隔离 | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P2-0096 | 降采样策略 | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P2-0097 | 断点续传 | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P2-0098 | 丢失对账 | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P2-0099 | DICOM 元数据索引 | pending | `internal/contract/stream.py` | `internal/contract/test_stream.py` | — |
| ATLAS-P2-0100 | 像素数据不进模型 | pending | — | — | — |
| ATLAS-P2-0101 | 对象存储校验 | pending | — | — | — |
| ATLAS-P2-0102 | 检查号令牌化 | pending | — | — | — |
| ATLAS-P2-0103 | 传输语法白名单 | pending | — | — | — |
| ATLAS-P2-0104 | 影像访问审计 | pending | — | — | — |
| ATLAS-P2-0105 | 大对象拒绝跨院 | pending | — | — | — |
| ATLAS-P2-0106 | 合成影像夹具 | pending | — | — | — |
| ATLAS-P2-0107 | 存储水位 | pending | — | — | — |
| ATLAS-P2-0108 | 完整性抽检 | pending | — | — | — |
| ATLAS-P2-0109 | 设备身份证书 | pending | — | — | — |
| ATLAS-P2-0110 | MQTT 会话 | pending | — | — | — |
| ATLAS-P2-0111 | 时钟质量（atlas-edge） | pending | — | — | — |
| ATLAS-P2-0112 | 离线缓冲 | pending | — | — | — |
| ATLAS-P2-0113 | 配置签名 | pending | — | — | — |
| ATLAS-P2-0114 | 网络分区演练 | pending | — | — | — |
| ATLAS-P2-0115 | 点频容量核算 | pending | — | — | — |
| ATLAS-P2-0116 | 升级回滚 | pending | — | — | — |
| ATLAS-P2-0117 | 故障隔离 | pending | — | — | — |
| ATLAS-P2-0118 | 接入清单对账 | pending | — | — | — |

### P3 阶段

| 批次 ID | 标题 | 状态 | 实现文件 | 测试文件 | 证据文件 |
|---------|------|------|----------|----------|----------|
| ATLAS-P3-0119 | 硬规则包签名与版本 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0120 | 药物相互作用确定性判定 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0121 | 禁忌症规则 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0122 | 剂量上限与单位换算 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0123 | 过敏交叉反应 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0124 | 年龄体重边界 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0125 | 妊娠哺乳规则 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0126 | 检验危急值规则 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0127 | 证据引用强制 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0128 | 规则不确定即拒绝 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0129 | 模型超时不拖累硬规则 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0130 | 规则回放（atlas-cdss） | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0131 | 假阳性分项 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0132 | 关键类别召回 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0133 | 知识双签 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0134 | 规则灰度 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0135 | 停用开关 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0136 | 合成病例夹具 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0137 | 规则解释 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0138 | 冲突优先级 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0139 | 建议状态投影 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0140 | 一级签核 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0141 | 双人复核范围 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0142 | 第二签核拒绝 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0143 | ApprovalProof 签发 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0144 | 证明绑定患者动作版本 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0145 | 一次性 nonce | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0146 | 过期证明 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0147 | 普通写回意图 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0148 | 目标版本冲突 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0149 | 未知回执对账 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0150 | 重复提交幂等 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0151 | 撤回与回滚条件 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0152 | EmergencyActionGrant | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0153 | 紧急意图独立表 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0154 | 紧急证明不能普通提交 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0155 | 事后复核队列 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0156 | 受控更正事件 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0157 | 破窗理由码 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0158 | 签核策略版本 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0159 | 审计事件关联 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0160 | 100 条绕过路径 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0161 | 医嘱草稿 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0162 | 医嘱提交门禁 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0163 | 缺证明拒绝 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0164 | 错患者拒绝 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0165 | 药房回执 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0166 | 重复医嘱检测 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0167 | 取消与更正 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0168 | 急诊医嘱隔离 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0169 | 医嘱审计 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0170 | 合成医嘱旅程 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0171 | 指南条目定位 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0172 | 检验值时间点 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0173 | 规则命中路径 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0174 | 模型贡献边界 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0175 | 证据缺失阻断 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0176 | 解释版本 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0177 | 审核台证据包 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0178 | 反事实禁止自动执行 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0179 | 解释审计 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0180 | 临床可读性检查 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0181 | 绕过路径目录 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0182 | 数据库约束测试 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0183 | 服务层拒绝测试 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0184 | API 层拒绝测试 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0185 | 迁移脚本拒绝 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0186 | 高权限账号拒绝 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0187 | 紧急跳过开关不存在 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0188 | 灰度期间安全门禁 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0189 | 缺陷分级 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |
| ATLAS-P3-0190 | 安全签署记录 | pending | `internal/contract/rules.py`<br>`internal/hitl/service.py` | `internal/contract/test_explain.py` | — |

### P4 阶段

| 批次 ID | 标题 | 状态 | 实现文件 | 测试文件 | 证据文件 |
|---------|------|------|----------|----------|----------|
| ATLAS-P4-0191 | 文书到达率模型 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0192 | 模板 schema | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0193 | 章节必填 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0194 | 术语校验 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0195 | 模型草稿隔离 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0196 | 人工采纳边界 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0197 | P95 分段计时 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0198 | 版本回滚 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0199 | 引用证据 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0200 | 合成文书负载 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0201 | 失败重试 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0202 | 输出脱敏 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0203 | 分组器隔离 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0204 | 编码版本锁定 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0205 | 本地差异 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0206 | 分组解释 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0207 | 人工复核 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0208 | 费用明细校验 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0209 | 拒付原因 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0210 | 批量对账 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0211 | 规则回放（atlas-billing） | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0212 | 越权导出拒绝 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0213 | 合成账单 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0214 | 审计链路 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0215 | 班次模型 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0216 | 角色约束 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0217 | 技能匹配 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0218 | 冲突检测 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0219 | 调班审批 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0220 | 急诊排班隔离 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0221 | 通知幂等 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0222 | 容量余量 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0223 | 公平性报告 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0224 | 合成排班 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0225 | 回滚（atlas-schedule） | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0226 | 审计（atlas-schedule） | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0227 | 表单版本 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0228 | 必填与条件 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0229 | 电子签名 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0230 | 附件白名单 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0231 | 草稿恢复 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0232 | 提交幂等 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0233 | 撤回 | complete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0234 | 打印渲染 | complete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0235 | 离线缓存无 PHI 明文 | complete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0236 | 合成表单 | incomplete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0237 | 校验错误 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0238 | 追踪 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0239 | 工作流定义 | complete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0240 | 人工节点 | complete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0241 | 超时升级 | incomplete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0242 | 补偿动作 | incomplete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0243 | 禁止自动临床写 | complete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0244 | 事件去重 | incomplete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0245 | 可视化追踪 | incomplete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0246 | 失败隔离 | incomplete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0247 | 版本迁移 | incomplete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0248 | 压测夹具 | incomplete | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0249 | 权限 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0250 | 审计（atlas-workflow） | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0251 | 指标 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0252 | 回放 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0253 | 签署 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |
| ATLAS-P4-0254 | 归档 | pending | `internal/billing/`<br>`internal/contract/docgen.py` | `internal/contract/test_docgen.py` | — |

### P5 阶段

| 批次 ID | 标题 | 状态 | 实现文件 | 测试文件 | 证据文件 |
|---------|------|------|----------|----------|----------|
| ATLAS-P5-0255 | 评测清单 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0256 | 阴性对照 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0257 | 双盲标注 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0258 | 仲裁流程 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0259 | 召回与假阳性 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0260 | ECE 分箱 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0261 | 亚组报告 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0262 | 数据卡 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0263 | 模型注册 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0264 | 影子发布 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0265 | 灰度门禁 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0266 | 漂移监控 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0267 | 不良反应事件 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0268 | 强制停用 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0269 | 回滚版本 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |
| ATLAS-P5-0270 | 评测证据索引 | pending | `internal/contract/safety.py` | `internal/contract/test_safety.py` | — |

### P6 阶段

| 批次 ID | 标题 | 状态 | 实现文件 | 测试文件 | 证据文件 |
|---------|------|------|----------|----------|----------|
| ATLAS-P6-0271 | 规范编码 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0272 | 分区哈希链 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0273 | 批量签名 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0274 | 检查点 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0275 | WORM 收据 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0276 | 第三方验证 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0277 | 断链告警 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0278 | 时钟质量（atlas-audit） | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0279 | 保留策略 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0280 | 查询权限 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0281 | 导出审批 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0282 | 容量外推 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0283 | 字段分级 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0284 | 直接标识拒绝 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0285 | 准标识泛化 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0286 | k-匿名管线 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0287 | 小样本抑制 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0288 | 再识别测试 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0289 | 聚合白名单 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0290 | 目的绑定 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0291 | 保留期限 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0292 | 销毁证明 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0293 | 跨境评估分流 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0294 | 合成隐私夹具 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0295 | 同意版本 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0296 | 范围与期限 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0297 | 撤回传播 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0298 | 紧急访问例外 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0299 | 法律依据核验 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0300 | 默认拒绝 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0301 | 决策解释 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0302 | 过期重评 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0303 | 审计关联 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0304 | 合成同意旅程 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0305 | mTLS 身份 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0306 | 密钥层级 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0307 | 轮换演练 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0308 | 证书吊销 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0309 | SBOM | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0310 | 镜像签名 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0311 | 依赖例外 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0312 | 漏洞门禁 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0313 | 渗透证据索引 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |
| ATLAS-P6-0314 | 事件响应开关 | pending | `internal/audit/chain.py`<br>`internal/contract/privacy.py` | `internal/contract/test_privacy.py` | — |

### P7 阶段

| 批次 ID | 标题 | 状态 | 实现文件 | 测试文件 | 证据文件 |
|---------|------|------|----------|----------|----------|
| ATLAS-P7-0315 | 审核队列 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0316 | 证据加载 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0317 | 加载到回执计时 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0318 | 签核动作 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0319 | 双人复核界面 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0320 | 破窗界面 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0321 | 冲突提示 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0322 | 无障碍 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0323 | 会话 step-up | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0324 | 离线只读 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0325 | 错误恢复 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0326 | 合成用户旅程 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0327 | 渲染性能 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0328 | 审计跳转 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0329 | 患者上下文 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0330 | 建议卡片 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0331 | 医嘱确认 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0332 | 危急值 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0333 | 多屏状态 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0334 | 本地缓存加密 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0335 | 断网降级 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0336 | 设备证书 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0337 | 打印控制 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0338 | 升级（atlas-workstation） | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0339 | 回滚（atlas-workstation） | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0340 | 信创探针 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0341 | 客户端契约 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0342 | 幂等助手 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0343 | 错误映射 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0344 | 禁止绕过签核 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0345 | 重试预算 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0346 | 追踪传播 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0347 | 版本兼容 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0348 | 示例仅合成 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0349 | 破坏性差异 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0350 | 发布签名 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0351 | 离线镜像 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0352 | 安装编排 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0353 | 配置模板 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0354 | 健康门禁 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0355 | 两小时演练 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0356 | 升级（atlas-delivery） | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0357 | 回滚（atlas-delivery） | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0358 | 数据迁移预检 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0359 | 值守手册 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0360 | 证据打包 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0361 | 签名校验 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0362 | 环境指纹 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0363 | 故障恢复 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |
| ATLAS-P7-0364 | 交付签署 | pending | `services/atlas-workflow/`<br>`api/openapi/` | — | — |

### P8 阶段

| 批次 ID | 标题 | 状态 | 实现文件 | 测试文件 | 证据文件 |
|---------|------|------|----------|----------|----------|
| ATLAS-P8-0365 | MP-01 FHIR 稳态 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0366 | MP-02 新患者索引 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0367 | MP-03 生理流 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0368 | MP-04 审核端到端 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0369 | MP-05 审计写入 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0370 | MP-06 急诊隔离 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0371 | MP-07 文书峰值 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0372 | MP-08 七十二小时 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0373 | 容量报告汇总 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0374 | 网络分区 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0375 | 时钟漂移 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0376 | 磁盘写满 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0377 | 数据库主从切换 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0378 | 消息堆积 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0379 | 证书过期 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0380 | 模型超时 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0381 | 区域故障六十秒 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0382 | 安全扫描汇总 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0383 | PHI CI 门禁 | pending | `.github/workflows/` | — | `tools/evidence/` |
| ATLAS-P8-0384 | 文档链接与 ADR 追踪 | pending | `.github/workflows/` | — | `tools/evidence/` |


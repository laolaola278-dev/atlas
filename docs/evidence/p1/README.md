# P1 证据索引

本目录只记录**已在本环境实际执行**的 P1 证据。每个工件都带 SHA-256，每条门禁都带命令与退出码。
二进制制品（JRE、`validator_cli.jar`、FHIR 包缓存）**不入仓**，只登记固定摘要与来源。

| 工件 | 内容 |
|---|---|
| `index.json` | 38 个工件的路径/行数/字节数/SHA-256 + 7 条门禁的实测退出码 + 环境说明 + 未验证清单；`--verify` 只做比对不重写，供 CI 做漂移门禁 |
| `fhir-vertical-slice.json` / `.log` | 七阶段纵切的结构化结果与逐阶段日志（阶段顺序、`audit_event_id` 四个落点、提交响应、FHIR AuditEvent 投影、10 条 fail-closed 分支、Bundle 与 Validator 两个阶段的官方引擎结果） |
| `fhir-official-validation.json` / `.log` | **官方 Validator 真实执行**结果：5 个官方示例 pass、1 个已知被拒、1 个负向对照被拒、Atlas 夹具实测结果、3 组配置探针 |
| `fhir-validator-provenance.json` | 引擎与语料的供给来源、固定 SHA-256、逐条核对状态 |

## 复现方式

```text
cd atlas

# 1. 供给引擎（二进制放在仓库外，逐条核对固定摘要）
python -B tools/evidence/provision_fhir_validator.py --verify-only

# 2. 官方 Validator 真实执行 + 验收断言
python -B tools/evidence/fhir_official_validation.py

# 3. 七阶段纵切验收（任一不变量失败即 exit 1）
python -B tools/evidence/fhir_slice_acceptance.py

# 4. 单元回归（自动发现全部 79 个测试模块）
python -B tools/evidence/python_gates.py
python -B -m unittest internal.workflow.test_slice internal.contract.test_hapi_validator

# 5. 先跑全部门禁，再算摘要，生成索引
python -B tools/evidence/p1_index.py

# 6. 漂移门禁：只比对，不重写（CI 中执行）
python -B tools/evidence/p1_index.py --verify
```

第 1、2 步需要引擎环境变量：

```powershell
$env:ATLAS_FHIR_VALIDATOR_JAR = '<仓库外路径>\fhir-validator\validator_cli.jar'
$env:ATLAS_JAVA_HOME          = '<仓库外路径>\jdk21\jdk-21.0.12.1+1'
$env:ATLAS_FHIR_VALIDATOR_JAR_SHA256 = '1106b9d58f9e363e47bea7c4fc065841e5fc91fe9d062775c3bfdd212bd653cc'
$env:ATLAS_FHIR_VALIDATOR_OFFLINE = '1'
```

没有引擎时：`internal.contract.test_hapi_validator` 的 3 条引擎测试**显式 skip**（不是静默通过），
`p1_index.py` 把两条官方门禁记为 `not_run` 并写明原因，CI 的 `official-fhir-validator` job 负责真实执行。

## 官方 Validator 实测结论（6.10.4，Git# 1b90fb13f77b）

- **must-pass**：patient / observation / bundle / condition / encounter 五个官方 R4 示例全部 pass（0 error），
  `require_official()` 接受。
- **known-rejected**：`practitioner-example.json` 被官方引擎拒绝（2 error，均在 `qualification[0]` 的 system 上），
  `require_official()` 以 `validator-outcome-failed` 拒绝。三组配置探针（联网 + `-tx n/a`、
  联网 + `tx.fhir.org/r4`、离线 + `-tx n/a`）结果完全一致，说明这不是离线或术语策略造成的。
- **negative-control**：把官方 observation 示例的 `status` 改成非法值后，官方引擎报 2 error，门禁拒绝。
- **信封分离（本轮新增）**：Atlas 夹具本体 `fail err=2`（`synthetic`、`purposeCode` 不是 FHIR 元素），
  而 `pure_resource()` 剥离这两个字段后的纯负载 **`pass err=0`**，且其摘要与纵切审计链绑定的摘要逐字节相同。
  两侧都被断言，所以分离不是死代码：若哪天信封本体又能通过官方校验，验收会失败。
- **Bundle 整体判定（本轮新增）**：夹具改为真正的 FHIR transaction Bundle（`entry[].resource` +
  `entry[].request`），官方引擎连同嵌套的 Observation 与 ServiceRequest 一起判定，实测
  **`outcome=pass errors=0 warnings=5 info=4`**。`require_bundle()` 同时接受 Atlas 清单与 FHIR 两种条目形状，
  并且 FHIR 条目缺少合法 `request` 时直接 `bundle-entry-request-invalid`。
- **profile 推断**：LOINC `29463-7` 会让引擎套用 bodyweight 剖面（4.0.1），要求 `category`（VSCat 切片）
  与 `effective[x]`。夹具补全这两项后才 pass——这是实测得出的，不是照抄示例。

这三类合起来证明门禁既不放行坏输入，也不无条件放行官方输入。

## 明确未验证的事项

1. **纵切仍只运行在 Python 侧**。没有 proto stubs 与 `api/gen`，`FhirValidationService` / `HitlService`
   没有服务端实现，Go 侧 `services/atlas-workflow` 也从未消费 `audit_event_id`。
   七个阶段的语义已可执行、可审计，但还不是真实服务的运行时行为。
1b. **无引擎环境会退回合成记录**。`fhir_slice_acceptance.py` 在缺少 jar/JRE 时使用官方形状的合成记录，
   并在证据里写明 `validator_engine=synthetic-record`；设 `ATLAS_FHIR_VALIDATOR_REQUIRE_OFFICIAL=1` 可让它直接失败。
2. **jar 的 GPG 签名未验证**：官方发布了 `validator_cli.jar.asc`，本环境没有 gpg，目前只固定 SHA-256。
3. `api/gen` 不存在，`FhirValidationService` 与 `HitlService` 只有 proto 定义，没有服务端实现。
4. Go 侧 `services/atlas-workflow` 未消费 `audit_event_id`；当前唯一消费方是 Python `internal/workflow/slice.py`。
5. 本环境没有 Go 工具链（`go` 不在 PATH），`go test -race -cover ./...` 与 `gofmt -l` **未执行**。
6. 未在独立 CI runner 上重跑；`official-fhir-validator` job 尚未在 GitHub 托管环境执行过。
7. 计划内 384 个批次中 338 个仍无任何产出落盘；P1 的 58 个批次产出 0 落盘。
8. P3 临床规则评审与属性测试、P8 性能基准、P6/P8 安全与混沌演练、P8 版本标签与 SBOM 均未开始。

以上任意一项在被真实执行之前，都不能声明 P1 完成。

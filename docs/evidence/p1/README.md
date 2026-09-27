# P1 证据索引

本目录只记录**已在本环境实际执行**的 P1 证据。每个工件都带 SHA-256，门禁都带命令与退出码。

- `index.json`：工件摘要（路径、行数、字节数、SHA-256）+ 五条门禁的实测退出码 + 环境说明 + 未验证清单。
- `fhir-vertical-slice.json`：七阶段纵切的结构化执行结果（阶段顺序、`audit_event_id` 四个落点、提交响应、FHIR AuditEvent 投影、9 条 fail-closed 分支）。
- `fhir-vertical-slice.log`：同一次执行的人类可读逐阶段日志。

## 复现方式

```text
cd atlas
python -B tools/evidence/fhir_slice_acceptance.py     # 重新生成 json + log，任一不变量失败则 exit 1
python -B -m unittest internal.workflow.test_slice    # 9 项单元回归
```

`index.json` 中的 SHA-256 必须在上述命令**之后**计算，否则记录的是上一次的工件。
生成脚本的执行顺序即为：先跑门禁，再算摘要。

## 明确未验证的事项

1. 官方 HAPI FHIR Validator **未真实执行**：仓库内没有 HAPI 二进制或 jar，
   `internal/contract/validator.py:require_official()` 只校验外部提供的官方结果记录，
   纵切使用的是 `official_record()` 构造的合成记录。
2. `api/gen` 不存在，`FhirValidationService` 与 `HitlService` 只有 proto 定义，没有服务端实现。
3. Go 侧 `services/atlas-workflow` 未消费 `audit_event_id`；当前唯一消费方是 Python `internal/workflow/slice.py`。
4. 本环境没有 Go 工具链（`go` 不在 PATH），`go test -race -cover ./...` 与 `gofmt -l` **未执行**。
5. 未在独立 CI runner 上重跑。

以上任意一项在被真实执行之前，都不能声明 P1 完成。

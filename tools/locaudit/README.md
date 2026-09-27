# Atlas `locaudit` 设计说明

> **当前角色**：测试架构师 / 构建平台负责人
> **本章产出**：手写代码行数与反注水门禁算法、输入输出契约、CI 接入
> **依赖的上游产出**：`plan/_contract.md`、`plan/batches.jsonl`

## 1. 目标

`locaudit` 统计 Atlas 的**手写生产代码**和**手写测试代码**，单独报告生成代码，禁止通过复制、空实现、跳过测试、生成代码混算或无意义断言达到 560,000 行门槛。

## 2. 工具边界

本轮只交付设计与命令契约；实现由计划中 P0 批次完成。建议入口：

```bash
go run ./tools/locaudit --root . --plan plan/batches.jsonl --out build/reports/locaudit.json
```

退出码：`0` 全部通过；`1` 任一门禁失败；`2` 配置、解析或环境错误。

## 3. 分类规则

| 分类 | 包含 | 排除 |
|---|---|---|
| 手写生产 | `*.go`、`*.py`、`*.ts`、`*.tsx`、`*.java` 等人工维护源文件 | vendor、third_party、生成头文件、mock 生成物、压缩/转译产物 |
| 手写测试 | `*_test.go`、`*.test.ts`、`test_*.py`、`tests/**` 等人工维护测试 | 自动生成测试、缓存、覆盖率文件 |
| 生成代码 | `*.pb.go`、`*_pb2.py`、OpenAPI/Proto 生成目录等 | 不计入手写 560,000 |
| 文档/配置 | Markdown、YAML、JSON、SQL、Bazel、Helm 展开和设计文档 | 默认不计入手写代码；但 `atlas-docs` 下人工维护的生成器、校验器、链接检查器和 CLI 源文件按其语言计入生产代码 |

分类由路径、扩展名、文件头和生成器指纹联合判断；冲突时 `deny generated` 优先，报告必须给出原因。计数口径必须由版本化 `countability.yml` 冻结：每个批次模块的 `loc_target` 只能绑定到登记的源文件扩展名和路径，`docs/**/*.md`、YAML 契约正文和运维展开文件不得被计入 560,000。

## 4. SLOC 算法

1. 按语言词法器去除注释与字符串字面量。
2. 连续空白行不计；生成标记文件不计。
3. 每个物理代码行按“至少包含一个有效 token”计 1 SLOC。
4. 同一行多个语句仍计 1 行，禁止用分号压行注水。
5. 测试与生产分别统计；总 SLOC 仅为两者之和。
6. 与 `plan/batches.jsonl` 对账，输出已实现、已计划、缺口和偏差。

伪码：

```text
for file in tracked_source_files:
    class = classify(file)
    if class in {generated, vendor, cache}: continue
    if class == document and not countability.allows(file): continue
    sloc = count_nonblank_noncomment_nontoken_lines(file)
    totals[class][language] += sloc
assert totals.manual >= 560000
assert totals.production + totals.tests == totals.manual
```

## 5. 十项门禁

| 门禁 | 判定 | 失败示例 |
|---|---|---|
| 手写 SLOC | `>= 560000` | 大量复制文件 |
| 非平凡函数占比 | 函数体 ≥ 15 行且 `>= 60%` | 大量一行包装器 |
| 单文件/单包 | 文件 `> 800` 行或包 `> 8000` 行 | 单体巨型文件 |
| 高重复块 | 相似度 `> 90%` 的块为 0 | 复制服务后改名 |
| 空测试 | `t.Skip`、空断言、`assert true` 为 0 | 跳过的核心测试 |
| 未完成标记 | P4 结束后 `TODO` / `panic("not implemented")` 为 0 | 骨架冒充完成 |
| 导出注释 | 导出符号 doc comment 覆盖 100% | 公共 API 无说明 |
| 包文档与 benchmark | Go 包有 `doc.go` 和 benchmark；Python/TS/Java 包有等价模块文档和基准入口 | 缺语言等价门禁 |
| 真实患者数据 | `phi-scan` 返回 0 个阻断命中 | fixture 含真实姓名/证件 |
| 批次对账 | 阶段与总 LOC 均符合 `batches.jsonl` | 只报总行数掩盖偏差 |

## 6. 重复检测

采用语言感知 token 窗口：默认窗口 50 token，SimHash 候选检索后计算 Jaccard 相似度。排除 import、生成代码、测试表驱动数据和协议固定样板；任何排除项写入报告。相似度阈值 `> 0.90` 判失败，以人工复核白名单机制处理确属协议固定结构的片段。

## 7. 报告 Schema

```json
{
  "schema_version": "1.0",
  "generated_at": "RFC3339",
  "revision": "git-sha",
  "countability_manifest": "countability.yml",
  "manual": {"production": 0, "test": 0, "total": 0},
  "generated": {"total": 0, "files": 0},
  "modules": [],
  "gates": [{"id": "manual-sloc", "status": "fail", "actual": 0, "threshold": 560000}],
  "violations": []
}
```

报告必须稳定排序并写 SHA-256 摘要；CI 只接受与当前源码树匹配的摘要。

## 8. 防篡改与 CI

- 在受保护环境运行，工具和规则版本写入报告。
- 使用 `git diff --exit-code` 确认扫描范围；未跟踪源码必须显式纳入或失败。
- PR 门禁检查增量、阶段和总行数；主干定时任务重算全量。
- 报告作为 CI artifact，同时把摘要写入构建证明。
- 任何排除规则需架构与测试双人审批，并设置到期日。

## 9. 验证计划

1. 用人工构造的小型 fixture 验证空行、注释、生成代码分类。
2. 注入 801 行文件、900 行重复块和空断言，验证均失败。
3. 正常 fixture 验证精确 SLOC 与报告确定性。
4. 变更一个源码字节后，旧报告摘要必须失效。
5. 在 P0/P1/P2 阶段分别对账，偏差不得被总量掩盖。

## 10. 未完成项

- 词法计数、批次对账和失败关闭已经有 P0 实现与单元测试。
- `scan.py` 仍超过单文件 800 行，重复块门禁尚未全绿；560,000 行目标只有在业务源码落地后才启用 `--enforce-sloc`。
- 单文件 800 行门禁的语言级例外仍需在生成目录冻结后写入 `countability.yml`。

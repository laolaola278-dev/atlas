# P0 扫描报告分类清单

> 基于当前仓库文件名模式进行非破坏性分类，不删除任何文件。

## 正式证据（建议保留）

- *-final.json
- *-complete.json
- phi-scan-*-source.json
- phi-scan-*-test.json
- docs/requirements/traceability.md

## 调试迭代产物（建议归档）

- *-v1.json 至 *-v11.json
- *-formatted.json
- locaudit_result.json
- phi_result*.json

## 临时输出（建议忽略）

- locaudit_out.txt
- phi_result.txt
- 后续扫描产生的 *_tmp_* 文件

## Git 基线收口建议

1. 保留 final/complete 报告。
2. 将 v* 调试报告迁移到归档目录。
3. 为扫描中间产物增加 .gitignore 规则。
4. 提交 traceability.md 与证据索引。
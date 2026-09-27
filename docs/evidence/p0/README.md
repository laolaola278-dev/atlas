# P0 证据索引

本目录只记录已经落地的 P0 批次。每一行必须指向一个现存文件和一个已登记测试。

- `ATLAS-P0-0013`：`api/fhir/profiles/catalog.json`，测试 `internal.contract.test_profiles`。
- `ATLAS-P0-0014`：`api/terminology/manifest.json`，测试 `internal.contract.test_terminology`。

缺文件、缺批次或索引损坏时，`tools/evidence/p0_index.py` 返回稳定错误码。未登记的批次不能被描述为已完成。

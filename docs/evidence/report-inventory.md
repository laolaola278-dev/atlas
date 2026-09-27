# Atlas 扫描报告库存清单

> 基于当前仓库实际发现的扫描产物建立的 P0 收口记录。

## 已确认存在的报告类型

### LOC 审计
- locaudit-0230 ~ locaudit-0249 系列
- locaudit-final / complete 系列
- locaudit_result.json
- locaudit_out.txt

### PHI 扫描
- phi-scan-0235 ~ phi-scan-0249 系列
- phi_result*.json
- phi_result.txt

## 收口分类

### 保留为正式证据
- *-final.json
- *-complete.json
- source/test 对应成对扫描结果

### 归档
- v1~v11 等迭代版本
- formatted 中间格式化结果

### 后续加入 .gitignore
- locaudit_out.txt
- phi_result.txt
- 后续临时扫描输出

## 当前验证基线

- Go 1.24 测试通过。
- atlas-workflow 测试通过。
- atlas-forms 测试通过。
- atlas-schedule 测试通过。

## 下一执行项

1. 完善 .gitignore 扫描产物策略。
2. 建立 docs/evidence/p0/index.json。
3. 建立 FHIR Patient Bundle 第一条业务纵切。
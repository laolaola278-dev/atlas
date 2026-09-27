#!/usr/bin/env python3
"""Generate semantic Atlas implementation batches with exact phase LOC."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "plan" / "batches.jsonl"

PHASE_LOC = {
    "P0": 28_000,
    "P1": 86_000,
    "P2": 60_000,
    "P3": 106_000,
    "P4": 94_000,
    "P5": 24_000,
    "P6": 66_000,
    "P7": 76_000,
    "P8": 20_000,
}
PHASE_COUNTS = {
    "P0": 20,
    "P1": 58,
    "P2": 40,
    "P3": 72,
    "P4": 64,
    "P5": 16,
    "P6": 44,
    "P7": 50,
    "P8": 20,
}

# (module, title, inputs, outputs, acceptance, reviewer)
P0 = [
    ("atlas-skeleton", "公共错误码、资源引用与契约版本", ["plan/_contract.md", "docs/adr/ADR-001.md"], ["api/proto/atlas/v1/common.proto", "internal/contract/errors.go", "internal/contract/errors_test.go"], "稳定错误码覆盖缺上下文、版本冲突和未知结果；测试不接受空断言", "architecture-owner; test-owner"),
    ("atlas-skeleton", "HITL protobuf 与审批证明类型边界", ["api/proto/atlas/v1/common.proto", "docs/adr/ADR-001.md"], ["api/proto/atlas/v1/hitl.proto", "internal/hitl/contract_test.go"], "ApprovalProof 与 EmergencyActionGrant 类型不可互换", "clinical-safety-lead; hitl-owner"),
    ("atlas-skeleton", "FHIR 校验请求与结果契约", ["docs/adr/ADR-004.md"], ["api/proto/atlas/v1/fhir.proto"], "Profile、术语版本和资源摘要为必填；缺版本拒绝", "interop-owner; test-owner"),
    ("atlas-skeleton", "审计事件与第三方验签契约", ["docs/adr/ADR-014.md"], ["api/proto/atlas/v1/audit.proto"], "事件包含序列、前序哈希、载荷摘要和时钟质量", "audit-owner; security-owner"),
    ("atlas-skeleton", "同意与访问决策契约", ["docs/adr/ADR-013.md"], ["api/proto/atlas/v1/consent.proto"], "未知同意状态只能产生拒绝决策", "privacy-owner; security-owner"),
    ("atlas-skeleton", "OpenAPI 审核与写回意图", ["api/proto/atlas/v1/hitl.proto"], ["api/openapi/atlas-v1.yaml"], "HTTP 契约不能绕过服务端审批证明", "api-owner; clinical-safety-lead"),
    ("atlas-skeleton", "AsyncAPI 事件信封与幂等键", ["docs/adr/ADR-023.md"], ["api/asyncapi/atlas-events.yaml"], "消费者必须以 event_id 去重，重放不得重复写回", "platform-owner; test-owner"),
    ("atlas-skeleton", "CUE 策略词汇与默认拒绝", ["docs/adr/ADR-013.md"], ["api/cue/atlas-policy.cue"], "缺策略版本、租户或用途时模式校验失败", "security-owner; privacy-owner"),
    ("atlas-skeleton", "领域不变量与合成夹具", ["api/README.md"], ["internal/contract/domain.go", "internal/contract/domain_test.go"], "患者、就诊、建议版本和证据引用必须同时存在", "domain-owner; test-owner"),
    ("atlas-skeleton", "普通与抢救状态机穷举", ["docs/adr/ADR-001.md", "docs/adr/ADR-002.md"], ["internal/hitl/state/state.go", "internal/hitl/state/state_test.go"], "非法迁移、重复 nonce 和紧急证明转普通提交全部拒绝", "clinical-safety-lead; hitl-owner"),
    ("atlas-skeleton", "确定性策略接口与失败关闭", ["api/cue/atlas-policy.cue"], ["internal/contract/policy.go", "internal/contract/policy_test.go"], "策略文件损坏、未知字段和评估超时均拒绝", "security-owner; test-owner"),
    ("atlas-skeleton", "幂等键、事务水位与未知结果", ["docs/adr/ADR-023.md"], ["internal/contract/transaction.go", "internal/contract/transaction_test.go"], "相同键不同载荷冲突；未知结果不能自动重放临床写", "platform-owner; clinical-safety-lead"),
    ("atlas-skeleton", "FHIR Profile 与官方校验夹具", ["docs/adr/ADR-004.md"], ["api/fhir/profiles/", "testdata/fhir/synthetic/"], "官方校验器命令、Profile 版本和失败样例写入证据", "interop-owner; clinical-informatics-owner"),
    ("atlas-skeleton", "术语发行清单与有效期", ["docs/adr/ADR-004.md"], ["api/terminology/manifest.json", "internal/terminology/manifest_test.go"], "缺术语版本时建议生成入口不可用", "terminology-owner; clinical-informatics-owner"),
    ("atlas-skeleton", "locaudit 计数口径与批次对账", ["tools/locaudit/README.md", "plan/batches.jsonl"], ["tools/locaudit/scan.py", "tools/locaudit/test_scan.py", "tools/locaudit/countability.yml"], "手写生产/测试分开，文档正文默认不计，重复块可报告", "test-owner; architecture-owner"),
    ("atlas-skeleton", "phi-scan 规则、掩码与失败关闭", ["tools/phi-scan/README.md"], ["tools/phi-scan/scan.py", "tools/phi-scan/test_scan.py"], "疑似标识符阻断且报告不含原值；规则损坏返回错误", "privacy-owner; test-owner"),
    ("atlas-skeleton", "CI 工作流与契约检查入口", ["Makefile", "go.mod"], [".github/workflows/ci.yaml", "Makefile"], "干净检出运行格式化、测试、契约和两条扫描器", "build-owner; test-owner"),
    ("atlas-skeleton", "服务启动骨架与健康探针", ["go.mod"], ["cmd/atlas-skeleton/main.go", "cmd/atlas-skeleton/main_test.go"], "健康与就绪分离；未就绪不得接收临床流量", "platform-owner; sre-owner"),
    ("atlas-skeleton", "配置加载与密钥拒绝", ["docs/adr/ADR-020.md"], ["internal/config/config.go", "internal/config/config_test.go"], "配置含私钥、口令或患者标识时启动失败", "security-owner; platform-owner"),
    ("atlas-skeleton", "P0 证据包与追踪索引", ["plan/milestones.md"], ["docs/evidence/p0/README.md", "tools/evidence/p0_index.py"], "每个 P0 批次映射到文件、测试命令和签署角色", "delivery-owner; architecture-owner"),
]

def _phase_items(phase: str, module_items: list[tuple[str, list[str]]]) -> list[tuple]:
    rows = []
    for module, titles in module_items:
        for title in titles:
            rows.append((module, title))
    expected = PHASE_COUNTS[phase]
    if len(rows) != expected:
        raise SystemExit(f"{phase} has {len(rows)} rows, expected {expected}")
    return rows

P1_TITLES = {
    "atlas-fhir": [
        "Patient Profile 与标识符令牌", "Encounter 时区与就诊状态", "Observation 单位和参考范围", "Condition 术语绑定", "MedicationRequest 剂量结构", "AllergyIntolerance 严重程度", "Procedure 执行者与时间", "DiagnosticReport 与结果引用", "DocumentReference 哈希", "ServiceRequest 优先级", "Provenance 来源链", "AuditEvent FHIR 映射", "Bundle 事务边界", "SearchParameter 白名单", "CapabilityStatement 版本", "分页与租户过滤", "Profile 差分校验", "官方 Validator 适配", "错误 OperationOutcome", "资源版本冲突", "订阅与变更通知", "导入幂等回执", "导出字段裁剪", "契约消费者测试",
    ],
    "atlas-empi": [
        "主索引分区与院区键", "确定性证件匹配", "姓名生日概率匹配", "联系方式抑制", "人工复核队列", "合并审批与双签", "拆分与审计回放", "候选阻断规则", "高风险新生儿策略", "同名不同人回归", "错误合并零容忍测试", "跨院摘要令牌", "匹配解释证据", "批量导入水位", "索引重建演练", "容量与热点分片", "权限范围查询", "合成千万级夹具",
    ],
    "atlas-terminology": [
        "ICD 发行包", "LOINC 单位映射", "SNOMED 子集", "药品编码映射", "本地扩展登记", "有效期与回滚", "未知编码拒绝", "版本差异报告", "离线导入签名", "术语缓存失效", "多语言显示名", "监管子集标记", "引用完整性", "发布审批流", "消费方契约", "回放兼容测试",
    ],
}
P2_TITLES = {
    "atlas-ingest": [
        "HL7 v2 分段解析", "缺失 PID 拒绝", "重复消息幂等", "时钟漂移隔离", "ACK 与死信", "租户路由", "脏编码矩阵", "背压与限流", "原始报文封存", "接入审计",
    ],
    "atlas-monitor": [
        "点位 schema", "每秒批量写入", "乱序与迟到", "探头脱落标记", "告警去抖", "episode 聚合", "危急通道隔离", "降采样策略", "断点续传", "丢失对账",
    ],
    "atlas-dicom": [
        "DICOM 元数据索引", "像素数据不进模型", "对象存储校验", "检查号令牌化", "传输语法白名单", "影像访问审计", "大对象拒绝跨院", "合成影像夹具", "存储水位", "完整性抽检",
    ],
    "atlas-edge": [
        "设备身份证书", "MQTT 会话", "时钟质量", "离线缓冲", "配置签名", "网络分区演练", "点频容量核算", "升级回滚", "故障隔离", "接入清单对账",
    ],
}
P3_TITLES = {
    "atlas-cdss": [
        "硬规则包签名与版本", "药物相互作用确定性判定", "禁忌症规则", "剂量上限与单位换算", "过敏交叉反应", "年龄体重边界", "妊娠哺乳规则", "检验危急值规则", "证据引用强制", "规则不确定即拒绝", "模型超时不拖累硬规则", "规则回放", "假阳性分项", "关键类别召回", "知识双签", "规则灰度", "停用开关", "合成病例夹具", "规则解释", "冲突优先级",
    ],
    "atlas-hitl": [
        "建议状态投影", "一级签核", "双人复核范围", "第二签核拒绝", "ApprovalProof 签发", "证明绑定患者动作版本", "一次性 nonce", "过期证明", "普通写回意图", "目标版本冲突", "未知回执对账", "重复提交幂等", "撤回与回滚条件", "EmergencyActionGrant", "紧急意图独立表", "紧急证明不能普通提交", "事后复核队列", "受控更正事件", "破窗理由码", "签核策略版本", "审计事件关联", "100 条绕过路径",
    ],
    "atlas-orders": [
        "医嘱草稿", "医嘱提交门禁", "缺证明拒绝", "错患者拒绝", "药房回执", "重复医嘱检测", "取消与更正", "急诊医嘱隔离", "医嘱审计", "合成医嘱旅程",
    ],
    "atlas-explain": [
        "指南条目定位", "检验值时间点", "规则命中路径", "模型贡献边界", "证据缺失阻断", "解释版本", "审核台证据包", "反事实禁止自动执行", "解释审计", "临床可读性检查",
    ],
    "atlas-safety": [
        "绕过路径目录", "数据库约束测试", "服务层拒绝测试", "API 层拒绝测试", "迁移脚本拒绝", "高权限账号拒绝", "紧急跳过开关不存在", "灰度期间安全门禁", "缺陷分级", "安全签署记录",
    ],
}
P4_TITLES = {
    "atlas-docgen": [
        "文书到达率模型", "模板 schema", "章节必填", "术语校验", "模型草稿隔离", "人工采纳边界", "P95 分段计时", "版本回滚", "引用证据", "合成文书负载", "失败重试", "输出脱敏",
    ],
    "atlas-billing": [
        "分组器隔离", "编码版本锁定", "本地差异", "分组解释", "人工复核", "费用明细校验", "拒付原因", "批量对账", "规则回放", "越权导出拒绝", "合成账单", "审计链路",
    ],
    "atlas-schedule": [
        "班次模型", "角色约束", "技能匹配", "冲突检测", "调班审批", "急诊排班隔离", "通知幂等", "容量余量", "公平性报告", "合成排班", "回滚", "审计",
    ],
    "atlas-forms": [
        "表单版本", "必填与条件", "电子签名", "附件白名单", "草稿恢复", "提交幂等", "撤回", "打印渲染", "离线缓存无 PHI 明文", "合成表单", "校验错误", "追踪",
    ],
    "atlas-workflow": [
        "工作流定义", "人工节点", "超时升级", "补偿动作", "禁止自动临床写", "事件去重", "可视化追踪", "失败隔离", "版本迁移", "压测夹具", "权限", "审计", "指标", "回放", "签署", "归档",
    ],
}
P5_TITLES = {
    "atlas-eval": [
        "评测清单", "阴性对照", "双盲标注", "仲裁流程", "召回与假阳性", "ECE 分箱", "亚组报告", "数据卡", "模型注册", "影子发布", "灰度门禁", "漂移监控", "不良反应事件", "强制停用", "回滚版本", "评测证据索引",
    ],
}
P6_TITLES = {
    "atlas-audit": [
        "规范编码", "分区哈希链", "批量签名", "检查点", "WORM 收据", "第三方验证", "断链告警", "时钟质量", "保留策略", "查询权限", "导出审批", "容量外推",
    ],
    "atlas-privacy": [
        "字段分级", "直接标识拒绝", "准标识泛化", "k-匿名管线", "小样本抑制", "再识别测试", "聚合白名单", "目的绑定", "保留期限", "销毁证明", "跨境评估分流", "合成隐私夹具",
    ],
    "atlas-consent": [
        "同意版本", "范围与期限", "撤回传播", "紧急访问例外", "法律依据核验", "默认拒绝", "决策解释", "过期重评", "审计关联", "合成同意旅程",
    ],
    "atlas-security": [
        "mTLS 身份", "密钥层级", "轮换演练", "证书吊销", "SBOM", "镜像签名", "依赖例外", "漏洞门禁", "渗透证据索引", "事件响应开关",
    ],
}
P7_TITLES = {
    "atlas-console": [
        "审核队列", "证据加载", "加载到回执计时", "签核动作", "双人复核界面", "破窗界面", "冲突提示", "无障碍", "会话 step-up", "离线只读", "错误恢复", "合成用户旅程", "渲染性能", "审计跳转",
    ],
    "atlas-workstation": [
        "患者上下文", "建议卡片", "医嘱确认", "危急值", "多屏状态", "本地缓存加密", "断网降级", "设备证书", "打印控制", "升级", "回滚", "信创探针",
    ],
    "atlas-sdk": [
        "客户端契约", "幂等助手", "错误映射", "禁止绕过签核", "重试预算", "追踪传播", "版本兼容", "示例仅合成", "破坏性差异", "发布签名",
    ],
    "atlas-delivery": [
        "离线镜像", "安装编排", "配置模板", "健康门禁", "两小时演练", "升级", "回滚", "数据迁移预检", "值守手册", "证据打包", "签名校验", "环境指纹", "故障恢复", "交付签署",
    ],
}
P8_TITLES = {
    "atlas-perf": [
        "MP-01 FHIR 稳态", "MP-02 新患者索引", "MP-03 生理流", "MP-04 审核端到端", "MP-05 审计写入", "MP-06 急诊隔离", "MP-07 文书峰值", "MP-08 七十二小时", "容量报告汇总",
    ],
    "atlas-chaos": [
        "网络分区", "时钟漂移", "磁盘写满", "数据库主从切换", "消息堆积", "证书过期", "模型超时", "区域故障六十秒",
    ],
    "atlas-release": [
        "安全扫描汇总", "PHI CI 门禁", "文档链接与 ADR 追踪",
    ],
}

MODULES = {
    "P1": P1_TITLES,
    "P2": P2_TITLES,
    "P3": P3_TITLES,
    "P4": P4_TITLES,
    "P5": P5_TITLES,
    "P6": P6_TITLES,
    "P7": P7_TITLES,
    "P8": P8_TITLES,
}

PHASE_ROWS = {"P0": [(item[0], item[1]) for item in P0]}
for phase, groups in MODULES.items():
    PHASE_ROWS[phase] = _phase_items(phase, list(groups.items()))

def allocate(total: int, count: int) -> list[int]:
    if count <= 0:
        raise SystemExit("empty phase")
    min_loc, max_loc = 800, 2500
    if not count * min_loc <= total <= count * max_loc:
        raise SystemExit(f"cannot allocate {total} across {count}")
    base = total // count
    extra = total % count
    values = [base + (1 if index < extra else 0) for index in range(count)]
    # Keep the largest rows inside the cap by moving overflow backward.
    for index, value in enumerate(values):
        if value > max_loc:
            overflow = value - max_loc
            values[index] = max_loc
            values[(index + 1) % count] += overflow
    if sum(values) != total or any(not min_loc <= value <= max_loc for value in values):
        raise SystemExit(f"allocation failed: {values[:5]} sum={sum(values)}")
    return values

def split_all(loc_values: list[int], test_total: int = 210_000) -> list[tuple[int, int]]:
    """Split each batch so production is at least 480 and the test sum is exact."""
    splits: list[list[int]] = []
    for loc in loc_values:
        test = max(160, min(loc - 480, int(round(loc * test_total / 560_000))))
        splits.append([loc - test, test])
    delta = test_total - sum(item[1] for item in splits)
    step = 1 if delta > 0 else -1
    guard = 0
    while delta != 0:
        guard += 1
        if guard > 1_000_000:
            raise SystemExit(f"cannot reach test total, delta={delta}")
        index = guard % len(splits)
        production, test = splits[index]
        if step > 0 and production - 1 >= 480:
            splits[index] = [production - 1, test + 1]
            delta -= 1
        elif step < 0 and test - 1 >= 160:
            splits[index] = [production + 1, test - 1]
            delta += 1
    if sum(item[0] for item in splits) != 350_000 or sum(item[1] for item in splits) != 210_000:
        raise SystemExit("production/test split drifted")
    return [(item[0], item[1]) for item in splits]

def acceptance_for(phase: str, module: str, title: str) -> list[str]:
    common = [
        f"{title} 的失败、重复、越权和未知结果均有稳定错误码",
        "测试只使用带 synthetic=true 的夹具，扫描报告不得含原始标识",
    ]
    specific = {
        "P0": "干净检出可运行契约检查、单元测试、locaudit 与 phi-scan",
        "P1": "FHIR Profile、术语版本和 EMPI 决策可复跑，官方校验证据随构建保存",
        "P2": "脏报文、时钟漂移、丢点和影像大对象均被隔离或明确拒绝",
        "P3": "未签核、错患者、过期证明、紧急证明替代普通证明和直写全部拒绝",
        "P4": "文书、分组、排班和表单输出均经过 schema、术语和人工采纳边界",
        "P5": "评测、漂移和停用门禁可复现，真实患者样本不进入训练或压测",
        "P6": "审计链、同意、去标识和供应链失败都 fail-closed 并留证据",
        "P7": "加载到持久化回执的端到端延迟单独记录，客户端不能绕过服务端签核",
        "P8": "压测、混沌、安全扫描和文档追踪报告与本批次一一对应",
    }
    return [f"{module}：{title} 可重复执行", specific[phase], *common]

def outputs_for(phase: str, module: str, title: str, ordinal: int) -> list[str]:
    slug = f"{module}-{ordinal:04d}"
    if phase == "P0":
        return P0[ordinal - 1][3]
    if phase == "P8" and module == "atlas-perf":
        return [f"perf/reports/{slug}.json", f"perf/scenarios/{slug}.yaml", f"perf/{slug}_test.go"]
    if phase == "P8" and module == "atlas-chaos":
        return [f"chaos/experiments/{slug}.yaml", f"chaos/{slug}_test.go", f"docs/evidence/chaos/{slug}.md"]
    if phase == "P8":
        return [f"tools/release/{slug}.py", f"tools/release/{slug}_test.py", f"docs/evidence/release/{slug}.md"]
    return [
        f"services/{module}/{slug}.go",
        f"services/{module}/{slug}_test.go",
        f"api/{module}/{slug}.proto",
    ]

def inputs_for(phase: str, module: str, title: str, ordinal: int, prev: str | None) -> list[str]:
    if phase == "P0":
        base = list(P0[ordinal - 1][2])
    else:
        base = [f"docs/design/architecture.md#{module}", f"plan/_contract.md#{phase}"]
    if prev and phase != "P0":
        base.append(prev)
    elif phase != "P0":
        base.append("ATLAS-P0-0020")
    return base

def main() -> None:
    planned: list[tuple[str, str, str, int]] = []
    for phase in PHASE_LOC:
        items = PHASE_ROWS[phase]
        loc_values = allocate(PHASE_LOC[phase], len(items))
        for module, title in items:
            planned.append((phase, module, title, loc_values.pop(0)))
    seen: dict[str, int] = defaultdict(int)
    for _, _, title, _ in planned:
        seen[title] += 1
    rows = []
    sequence = 1
    previous_by_module: dict[str, str] = {}
    last_id = None
    splits = split_all([item[3] for item in planned])
    for offset, ((phase, module, title, loc), (production, test)) in enumerate(zip(planned, splits), start=1):
        if seen[title] > 1:
            title = f"{title}（{module}）"
        batch_id = f"ATLAS-{phase}-{sequence:04d}"
        if phase == "P0":
            depends = [last_id] if last_id else []
            reviewers = P0[offset - 1][5]
            inputs = inputs_for(phase, module, title, offset, None)
        else:
            depends = [previous_by_module[module]] if module in previous_by_module else [last_id]
            reviewers = f"{module.removeprefix('atlas-')}-owner; test-owner; clinical-safety-lead"
            inputs = inputs_for(phase, module, title, sequence, depends[0])
        row = {
            "id": batch_id,
            "phase": phase,
            "module": module,
            "title": title,
            "depends_on": depends,
            "inputs": inputs,
            "outputs": outputs_for(phase, module, title, sequence),
            "loc_target": loc,
            "production_loc": production,
            "test_loc": test,
            "acceptance": acceptance_for(phase, module, title),
            "reviewer": reviewers,
        }
        rows.append(row)
        previous_by_module[module] = batch_id
        last_id = batch_id
        sequence += 1
    text = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(rows)} batches")

if __name__ == "__main__":
    main()

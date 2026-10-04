# Atlas 生产级测试策略

> **当前角色**: 测试架构师 / SRE 负责人  
> **本章产出**: 无生产机环境下的分层测试方案  
> **依赖的上游产出**: `plan/milestones.md` MP-01~MP-08、`docs/design/architecture.md`

## 1. 测试分层策略

没有足够生产机时，采用**四层验证模型**：

```
┌─────────────────────────────────────────────┐
│  L4: 云 Spot 实例 (5-10台，$50-100)          │  ← 真实分布式验证
├─────────────────────────────────────────────┤
│  L3: 容器化压测 (Docker Compose 10-20容器)   │  ← 单机极限压测
├─────────────────────────────────────────────┤
│  L2: 仿真建模 (DES/数学证明)                 │  ← 算法正确性
├─────────────────────────────────────────────┤
│  L1: 单元测试 + Chaos (本地)                 │  ← 逻辑正确性
└─────────────────────────────────────────────┘
```

## 2. 八大压测剧本的替代方案

### MP-01: 稳态门诊高峰 (26万 QPS × 8h)

**生产方案**: 13 台 FHIR 服务器  
**替代方案**:

```yaml
# L3: Docker Compose 单机压测
services:
  atlas-fhir:
    image: atlas:latest
    deploy:
      replicas: 4  # 单机 4 实例
    environment:
      - GOMAXPROCS=2
  
  loadgen:
    image: vegeta:latest
    command: ["-duration=8h", "-rate=5000", "-connections=1000"]
```

**验证指标**:
- 单实例 QPS × 4 = 实测吞吐
- 外推到 13 实例的线性扩展系数
- P99 延迟分布（loopback 网络需加 5-10ms 模拟真实网络）

**可信度**: 中（内核瓶颈非网络）

---

### MP-02: 建索引风暴 (2h 新增 100万患者)

**生产方案**: 26 台 EMPI 实例  
**替代方案**:

```bash
# L1: 单元测试 + 属性测试
go test -run TestEMPI_BulkImport -v \
  -count=10000 \
  -timeout=2h
```

**验证指标**:
- 消歧准确率（合成金标准集）
- 误合并率（注入 1% 相似记录）
- 内存增长曲线

**可信度**: 高（算法层面）

---

### MP-03: 监护洪峰 (10万设备 100万点/秒)

**生产方案**: 6 台时序库  
**替代方案**:

```python
# L2: 离散事件仿真
from simpy import Environment

def simulate_device_flood(env, devices=100000, points_per_sec=1000000):
    """模拟设备数据洪流"""
    for i in range(devices):
        env.process(device_stream(env, device_id=i))
    
    # 验证告警延迟分布
    yield env.timeout(3600)  # 1小时仿真
```

**验证指标**:
- 告警丢失率（应为 0）
- 端到端告警 P99（仿真时间）
- 背压机制有效性

**可信度**: 高（逻辑正确性）

---

### MP-04: 审核并发 (5000审核者)

**生产方案**: 13 台审核服务  
**替代方案**:

```yaml
# L4: 云 Spot 实例 (5台)
services:
  atlas-hitl:
    replicas: 5
  
  k6-loadgen:
    image: grafana/k6
    command: ["run", "/scripts/review-concurrent.js"]
    environment:
      - VUS=1000  # 每实例 1000 虚拟用户
```

**验证指标**:
- 加载+提交端到端 P99 < 500ms
- 重复签核 = 0
- 丢签 = 0

**可信度**: 高（真实分布式）

---

### MP-05: 审计洪峰 (20亿事件/天 × 24h)

**生产方案**: 104 台审计服务  
**替代方案**:

```go
// L1: 哈希链单元测试
func TestAuditChain_Integrity(t *testing.T) {
    chain := NewAuditChain()
    
    // 写入 100万事件
    for i := 0; i < 1000000; i++ {
        event := generateSyntheticEvent(i)
        chain.Append(event)
    }
    
    // 验证哈希链连续
    assert.True(t, chain.Verify())
    
    // 注入篡改，验证检出
    chain.Tamper(500000)
    assert.False(t, chain.Verify())
}
```

**验证指标**:
- 哈希链连续（单元测试）
- WORM 不可覆盖（mock 存储层）
- 写入吞吐（单机极限）

**可信度**: 高（逻辑正确性）

---

### MP-06: 急诊故障 (杀30%节点 + 丢1AZ)

**生产方案**: 多 AZ 部署  
**替代方案**:

```bash
# L3: Docker Compose + Chaos
# 启动 10 容器，随机 kill 3 个
pumba --random kill --signal SIGKILL atlas-fhir

# 验证 RTO < 60s, RPO = 0
```

**验证指标**:
- RTO（恢复时间目标）
- RPO（恢复点目标）
- 数据一致性

**可信度**: 高（chaos engineering）

---

### MP-07: 多院区隔离

**生产方案**: 5 院区联邦  
**替代方案**:

```bash
# L3: tc-netem 网络分区
# 模拟 1 院区满载、4 院区正常
tc qdisc add dev eth0 root netem delay 100ms loss 30%
```

**验证指标**:
- 正常院区 P99 波动 < 10%
- 隔离院区降级可见

**可信度**: 中（网络层模拟）

---

### MP-08: 72小时长稳

**生产方案**: 全量负载 72h  
**替代方案**:

```yaml
# L3: 单机 24h 极限压测 + 外推
duration: 24h
load: 200% 设计容量
metrics:
  - memory_growth < 2%
  - p99.9_drift < 10%
```

**验证指标**:
- 内存泄漏检测
- GC 暂停时间分布
- FD 耗尽风险

**可信度**: 中（时间压缩）

## 3. 工具链清单

| 工具 | 用途 | 成本 |
|------|------|------|
| **pumba** | Docker chaos (kill/延迟/丢包) | 免费 |
| **tc-netem** | Linux 网络故障注入 | 免费 |
| **vegeta** | HTTP 恒定速率压测 | 免费 |
| **k6** | 脚本化负载测试 | 免费 |
| **Locust** | Python 分布式压测 | 免费 |
| **Chaos Mesh** | K8s 原生 chaos | 免费 |
| **SimPy** | 离散事件仿真 | 免费 |
| **Hypothesis** | Python 属性测试 | 免费 |

## 4. 执行计划

### Week 1: L1 单元测试 + Chaos

- [ ] 所有 P0-P6 核心包单元测试
- [ ] 哈希链、状态机、HITL 绕过路径穷举
- [ ] Docker chaos 演练（kill、网络分区）
- **预期**: 发现 80% 的状态机 bug

### Week 2: L3 容器化压测

- [ ] Docker Compose 10-20 容器
- [ ] 梯度加压到单机极限
- [ ] 24h 长稳测试
- **预期**: 找到内存泄漏和 FD 耗尽

### Week 3: L4 云 Spot 实例

- [ ] 5 台 Spot 实例跑真实分布式测试
- [ ] MP-04 审核并发、MP-06 急诊故障
- [ ] 跨节点一致性验证
- **预期**: 发现网络分区和时钟问题
- **成本**: $50-100

### Week 4: L2 数学证明 + 代码审计

- [ ] DRF 算法形式化验证
- [ ] 关键路径延迟分析
- [ ] 安全代码审计
- **预期**: 补齐无法实测的门禁

## 5. 降级验证清单

| 生产门禁 | 单机替代方案 | 可信度 |
|---------|--------------|--------|
| MP-01 26万 QPS | 单实例 × 4 + 外推 | 中 |
| MP-02 100万患者 | 属性测试 + 合成数据 | 高 |
| MP-03 100万点/秒 | 离散事件仿真 | 高 |
| MP-04 5000审核者 | 云 Spot 5台 | 高 |
| MP-05 20亿事件 | 哈希链单元测试 | 高 |
| MP-06 急诊故障 | Docker chaos | 高 |
| MP-07 多院区隔离 | tc-netem 网络分区 | 中 |
| MP-08 72h 长稳 | 24h 极限压测 | 中 |

## 6. 关键风险

1. **单机瓶颈**: 内核 FD 限制、网络栈限制
   - 缓解: `ulimit -n 1000000`、`ip netns` 多命名空间

2. **Loopback 网络**: 无真实网络延迟
   - 缓解: `tc-netem` 注入 5-10ms 延迟

3. **时间压缩**: 24h ≠ 72h
   - 缓解: 200% 负载加速老化

4. **外推误差**: 线性扩展假设
   - 缓解: 云 Spot 验证关键节点

## 7. 下一步

1. ✅ Go 工具链已验证（BLK-001 解决）
2. ⏳ 安装 `buf` 工具进行 protobuf 校验
3. ⏳ 配置 CI 使用 `E:\依赖\go`
4. ⏳ 执行 Week 1 L1 测试
5. ⏳ 申请云 Spot 实例预算

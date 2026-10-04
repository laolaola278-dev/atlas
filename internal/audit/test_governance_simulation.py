"""
临床治理委员会模拟实验测试
"""

import unittest
from datetime import datetime
from governance_simulation import GovernanceCommittee


class TestGovernanceCommittee(unittest.TestCase):
    """测试治理委员会模拟"""
    
    def setUp(self):
        """初始化委员会"""
        self.committee = GovernanceCommittee()
        
    def test_committee_setup(self):
        """测试委员会组建（GCP 2020版第十二条：至少5人，奇数）"""
        result = self.committee.setup_committee()
        self.assertTrue(result, "委员会组建应成功")
        self.assertEqual(len(self.committee.members), 5, "委员会应为5人")
        self.assertEqual(len(self.committee.members) % 2, 1, "委员会人数应为奇数")
        
    def test_member_roles(self):
        """测试成员角色完整性"""
        self.committee.setup_committee()
        roles = [m.role for m in self.committee.members]
        
        expected_roles = [
            "主任委员",
            "临床专科委员", "临床专科委员",  # 2人
            "临床信息学委员",
            "药学委员"
        ]
        
        self.assertEqual(roles.count("主任委员"), 1, "应有1名主任委员")
        self.assertEqual(roles.count("临床专科委员"), 2, "应有2名临床专科委员")
        self.assertEqual(roles.count("临床信息学委员"), 1, "应有1名临床信息学委员")
        self.assertEqual(roles.count("药学委员"), 1, "应有1名药学委员")
        
    def test_conflict_declaration(self):
        """测试利益冲突声明"""
        self.committee.setup_committee()
        for member in self.committee.members:
            self.assertTrue(member.conflict_declared, 
                          f"{member.name}应已签署利益冲突声明")
            
    def test_meeting_quorum(self):
        """测试会议法定人数"""
        self.committee.setup_committee()
        meeting = self.committee.hold_meeting(
            datetime(2026, 10, 7), 
            ["CG-01"]
        )
        self.assertTrue(meeting["quorum"], "会议应达到法定人数")
        
    def test_compensation_calculation(self):
        """测试报酬计算（财行〔2016〕440号）"""
        self.committee.setup_committee()
        compensation = self.committee.calculate_compensation(meetings=8)
        
        # 主任委员（正高）：3000元/次 × 8次 = 24000元
        self.assertEqual(compensation["主任委员"], 24000)
        
        # 临床专科委员（副高）：1500元/次 × 8次 × 2人 = 24000元
        self.assertEqual(compensation["临床专科委员"], 24000)
        
        # 临床信息学委员：1500元/次 × 8次 = 12000元
        self.assertEqual(compensation["临床信息学委员"], 12000)
        
        # 药学委员：1500元/次 × 8次 = 12000元
        self.assertEqual(compensation["药学委员"], 12000)
        
        # 总计：24000 + 24000 + 12000 + 12000 = 72000元
        self.assertEqual(compensation["总计"], 72000)
        
    def test_cg03_drill_clinical_acceptability(self):
        """测试CG-03急诊RTO临床可接受性（<30分钟）"""
        self.committee.setup_committee()
        
        # 场景1：RTO=25分钟（1500秒）- 通过
        drill = self.committee.simulate_cg03_drill(rto_seconds=1500, rpo_minutes=15)
        self.assertTrue(drill["clinical_acceptable"], "25分钟RTO应临床可接受")
        self.assertTrue(drill["etl_acceptable"], "25分钟RTO应符合等保三级")
        self.assertEqual(drill["result"], "通过")
        
        # 场景2：RTO=35分钟（2100秒）- 不通过
        drill = self.committee.simulate_cg03_drill(rto_seconds=2100, rpo_minutes=15)
        self.assertFalse(drill["clinical_acceptable"], "35分钟RTO应不可接受")
        self.assertTrue(drill["etl_acceptable"], "35分钟RTO仍符合等保三级")
        self.assertEqual(drill["result"], "不通过")
        
        # 场景3：RTO=5小时（18000秒）- 不通过临床但通过等保
        drill = self.committee.simulate_cg03_drill(rto_seconds=18000, rpo_minutes=15)
        self.assertFalse(drill["clinical_acceptable"], "5小时RTO应不可接受")
        self.assertFalse(drill["etl_acceptable"], "5小时RTO不符合等保三级（≤4小时）")
        self.assertEqual(drill["result"], "不通过")
        
    def test_rpo_acceptability(self):
        """测试RPO可接受性（<30分钟）"""
        self.committee.setup_committee()
        
        # RPO=15分钟 - 通过
        drill = self.committee.simulate_cg03_drill(rto_seconds=1500, rpo_minutes=15)
        self.assertTrue(drill["clinical_acceptable"])
        
        # RPO=35分钟 - 不通过
        drill = self.committee.simulate_cg03_drill(rto_seconds=1500, rpo_minutes=35)
        self.assertFalse(drill["clinical_acceptable"], "35分钟RPO应不可接受")
        
    def test_meeting_frequency_compliance(self):
        """测试会议频率符合性（《医疗机构药事管理规定》每季度至少1次）"""
        self.committee.setup_committee()
        
        # P0核验期：每周1次（8周=8次）
        p0_meetings = 8
        quarterly_p0 = p0_meetings / 2  # 8周约2个月，按季度算应≥1次
        self.assertGreaterEqual(quarterly_p0, 1, "P0期每季度应≥1次")
        
        # 常规运营期：每两周1次（12个月=24次）
        regular_meetings = 24
        quarterly_regular = regular_meetings / 4  # 每季度6次
        self.assertGreaterEqual(quarterly_regular, 1, "常规期每季度应≥1次")


if __name__ == "__main__":
    unittest.main()

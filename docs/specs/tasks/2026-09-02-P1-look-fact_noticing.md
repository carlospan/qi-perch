# 2026-09-02 · P1：look 深路径二期 · fact_noticing

> Cursor 单线。HITL 真源：审计简报 §〇.37；承 §二 look 深路径收尾。  
> **编码放行**：**已放行 A（2026-09-02）**。

---

## Spec（外部行为）

1. **仅邀瞥**（`reactive=True`）走心流程末尾，对 **impression 原样**调 `memory.notice_facts`。  
2. 与 open_loops enqueue **同拍**；不论主观短说是否出字；失败不挡 look。  
3. 自主瞥不调 notice_facts。  
4. **本刀不做**：改 fact 模板、加前缀、专用 look 抽取、recent_messages。

## 实现（步骤）

1. [x] HITL 齐 + 编码放行  
2. [x] `look_heart._notice_look_facts` + 邀瞥末尾接线  
3. [x] 单测 + pytest  

## 验收（判据）

- [x] 邀瞥走心末尾调 `notice_facts(impression, …)`（单测）  
- [x] 自主瞥不调 notice_facts（单测）  
- [x] notice_facts 失败不挡 look（单测）  
- [x] 短说空仍调 notice_facts（单测）  
- [x] `tests/test_look_heart.py` 绿  
- [ ] （感受）维护者：邀瞥后相关用户事实可被后续对话记起  

## HITL

| # | 议题 | 结论 | 状态 |
|---|------|------|------|
| 0 | 下一刀选题 | **look 续：fact_noticing** | **已拍板 A（2026-09-02）** |
| 1 | 本刀范围 | **仅邀瞥 notice** | **已拍板 A（2026-09-02）** |
| 2 | 抽什么文本 / 怎么防误抽 | **impression 原样** | **已拍板 A（2026-09-02）** |
| 3 | 何时调用 | **走心末尾，与 enqueue 同拍** | **已拍板 A（2026-09-02）** |
| 4 | 本刀 HITL 收口与编码放行 | **收口并编码放行** | **已拍板 A（2026-09-02）** |

## 不含

- fact 模板 / 前缀 / 自主瞥 notice / 专用抽取  

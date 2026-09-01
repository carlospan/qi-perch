# 2026-09-02 · P1：look 深路径二期 · open_loops（事后心事）

> Cursor 单线。HITL 真源：审计简报 §〇.36；承 `2026-08-29-look-所见走心-情绪冲击.md` HITL #4（二期本包）。  
> **编码放行**：**已放行 A（2026-09-02）**。

---

## Spec（外部行为）

1. 成功 look 主观短说前，**读取现有 open_loops** 并参与 express（不再完全无视心事队列）。  
2. **仅邀瞥**（`reactive=True`）且走心完成后 **enqueue** 一条 `look_glance` 心事（seed = impression 前 40 字）；自主瞥只读不写。  
3. 读/写失败 → 不挡 look（与记忆检索刀一致）。  
4. **本刀不做**：fact_noticing、recent_messages 进 express。

## 实现（步骤）

1. [x] HITL 齐 + 编码放行  
2. [x] `look_heart` 读 open_loops + express 接线  
3. [x] `look_heart` 写 enqueue + `build_concern` / evict 优先  
4. [x] 单测 + pytest  

## 验收（判据）

- [x] look express 可收到 loop 素材（单测）  
- [x] 成功瞥后 body_memory open_loops 新增/刷新 look kind（单测）  
- [x] 无 db / 队列失败时行为与现有一致  
- [x] `tests/test_look_heart.py` 绿  
- [ ] （感受）维护者：瞥后短说能带上悬着的心事；事后内在生命能接着想这一眼  

## HITL

| # | 议题 | 结论 | 状态 |
|---|------|------|------|
| 0 | 下一刀选题 | **look 续：open_loops** | **已拍板 A（2026-09-02）** |
| 1 | 本刀范围 | **读+写** | **已拍板 C（2026-09-02）** |
| 2 | 读路径怎么接 | **第一条 loop → loop 素材追加** | **已拍板 A（2026-09-02）** |
| 3 | 写路径（enqueue） | **仅邀瞥 enqueue** | **已拍板 B（2026-09-02）** |
| 4 | 本刀 HITL 收口与编码放行 | **收口并编码放行** | **已拍板 A（2026-09-02）** |

## 不含

- fact_noticing / recent_messages  

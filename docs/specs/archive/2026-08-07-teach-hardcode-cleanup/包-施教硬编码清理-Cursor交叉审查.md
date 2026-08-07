# 施教硬编码清理——Cursor 交叉审查

> **角色**：Cursor（执行侧交叉审查，本轮**不写码**）  
> **依据**：`docs/specs/tasks/2026-08-07-施教硬编码清理.md`、`包-施教硬编码清理-PR方案.md`  
> **对照代码**：`intention.py` / `expression.py` / `culture.py` / `consciousness_stream.txt` + 包 15-17 相关单测  
> **审查时刻**：2026-08-07  

---

## 总判

**方向对（去睡眠内容墙、对齐 contract 护栏），可编码前须收紧 §3.3 叙事并补全测试改动面。**

删 prompt/fallback/culture 里的「数到七」「躺着/看天花板」是真清理。但把 `detect_sleep_*` 改名却**原样保留** `_INVERT_TOPIC_RE`，再验收「你教过我弹吉他」——**实现与验收互相打架**；既有负例单测也明确不拦非睡眠「你教我写代码」。

---

## 认可

1. 违规清单对得上现行代码；与此前「助眠焊死 vs N5 铁律」判断一致。  
2. 保留 `infer_recall_relation` / `anchor_teaching_relation` / `recall_relation` ——对；真通用闸已在 `assert_reply_respects_card`（`card.recall_relation == "taught_by_qi"` + 反转句式）。  
3. culture / consciousness_stream / expression 文案去细节——正中 contract「少靠不准说清单」。  
4. HITL 无、去债不改架构——同意。

---

## 必须整改（阻塞编码）

### B1. §3.3「泛化」名不副实，且与新单测/旧负例冲突

现状与改后伪码**同为**：

```text
_INVERT_TAUGHT_BY_QI_RE ∧ _INVERT_TOPIC_RE
_INVERT_TOPIC_RE = 入睡|睡不着|失眠|睡|方法|法子
```

既有（须保留语义）：

```text
not detect_sleep_teach_inversion("你教我写代码的样子很认真")  # True：故意不拦
```

方案却写：新增「你教过我弹吉他」也能检出——**按保留的 topic 正则会失败**（无「方法/睡/法子」则 False）。

**整改（三选一，写进方案，勿只改名）**：

| 选项 | 做法 | 建议 |
|------|------|------|
| **A（推荐）** | 本包只做**内容去硬编码**（§3.1/3.2/3.4）；`detect_*` 可 rename + 别名，**不宣称**话题泛化；删「弹吉他」验收条；负例「写代码」仍绿 | 范围清晰，风险低 |
| **B** | 真泛化：`detect_teach_inversion(text, relation=…)`——有 `taught_by_qi` 则只靠反转句式；无卡时才用 topic 启发式。同步改「写代码」类负例的适用前提 | 对齐卡内闸，工作量大一点 |
| **C** | 扩 `_INVERT_TOPIC_RE` 到任意「教」——易误伤真实「你教我写代码」，**不推荐** | — |

推荐 **A**；若要坚持「弹吉他」，必须走 **B** 并改测试矩阵。

### B2. §3.5 漏改必红单测

落地必碰（方案应点名）：

| 文件 | 现状 | 清理后 |
|------|------|--------|
| `tests/test_relationship.py` | `assert "躺着/不强迫/看天花板" in block` | 改为断言方向锤**不含**该原话，仍含「栖教用户」「勿反转」 |
| `tests/test_inner_life.py` | `assert "数到七" in prompt`（因 stream 硬约束句曾点名） | 改为 **`not in`**，并保留「不得添加锚定里没有的细节」 |
| `tests/test_expression.py` 等 | 若断言旧 FALLBACK 全文含「入睡/躺着」 | 跟新模板改断言；行为「违规→模板」不变即可 |

「既有测试不变」写过头了——**行为不变，字符串断言会变**。

### B3. 索引卫生

- `specs/tasks/README.md` 现行未列本任务（仍只有 N5-b）。  
- `specs/archive/INDEX.md` 未挂本桶。

---

## 建议（不阻塞，若选 A 可顺手）

### S1. §1 vs §2 对 `_SLEEP_ADVICE_RE`

§1 列入违规清单，§2/红线又保留——请改成：**保留作 anchor 启发式（识别助眠建议证据），本包不删；违规的是把它写进 prompt/fallback。** 避免审查读成「清理了又没清」。

### S2. FALLBACK 仍默认「是我教你的」

通用化后若违规来自空卡编造，模板仍宣称「我教你」略武断。可接受为过渡；更干净则按 `card.recall_relation` 分支一句，或中性「这个方向以记忆为准，我不会跟着说反」。非本包必做。

### S3. CONSTRAINT 提 `taught_by_qi`

比写死「入睡方法」好；注意重生约束里对模型露出内部枚举名——可改成「若卡标明栖教用户」中文，少露标识符（品味，非阻塞）。

### S4. N5-b 任务状态

N5-b 仍在 tasks 现行；本包依赖写 N5-b ✅。若方案验收已过可迁档；未过则依赖改为「编码已合入、待/已验收」以免假闭环。不阻塞本包审查。

---

## 对进度表

| 步骤 | 建议 |
|------|------|
| Cursor 交叉审查 | ✅ 本文件 |
| 方案整改 | 待 CodeBuddy：**至少关闭 B1、B2**（B3 可 Cursor 编码时顺手） |
| Cursor 编码 | **阻塞至 B1/B2 落盘** |

---

## 一句话给方案 Agent

内容墙该拆；**别把 rename 说成泛化**。要么本包只清文案（推荐），要么做卡感知的真泛化并改测试矩阵——「弹吉他」与「写代码不拦」不能两头要。

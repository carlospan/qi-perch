# L7 curiosity 候选解堵——整改复审

> **角色**：Cursor（执行侧整改复审，本轮**仍禁码**）  
> **依据**：修订后 [PR 方案](./2026-08-08-L7-curiosity候选解堵-PR方案.md)（§二 D/E、§四、§七）+ [任务包](./2026-08-08-L7-curiosity候选解堵.md) 验收栏 + [交叉审查](./2026-08-08-L7-curiosity候选解堵-Cursor交叉审查.md)  
> **时刻**：2026-08-08  

---

## 总判

**B1 / B2 均已关闭。方向 A 维持。整改复审通过。**  
仍禁码，待方案 Agent 落 `-编码请求.md` + 明示可编码后再动 `qi/`。

---

## 阻塞项逐条核对

| 项 | 交叉审查要求 | PR 修订落点 | 状态 |
|----|--------------|-------------|------|
| **B1** | 点名翻改 `test_collect_contenders_curiosity_gate` L127 → `assert not any(...)`；验收面含测试文件 | §二 D、§四测试段、§七表；任务包验收「git diff = trace + test_motivation_curiosity + docstring + 文档」 | **关闭** |
| **B2** | 删「arbitrate 选 share」拟新增测；防回归靠 collect 不含 curiosity；可选说明性测（证 curiosity 仍会赢） | §四明确删除该测；防回归只靠 B1；可选手造 contenders 说明性测（不要求选 share） | **关闭** |

无未关闭阻塞项，**不退回**方案 Agent。

---

## 非阻塞采纳核对

| # | 状态 | 备注 |
|---|------|------|
| N1 | 已采纳 → §二 E | docstring 微调；`contender()` 不删 |
| N2 | 已采纳 | 验收面与任务包一致 |
| N3 | 已采纳 | 测落 `test_motivation_curiosity.py` |
| N4 | 已采纳 | 维持 A |

**保留项**（审查认可）：`salience(kind="curiosity")` 默认保留；`contender()` 不删。编码时**勿**因「注入删除」清理 salience 分支（`test_salience_curiosity_branch` 仍用）。

---

## 编码前理解确认（仍禁码）

获编码请求 + 明示可编码后，将按修订后 PR：

1. **A**：删 `trace.py` `collect_contenders` 包 10 注入块（~L517–525），`curiosity` 形参保留。  
2. **B**：`salience(kind="curiosity")` **不动**。  
3. **D**：翻改 `test_collect_contenders_curiosity_gate` L127 → `not any`；不新增「arbitrate 选 share」。  
4. **E**（可选但方案已写进改动点）：`curiosity.py` 模块 docstring 一句回退说明。  
5. **C**：回写 L7-action.md / progress.md / 排查包文首。  
6. **F**：不改 gws / brain / volition / curiosity 计算 / settings。

可选说明性测：编码时按时间与价值决定是否加；不加不阻塞验收。

---

## 下一拍

1. 方案 Agent 落 `-编码请求.md`（以修订后 PR 为准）。  
2. 维护者 / 方案明示可编码 → Cursor 编码 → `-Cursor编码回执.md` 完工段。  
3. 维护者可异步追认方向 A（不阻塞本复审结论）。

**Cursor 结论**：B 项关闭，复审通过；**等待编码请求与明示可编码。**

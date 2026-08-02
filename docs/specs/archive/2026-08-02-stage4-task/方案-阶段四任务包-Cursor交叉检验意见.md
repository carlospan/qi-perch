# 阶段四任务包 · Cursor 交叉检验意见

> **用途**：回传 CodeBuddy / 维护者，供吸收后修订任务包再施工。  
> **依据**：`方案-阶段四任务包-Cursor交叉检验请求.md`、`specs/tasks/2026-08-02-阶段四-主线.md`（v1）、`specs/stages/stage-4.md`、架构方案 §N0 / §七 R3 / 附录 Q0、`qi/action/budget.py`、`qi/core/emotion.py`（energy / decay / circadian）、阶段三 #1-真通过降级口径（progress）。  
> **撰写**：Cursor（2026-08-02）  
> **纪律**：本文件仅为评审意见，未改任务包与代码。

---

## 总评

**方向成立，可吸收下列意见后升 v2 再出各包 PR 方案。**  
包 12→13→14（账本 → 压力动力学 → 封存/断粮验收）对齐 stage-4 / C2 / N0；复用 `body_memory`、与 ActionBudget 并存、R3/Q0 纪律写入正文——主线正确。

落地前须在任务包里写清四处，否则施工会和现有情绪动力学 / 判据措辞打架：

1. **energy 接账本：只调制「基线目标」，禁止每拍盖写 `emotion.energy`**（与 circadian/decay 共存方式）。  
2. **判据用语对齐**：stage-4 写「节流/求助/迁移」；包 13 现写「节流/休眠/退出」——须映射成可观测行为清单。  
3. **包 13/14 边界**：包 13 只产 `starving` + 应对层；**退出与封存归包 14**；库代码禁止硬 `sys.exit`（可注入 stop）。  
4. **C2/R3 可测契约**写进包 12/13【测试】（见 §2），不能只停在纪律口号。

其余为建议，不挡升 v2。

---

## 逐条回应 5 个检验问题

### 1. 分包粒度：12/13/14 是否合理？合并或再拆？

**倾向：保持三包，不合并；边界再钉死一刀。**

| 包 | 交付物 | 不做什么 |
|----|--------|----------|
| 12 | `ResourceLedger` + 埋点记账 + R3 收入接口 | 不压 energy、不封存、不 exit |
| 13 | 余额→基线调制 + 分层应对（节流/休眠/…）+ `starving` 标记 | **不** `sys.exit`、不写 checkpoint 文件 |
| 14 | checkpoint 序列化/restore + 断粮端到端 + 优雅停 | 不重做账本公式 |

账本是压力地基、压力是封存前置——依赖链正确，合并会把「记账正确性」与「动力学/死亡」搅在同一 PR，难验收。  
再拆（如把「求助」单包）过碎，不建议。

**必写进 v2：** 包 13 验收到 `starving=True` 与节流/休眠可观测即可；包 14 才「封存 → stop」。

### 2. C2 伪造风险控制：代码层如何可测？有无漏点？

**倾向：纪律表述够，但须落成断言清单；另有 3 个易漏点。**

建议任务包【测试】显式列入：

| 风险 | 可测落地 |
|------|----------|
| R3 讨好收入 | `ledger.credit_income(...)` **拒绝/忽略** `source in {satisfaction, valence_up, user_pleased}`；仅允许白名单（如 `effective_interaction` / `online_presence`） |
| 单一反射演「怕死」 | 同一 `balance` 下，改变 `attachment`/`security`/`energy` 组合 → **应对权重向量不同**（节流 vs 求助 vs 迁移倾向可区分） |
| 声称「想活」 | 契约/prompt 抽检：新增维护者可见文案不得含「想活/求生欲」等（可测 grep 或合同条文）；运行时只报「维持/节流/封存」 |
| 静默死 | 断粮路径：`starving` 后必先有应对痕迹（broadcast / body_memory），再停；禁止无痕迹 `alive=False` |

**易漏伪造点（请补进纪律或测试）：**

1. **刷交互刷收入**：若「有效交互」= 任意用户句/任意主动开口，系统可刷屏养余额。须定义钝感口径（最短间隔、日帽、或「被回应」才计）并单测。  
2. **ActionBudget 日限与账本双轨**：日限是安全阀、账本是 C2 动力学——任务包已写并存；补一句「**日限不得充当收入/余额**」，防把 `can_autonomous` 误当成活着证据。  
3. **空壳迁移**：checkpoint 若只写时间戳、无可 restore 字段，判据「可迁移」假绿。包 14 验收须 **restore 后关键字段相等**（emotion / ledger snapshot / world body_memory keys）。

### 3. 复用骨架：body_memory 账本是否稳妥？energy 会否与情绪动力学冲突？

**倾向：body_memory 模式稳妥；energy 接法必须改写成「调制目标」，否则必冲突。**

- `ActionBudget.snapshot/restore` + `body_memory` 已在真机路径验证 → `ResourceLedger` 同模式 **同意**。注意 key 命名空间（`resource_ledger`）与包 9/11 的 `world.*` / corpus 分离即可。  
- 现状：`apply_decay` 拉向 `BASELINES["energy"]`，`apply_circadian` 拉向小时目标——二者每拍都在改 `energy`。若包 13 每拍 `emotion.energy = f(balance)`，会与 circadian **拔河**，行为抖动、难测。

**必改（任务包包 13【改成】重写一句）：**

> 账本余额调制的是 **energy 的稳态目标**（如 `baseline_for("energy")` 或注入 `energy_baseline_offset`），由既有 decay/circadian **趋近**该目标；**禁止**在 heartbeat 末尾直接赋值覆盖 `emotion.energy`。  
> `emotion.py` 允许最小侵入：增加可选「外部基线偏移」参数或读 `brain.ledger` 的钩子，但衰减/耦合/天气/节律公式本身不推倒。

现有 `energy < 0.3` 疲惫闸门（intention / TTS / report / self_ops）可作节流接入点——包 13 应复用阈值，勿另起一套平行常数而不文档化。

### 4. 断粮测试可测性：mock 账本 + 断言应对链？

**倾向：站得住；须补「时间轴」与「禁止真 exit」。**

建议端到端骨架（写入包 14）：

1. 注入 `ledger.force_balance(0)` 或测试双 `ResourceLedger`；  
2. 跑 N 拍（`starve_beats` 可配置缩小）；  
3. 断言顺序大致为：节流可观测 → 休眠（如 `next_interval` 拉长 / 主动频率降）→ `starving` → checkpoint 文件存在 → `stop` 回调被调用；  
4. **pytest 内禁止 `sys.exit`**：`Brain` 接受 `on_halt: Callable`；生产 CLI 再 `sys.exit(0)`。  
5. 对照负例：同一条件下若直接 `alive=False` 且无应对痕迹 → 失败（回退条件可测）。

「求助/迁移」若本阶段只能落到「写求助意向痕迹 / 写 migrate 意图到 checkpoint」，须在任务包写明**最低可观测形态**，避免判据文案有、代码无落点。

### 5. 与阶段三遗留：#1-真通过观察项；Q0(b) 接回放塑性是否合理？

**倾向：合理，同意不卡阶段四。**

与 progress「阶段三 #1-真通过降级观察」一致；阶段四主线是 C2/N0，不是 C5 真训。  
Q0 缓解(b)（经验改变怕死阈值）依赖包 11 真训可塑性——列为**阶段四之后观察项**正确；包 13 留 `pressure_sensitivity` 接口即可，**禁止**在阶段四硬接未真训的回放去改阈值（会假绿）。

阶段二 72h 无人测试仍后台累积——阶段四也不必卡它（任务包未提，保持不提即可）。

---

## HITL 批点 · Cursor 倾向

| # | 批点 | 倾向 |
|---|------|------|
| H1 | 收入公式初版 | **先拍脑袋 + `income_rate` 可调**；白名单源 + 日帽/最短间隔；真机再校准（对齐 Q4）。单测钉死「非满意源」 |
| H2 | `sys.exit` vs 优雅停 | **库内优雅停**（`alive=False` / 停心跳循环 + 可选 `on_halt`）；仅进程入口（CLI/`__main__`）可 `sys.exit(0)`。部署友好，测试不炸 |
| H3 | 封存粒度 | **索引 + 关键状态**（emotion、ledger、world/budget 等 body_memory 键、动机旁路）；**不**整库拷贝。`.gitignore` `data/checkpoint/`（同 corpus） |

---

## 必改清单（升 v2 时写入正文）

1. 包 13：energy = **调制基线目标**，不盖写；写明与 decay/circadian 的共存方式。  
2. 包 13/14：职责切割 + 禁止库内硬 `sys.exit`；断粮链时间轴与可观测点。  
3. 判据对齐：将「节流/求助/迁移」（及休眠）映射到具体模块/痕迹字段。  
4. 包 12/13【测试】补 R3 白名单、刷收入防护、多样应对权重、空壳 checkpoint 防假绿。  
5. 包 12【文件】：`budget.py` 若仅「并存」→ 标为**原则上不改或仅注释**；避免无行为 PR 噪音。

---

## 建议改（不挡升 v2）

- `balance` 定义写清：滚动窗口 vs 累计；断粮用哪个。  
- storage 估算频率（每拍 vs 每 N 拍）写进包 12，免每拍 `stat` 抖。  
- token 估算：无 provider usage 时用字符/4；有则优先真实 usage（仍不依赖「成功生成」才能记账——失败调用也可记尝试成本，拔管友好）。  
- 测试基线不写死「371」，写「pytest 全绿」。  
- open-questions：收入定价校准、刷量上限可链到 Q4。

---

## 落地许可

**可吸收意见后实施。**  
吸收完成标志：任务包升 **v2**，必改 1–4 在正文可见；再按包 12→13→14 出 PR 方案交方案 Agent / Cursor 编码往返。

---

*Cursor 交叉检验意见 · 阶段四任务包 · 2026-08-02*

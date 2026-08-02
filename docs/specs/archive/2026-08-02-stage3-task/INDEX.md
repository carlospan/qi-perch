# archive/2026-08-02-stage3-task · 阶段三任务包史料

> 本目录归档阶段三（换心：内生认知）任务包相关过程稿。
> 归档不删（对齐 OpenSpec / GitHub Spec Kit）。

## 包含

- `方案-阶段三任务包-Cursor交叉检验请求.md` —— 阶段三任务包草稿 v1 的 Cursor 交叉检验请求
- `方案-阶段三任务包-Cursor交叉检验意见.md` —— Cursor 意见（方向成立，3 必改 + 4 建议；许可吸收后实施）
- `包9-PR方案-Cursor编码请求.md` —— 包 9 实施 PR 方案，供 Cursor 自行读取落地的编码请求
- `包9-PR方案-Cursor编码回执.md` —— Cursor 落盘回执（开工前理解确认 + 完工结果，9 passed / 343 passed / ruff 全过）
- `包9-PR方案-CodeBuddy验收记录.md` —— 方案 Agent 实施验收记录（实测核对，验收通过 ✅）
- 任务包本体 `specs/tasks/2026-08-02-阶段三-主线.md`（v2：包 9 收在线节律 / 9b 情绪轨迹观察项 / 包 10 补随机审计三栏 / 判据 #1 拆地基·真通过）
- 包 9 实施 PR 方案 `specs/tasks/2026-08-02-阶段三-包9-PR方案.md`（方案 Agent 出方案，Cursor 编码）
- 包 10 实施 PR 方案 `specs/tasks/2026-08-02-阶段三-包10-PR方案.md`（方案 Agent 出方案：learning-progress 好奇替换随机数，含随机审计三栏表）
- `包10-PR方案-Cursor编码请求.md` —— 包 10 实施 PR 方案，供 Cursor 自行读取落地的编码请求
- `包10-PR方案-Cursor编码回执.md` —— Cursor 落盘回执（开工前理解确认 + 完工结果，12 passed / 355 passed / ruff 全过）
- `包10-PR方案-CodeBuddy验收记录.md` —— 方案 Agent 实施验收记录（实测核对，验收通过 ✅）
- 包 11 实施 PR 方案 `specs/tasks/2026-08-02-阶段三-包11-PR方案.md`（方案 Agent 出方案：经验回放管线，语料版本化 + 异时测试骨架 + 训练默认隔离）
- `包11-PR方案-Cursor编码请求.md` —— 包 11 实施 PR 方案，供 Cursor 自行读取落地的编码请求
- `包11-PR方案-Cursor编码回执.md` —— Cursor 落盘回执（开工前理解确认 + 完工结果，10 passed / 365 passed / ruff 全过）
- `包11-PR方案-CodeBuddy验收记录.md` —— 方案 Agent 实施验收记录（实测核对，#1-地基验收通过 ✅；#1-真通过待 HITL）

## 脉络

1. 阶段二已退出，进入阶段三（架构方案 §五 / `specs/stages/stage-3.md`）
2. 起草任务包 → Cursor 交叉检验（3 必改 + 4 建议）→ 任务包升 v2
3. 包 9 出 PR 方案（方案 Agent）→ Cursor 落地 → 方案 Agent 实测验收通过 ✅
4. 包 10 出 PR 方案（方案 Agent）→ Cursor 落地 → 方案 Agent 实测验收通过 ✅
5. 包 11 出 PR 方案（方案 Agent）→ Cursor 落地 → 方案 Agent 实测验收通过 ✅（交付 #1-地基）
6. 收尾：包 9b（情绪轨迹观察项，不阻塞）

> 已完成：包 11 编码回执落盘，方案 Agent 实测核对（代码+pytest+ruff+grep 心跳未调用训练+gitignore+drift_check）后验收通过（#1-地基），维护者未介入编码检查（符合 SDD-GUIDE 2.3）。
> **HITL 待办**：判据 #1-真通过（显式训练一次 或 正式降级为观察项）需维护者届时拍板——这是阶段三唯一剩余硬决策点。
> 协作分工：方案 Agent 出方案/验收，Cursor 固定执行编码（详见阶段三主线文档「协作分工」段 / `specs/SDD-GUIDE.md` 第二节，减少双方负担）。

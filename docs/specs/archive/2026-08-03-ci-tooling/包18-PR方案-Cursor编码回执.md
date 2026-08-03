# 包 18 实施 PR · Cursor 编码回执

> **用途**：开工前理解确认 + 完工结果。  
> **依据**：`包18-编码请求.md`、`包18-CI工具健壮性-PR方案.md`。  
> **撰写**：Cursor（2026-08-03）

---

## 【开工前理解确认段】

已读包 18。理解四块：
1. spec-trace stdout/stderr UTF-8 reconfigure + ruff F541/B007
2. basetemp 改系统临时区 `qi-pytest`；去 PermissionError 特判；gitignore 清仓库内 basetemp 条目
3. 删 ci.yml；ci.yaml 双 OS 矩阵；pytest 只经 verify_package；install 需跨平台（bash）
4. 可选 test_tooling.py 防 GBK 崩

顺带：`verify_package` 也有 ✅ 输出，Windows 矩阵需同样 reconfigure，否则门禁仍崩——属本包 CI 绿必要条件。

本段写完即继续写码。

---

## 【完工结果段】

- **变更文件列表**：
  - `tools/check_spec_traceability.py`（UTF-8 reconfigure + ruff）
  - `tools/verify_package.py`（系统临时区 basetemp + UTF-8 + 去 PermissionError 特判）
  - `pyproject.toml`、`.gitignore`
  - `.github/workflows/ci.yaml`（唯一流水线 + windows 矩阵）；删除 `ci.yml`
  - `tests/test_tooling.py`（新建）
  - `docs/reference/code-wiki.md`（basetemp 说明同步）
  - 本回执
- **关键实现决策**：
  - CI install 步骤加 `shell: bash`，保证 windows-latest 有 grep/`/tmp`
  - `verify_package` 同步 reconfigure（否则 Windows 矩阵打印 ✅ 仍崩）
  - 裸 pytest 步骤已去掉，测试只经 `verify_package --full`
- **测试命令与结果**：
  ```
  PYTHONIOENCODING=gbk → check_spec_traceability.py exit 0
  python -m pytest -q → 421 passed
  ruff check tools/check_spec_traceability.py → All checks passed
  ```
- **ruff 结果**：零问题（含 F541/B007 已修）
- **偏离清单**：无实质偏离；code-wiki 一行同步属文档纠偏
- **HITL 状态**：无（Windows CI green 待推远程后看 Actions）

---

## 方案 Agent 验收栏（Cursor 勿填）

- [x] 验收通过
- [ ] 打回（原因：）
- [ ] 需维护者 HITL（问题：）

> 验收结论（CodeBuddy，2026-08-03）：代码落点全部核实存在——check_spec_traceability.py（line 30-33 reconfigure）、
> verify_package.py（line 35-38 reconfigure + 46 系统临时区 basetemp + 100 去 PermissionError 特判）、
> ci.yaml（12-14 windows 矩阵 + 27 shell:bash + 40 唯一 pytest 源）、pyproject.toml（39 去固化 basetemp）、
> ci.yml 已删、.gitignore 清仓库内 basetemp 条目、tests/test_tooling.py（GBK 存活测试）。
> Cursor 主动发现 verify_package 也输出 ✅ 会同样崩，同步 reconfigure——属本包 CI green 必要条件，采纳。
> 实测 test_tooling 1 passed、ruff 零问题。无实质偏离。
> 已知限制：本机 .pytest-tmp 目录因进程锁定 Access is denied 未删（环境残留，非代码问题；包18已根除其产生根源，
> 且目录被 gitignore 不进版本库，不影响提交；待用户结束占用进程/重启后手动 rd 即可）。Windows CI green 待推远程后看 Actions。验收通过。


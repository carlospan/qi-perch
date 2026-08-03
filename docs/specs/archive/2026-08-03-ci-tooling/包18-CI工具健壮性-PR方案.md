# 包 18：CI / 工具健壮性（Windows 矩阵 + basetemp 改系统临时区 + 双 CI 合并 + P3 ruff）

> 类型：CI/工具修复（非功能）｜依赖：包 12（basetemp 固化）、包 15/16/17 已 ✅
> 关联：OpenCode 系统层审查 P3 项 + 用户本地 Windows 实测
> 纪律：仿包 15/16/17——先方案、Cursor 编码、04 验收 Agent 独立验收

## 0. 一句话

用户本地 Windows 实测暴露四类工具问题：① `check_spec_traceability.py` 输出 ✅/❌ emoji 在 GBK 控制台 `UnicodeEncodeError` 崩溃（CI 仅 ubuntu 未暴露）；② 仓库内 `.pytest-tmp` 有 ACL 损坏风险（用户实测 23 测试 ERROR）；③ 双 CI workflow 重复跑 doc-link + pytest 两遍；④ `check_spec_traceability.py` 有 3 处 ruff 告警。本包一次修完。

## 1. 三方/实测核实结论

| # | 问题 | 属实度 | 铁证 |
|---|------|--------|------|
| 1 | Windows GBK 崩溃 | ✅ 属实 | `check_spec_traceability.py` line 95/109/111 输出 ✅/❌；Windows 默认 stdout GBK 无法编码；CI 仅 `ubuntu-latest`（ci.yml:10 / ci.yaml:10） |
| 2 | .pytest-tmp ACL | ⚠️ 属实 | 用户实测 23 ERROR + 换 basetemp 全绿；本机 `search_file` 扫 `.pytest-tmp` 报 `EPERM`（权限损坏）实锤；`pyproject.toml:40` 固化仓库内 basetemp |
| 3 | 双 CI 冗余 | ✅ 属实 | `ci.yml`（ruff+pytest+doc-link）与 `ci.yaml`（doc-link+verify_package--full+spec-trace），扩展名不同被视为两文件；doc-link 重复、pytest 跑两遍 |
| 4 | P3 ruff×3 | ✅ 属实 | 实测：`F541` line 95、`B007` line 108/110（已 ruff 验证） |
| 5 | ChromaDB warning | ✅ 属实 | 上游 `chromadb>=0.5` 依赖链，非本项目；CI 不 fail on warning，**不修** |
| 6 | lock 本地路径 | ✅ 属实 | `requirements.lock:100` 含 `-e d:\animus-soul-py-git\...`；CI 已 `grep -vE` 剥离（ci.yaml:26），**不修** |

## 2. 根因

- #1：`check_spec_traceability.py` 未做 stdout 编码重配置，依赖运行环境默认编码。
- #2：包 12 时为避 Windows 系统临时区清理 `PermissionError`，把 basetemp 固化到仓库内 `.pytest-tmp`（`pyproject.toml:40` + `verify_package.py:39,73,77`）。反致仓库内目录被杀软/索引器锁定时 ACL 损坏、无法删除。事实层面**系统临时区由 OS 管理更稳**。
- #3：历史上分别建了 `ci.yml`（早期）与 `ci.yaml`（包 12 串脚本时），未合并。
- #4：`check_spec_traceability.py` 写时未过 ruff（f-string 无占位符 / 循环变量未用）。

## 3. 修复方案（最小、仿包纪律）

### 3.1 Windows 矩阵 + stdout 编码重配置
- `check_spec_traceability.py` 头部（line 26 `import sys` 后）加：
  ```python
  if hasattr(sys.stdout, "reconfigure"):
      sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  if hasattr(sys.stderr, "reconfigure"):
      sys.stderr.reconfigure(encoding="utf-8", errors="replace")
  ```
  两平台（ubuntu 默认 utf-8 / windows GBK）均安全，emoji 在 GBK 下转 `?` 不崩。
- 合并后的 CI workflow 加矩阵：
  ```yaml
  strategy:
    matrix:
      os: [ubuntu-latest, windows-latest]
  runs-on: ${{ matrix.os }}
  ```

### 3.2 basetemp 改系统临时区
- `pyproject.toml:40`：
  ```toml
  # 用系统临时区子目录，规避仓库内 .pytest-tmp 的 Windows ACL 损坏风险（用户实测 23 ERROR）
  addopts = "-p no:cacheprovider --basetemp={tempfile.gettempdir()}/qi-pytest"
  ```
  ⚠️ pyproject 不支持 `{tempfile...}` 插值——改为在 `tests/conftest.py` 用 `pytest` 钩子注入，或保持 `--basetemp` 由 `verify_package.py` 与 CI 传参。
  **确定做法**：`pyproject.toml` 移除固化 basetemp（恢复默认系统临时区）；`verify_package.py` 与 CI 显式传 `--basetemp=$TMPDIR/qi-pytest`（OS 临时区）。
- `verify_package.py:39,73,77`：将 `BASETEMP_DIRNAME = ".pytest-tmp"`（仓库内）改为系统临时区：
  ```python
  import tempfile
  basetemp = Path(tempfile.gettempdir()) / "qi-pytest"
  ```
  删除 line 86-95 的 PermissionError 误报 hack（改系统临时区后不再需要；pytest 正常退出即真结果）。
- `.gitignore`：移除 `.pytest-tmp/`（不再使用）或保留无害；新增不需。

### 3.3 双 CI 合并为单 workflow
- 删 `ci.yml`（早期），保留并扩展 `ci.yaml` 为唯一 CI：
  ```yaml
  name: CI
  on: [push, pull_request]
  jobs:
    verify:
      strategy:
        matrix:
          os: [ubuntu-latest, windows-latest]
      runs-on: ${{ matrix.os }}
      steps:
        - checkout / setup-python 3.12
        - install (lock sanitized: 剥离 -e git+ / -e d:\)
        - ruff check qi tests
        - pytest -q   # 单一来源，不跑两遍
        - doc-link check
        - verify_package --full
        - spec-trace check
  ```
- doc-link 只跑一次；pytest 只跑一次（verify_package 内部不再重复 pytest 基础跑，或明确 verify_package 的 pytest 即唯一测试来源、ci.yml 的裸 pytest 删去）。

### 3.4 P3 ruff 修复
`check_spec_traceability.py`：
- line 95：`print(f"...")` → `print("...")`（F541，无占位符去 f）
- line 108/110：循环变量 `title` 改为 `_title`（B007 未使用）

### 3.5 防回归测试
- `tests/test_tooling.py`（新建）或并入既有：
  - 构造无占位符 f-string 断言（静态，ruff 已覆盖，单测可省）；
  - `check_spec_traceability.py` 在 GBK 模拟下不崩：可用 `subprocess` 跑脚本并设 `PYTHONIOENCODING`/重定向验证 exit 0（轻量集成测试，可选）。
- CI 自身验证：合并后 workflow 在 ubuntu + windows 双矩阵 green。

## 4. 验收标准

1. `check_spec_traceability.py` 头部 reconfigure，Windows GBK 下不 `UnicodeEncodeError`（CI windows-latest green 为证）。
2. basetemp 改系统临时区（`tempfile.gettempdir()/qi-pytest`），仓库内 `.pytest-tmp` 不再使用；pytest 在 Windows 不再 23 ERROR。
3. 单一 CI workflow，ubuntu + windows 双矩阵 green；doc-link / pytest 各跑一次。
4. ruff 对 `check_spec_traceability.py` 零告警（F541/B007 修复）。
5. 全量 `pytest` 通过，`ruff` 零问题。

## 5. 红线（库内禁止）

- 不删 `verify_package.py` 的红线审计（sys.exit / clamp_emotion 豁免保留）。
- basetemp 不回退到仓库内固定目录（避免 ACL 复发）。
- CI 合并不丢任何既有门禁（ruff / pytest / doc-link / verify_package / spec-trace 全保留）。
- 不引入新依赖。

## 6. 影响面与回退

- 改动：`tools/check_spec_traceability.py`、`tools/verify_package.py`、`pyproject.toml`、`.github/workflows/ci.yml`(删)、`.github/workflows/ci.yaml`(扩)、`tests/conftest.py`(可选)、`tests/test_tooling.py`(新)、`.gitignore`。
- 回退：恢复 pyproject basetemp / 复活 ci.yml 即可，无数据迁移。

## 7. 进度（交 Cursor 编码）

| 步骤 | 状态 |
|------|------|
| PR 方案 | ✅ 已落盘 |
| Cursor 编码请求 | 待发 |
| 编码 + 单测 | 待做 |
| 04 验收 | 待做 |

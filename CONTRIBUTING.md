# 贡献指南（栖 / qi-perch）

本地改完再开 PR。CI 与本地验收入口一致。

## 开工前

- Python **3.12+**；具身前端另需 Node **18+**
- 密钥：复制 `.env.example` → `.env`（勿提交）
- 配置：推荐 `data/settings.yaml`（由 `settings.example.yaml` 复制）

## 必跑验收

```bash
# 全量：pytest（系统临时区 basetemp）+ ruff(qi/tests/tools) + 红线审计
python tools/verify_package.py --full

# 文档死链 / 规格追溯（CI 亦跑）
python tools/check_doc_links.py
python tools/check_spec_traceability.py
```

单包可用：`python tools/verify_package.py --test tests/test_xxx.py`

## 前端（改了 `qi/embodiment/desktop`）

```bash
cd qi/embodiment/desktop
npm ci
npm run build
```

## 文档纪律

- 实现规格以**代码**为准，回写 `docs/reference/layers/` / `config.md`
- 过程文档走 `docs/specs/`；权威链见 `docs/README.md`

## PR

请用仓库 PR 模板自检；勿把 `data/`、`.env`、含密钥的 `settings.yaml` 提交进库。

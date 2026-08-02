# archive/2026-08-02-doc-link-ci · 文档链接 CI 化史料

> 本目录归档 `docs/` 死链自动校验（CI 化）的过程终态。
> 归档不删（对齐 OpenSpec / GitHub Spec Kit）；中间往来稿已精选剔除，仅留定稿 + 终验闭环。

## 包含

- `方案-文档链接CI校验.md` —— 定稿 v2（吸收 Cursor 交叉检验：C1 自写 / archive 排除 / tools+tests 分工）
- `方案-文档链接CI校验-Cursor确认闭环.md` —— Cursor 确认本轮 CI 化正式闭环

## 脉络

1. 方案 v2 → Cursor 交叉检验（拍板 C1 + tools/tests 分工）
2. 落地 `e6a2260`（tools + tests + ci.yml step + 换机搭建死链修复）
3. Cursor 有条件通过（必改 2 + 建议 2）→ 修正 `e4bcc5b`
4. 终验回执 → Cursor 确认闭环

> 现行生效：`tools/check_doc_links.py` + `tests/test_doc_links.py` + `ci.yml` 的 Doc link check step。

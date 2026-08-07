## Summary
<!-- 改了什么、为什么（1–3 条） -->

## Checklist
- [ ] `python tools/verify_package.py --full` 本地通过
- [ ] 若改文档：`python tools/check_doc_links.py` 通过
- [ ] 若改 `qi/embodiment/desktop`：`npm ci && npm run build` 通过
- [ ] 未提交 `data/`、`.env`、含密钥配置
- [ ] 行为变更与纯重构不同 PR（能拆则拆）

## Test plan
<!-- 怎么验证；可贴关键 pytest 文件名 -->

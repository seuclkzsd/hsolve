## 改了什么、为什么

<!-- 一两段话：要解决的问题、做法，以及关联的 Issue（Closes #123）。 -->

## 跑过的检查

检查项与 [CONTRIBUTING.md「提交前检查」](https://github.com/seuclkzsd/hsolve/blob/main/CONTRIBUTING.md#提交前检查)和 CI 相同。

<!-- 勾选实际跑过的，并贴出结尾的摘要（例如 ctest 的 "100% tests passed"）。 -->

- [ ] `tools/dev/build.sh release`：没有编译告警
- [ ] `tools/dev/test.sh release`：全部 ctest 与 pytest 通过
- [ ] `tools/dev/test.sh debug`（改动内存管理、多线程或 MUMPS 调用时）
- [ ] `mkdocs build --strict`（改动文档时）

```text
<粘贴检查输出的摘要>
```

## 新增或修改的测试

<!-- 列出测试文件与用例名。修复缺陷时，说明哪个测试在改动前失败、改动后通过。 -->

## 对正确性的影响

- [ ] 不改变任何数值结果（纯重构、文档、测试、构建）
- [ ] 改变数值结果，但不涉及完备性证书（说明变化的范围与大小）
- [ ] **涉及完备性证书或残差验收**：已按 [GOVERNANCE.md](https://github.com/seuclkzsd/hsolve/blob/main/GOVERNANCE.md) 先开 Issue，并附上改动前失败的测试和独立评测（`tools/eval`）的回归汇总

<!-- 如有性能数字：写明硬件、核数、线程数、内存上限、重复次数与统计量，并附原始数据或生成表格的命令。 -->

## 接口与文档

- [ ] 不改变命令行选项、`config.json` 的键、`report.json` 的字段或 Python API
- [ ] 改变了上述接口，已更新 `docs/FORMATS.md` / `docs/PYTHON.md` 等文档
- [ ] 已在 `CHANGELOG.md` 的「未发布」一节写明用户可见的变化
- [ ] 测试数据是合成的或可以公开；新增依赖已登记到 `docs/DEPENDENCIES.md`、`THIRD_PARTY_NOTICES` 与 `NOTICE`

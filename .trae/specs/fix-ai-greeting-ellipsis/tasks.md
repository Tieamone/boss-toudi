# Tasks

- [x] Task 1: 增大 max_completion_tokens 从 256 到 1024
  - 修改 `boss_auto_apply.py` 中 `call_mimo_api()` 的 payload（约第 893 行）
  - 将 `"max_completion_tokens": 256` 改为 `"max_completion_tokens": 1024`
  - 验证：MiMo reasoning 模型有足够 token 完成思考+输出正文

- [x] Task 2: 优化 _shorten_text() 截断结尾
  - 修改 `boss_auto_apply.py` 中 `_shorten_text()` 函数（约第 795-799 行）
  - 将截断后的 `+ "..."` 改为 `+ "。"`（句号结尾）
  - 验证：截断后的文本以句号结尾，不含省略号

- [x] Task 3: 优化 _build_local_fallback_greeting() 作品证据呈现
  - 修改 `boss_auto_apply.py` 中 `_build_local_fallback_greeting()` 函数（约第 801-816 行）
  - 将 `proof = _shorten_text(proof_points[0] if proof_points else "", 42)` 的 max_len 从 42 提升到 60，让作品证据更完整
  - 验证：兜底招呼语中作品证据更完整，且不含省略号

- [x] Task 4: 增加 AI 空内容诊断日志
  - 修改 `boss_auto_apply.py` 中 AI 返回空内容的日志提示（约第 912-917 行）
  - 当 `finish_reason=length` 时，追加提示"max_completion_tokens 可能过小，reasoning 模型思考 token 占用过多，已自动调大"
  - 验证：日志中能清晰看到 token 不足的诊断信息

- [x] Task 5: 语法检查与验证
  - 运行 `python -c "import ast; ast.parse(open('boss_auto_apply.py', encoding='utf-8').read())"` 验证语法正确
  - 验证：无语法错误

# Task Dependencies
- Task 1, Task 2, Task 3, Task 4 可并行执行
- Task 5 依赖所有前置任务完成

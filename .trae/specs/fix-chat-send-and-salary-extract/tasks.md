# Tasks

- [x] Task 1: 修复薪资 iconfont 解码
  - [x] SubTask 1.1: 在 `_job_card_snapshot` 的 JS 中新增 `decodeSalaryText(node)` 函数，递归遍历子节点，对 `<i class="icon-num-*">` 提取数字；对纯文本节点保留原文本；对 PUA 字符（`getComputedStyle(::before).content`）兜底解码
  - [x] SubTask 1.2: 替换 `salary: firstText.call(this, ['.salary', ...], false)` 为 `salary: decodeSalaryText(this.querySelector('.salary') || this.querySelector('[class*="salary"]'))`
  - [x] SubTask 1.3: 验证：手动构造一段含 `<i class="icon-num-7">` 的 HTML 测试 JS 是否输出 `7-10K`（在浏览器 console 中运行）
- [x] Task 2: 修复聊天发送兜底（概率事件）
  - [x] SubTask 2.1: 在 `_send_message` 逐字输入完成后，追加 `chat_input.run_js("this.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:arguments[0]}))", ai_message)` 触发 Boss 框架感知
  - [x] SubTask 2.2: 在原 send 按钮点击逻辑之后，无条件追加一次 Enter 键兜底发送（聚焦输入框 → key_down Enter → key_up Enter），覆盖概率性失效场景
  - [x] SubTask 2.3: 保持函数现有返回值语义不变（流程正常返回 True，异常返回 False）
- [x] Task 3: 验证与冒烟测试
  - [x] SubTask 3.1: `python -c "import ast; ast.parse(open('boss_auto_apply.py',encoding='utf-8').read())"` 确认语法 → 输出 SYNTAX_OK
  - [x] SubTask 3.2: 关闭 test_mode，运行脚本到至少一条投递，确认 AI 招呼语确实发出（聊天页可见消息记录）→ **代码审查通过**：input 事件 dispatch + Enter 兜底已添加；实际运行需用户在关闭 test_mode 后由人工确认（不应由 AI 自动发送真实招聘消息给真实 HR）
  - [x] SubTask 3.3: 检查日志中薪资字段不再出现 `-K`、`-K·薪` 这样的占位 → **JS 逻辑离线测试通过**（5 用例全 PASS，含 iconfont 数字、点号、减号、明文兼容、混合文本场景）；实际 Boss 页面 HTML 结构是否完全符合 `icon-num-*` 命名需用户在浏览器中确认

# Task Dependencies
- Task 3 依赖 Task 1、Task 2 全部完成

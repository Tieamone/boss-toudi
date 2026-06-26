# Tasks

- [x] Task 1: 新增 AI JD 相关性判断函数 `judge_job_relevance_by_ai`
  - [x] SubTask 1.1: 在 `boss_auto_apply.py` 中（`call_mimo_api` 附近）新增函数 `judge_job_relevance_by_ai(position: str, company: str, job_desc: str, core_stack: str) -> tuple[bool, str, list]`，返回 `(是否相关, 原因, 命中的未掌握工具列表)`
  - [x] SubTask 1.2: 构造判断 prompt：向 AI 提供职位名、公司、JD（截断前 800 字）、候选人掌握工具栈（`RESUME_BASE_FACTS["core_stack"]`）；要求 AI 判断岗位是否与候选人掌握的工具/能力相关，若 JD 核心要求包含候选人不掌握的工具（如 CAD、3D Max、酷家乐、SolidWorks、UG、ProE、Revit、BIM 等）或方向不符（室内/建筑/机械/工业/服装设计），判定为无关
  - [x] SubTask 1.3: 约定 AI 输出格式为：首行 `通过` 或 `跳过`，第二行起为原因（含未掌握工具列表）；用 regex 解析首行判定，其余为原因；用 `<think>` 清理与 code block 清理复用现有逻辑
  - [x] SubTask 1.4: API 调用失败时默认返回 `(True, "AI判断接口失败，默认放行", [])`，记录 warning 日志；调用 `_call_mimo_api` 时 `temperature` 设为较低值（如 0.3）以保证判断稳定性，`max_completion_tokens` 设为较小值（如 512）
  - [x] SubTask 1.5: 验证：`python -c "import ast; ast.parse(open('boss_auto_apply.py',encoding='utf-8').read())"` 语法通过
- [x] Task 2: 在 `AI_CONFIG` 中新增开关字段
  - [x] SubTask 2.1: 在 `AI_CONFIG` 字典中新增 `"jd_relevance_filter_enabled": True`
- [x] Task 3: 在 `_process_job_card` 中插入 AI 相关性筛选环节
  - [x] SubTask 3.1: 在 `_process_job_card` 的本地适配分检查通过后（`min_fit_score` 判断之后）、查找沟通按钮（`apply_btn`）之前，插入 AI 相关性筛选调用
  - [x] SubTask 3.2: 仅当 `AI_CONFIG["enabled"]` 且 `AI_CONFIG.get("jd_relevance_filter_enabled")` 均为 True 时执行；执行时调用 `judge_job_relevance_by_ai(record.position, record.company, job_desc, RESUME_BASE_FACTS["core_stack"])`
  - [x] SubTask 3.3: 若 AI 判定无关（返回 `False`）：记录 `record.status="skipped"`、`record.reason=f"AI判定JD不相关：{原因}"`，`self._save_record(record)`，`detail_tab.close()`，返回 `False`；日志输出 `⏭  跳过 → AI判定JD不相关：{原因}（未掌握工具：{工具列表}）`
  - [x] SubTask 3.4: test_mode 下同样执行筛选；判定无关时终端用 `═`/`─` 分隔符输出判定结果（公司/职位/AI判定/原因/未掌握工具），不打印招呼语
  - [x] SubTask 3.5: 判定相关时日志输出 `✅ AI判定JD相关：{原因}`，继续后续流程
- [x] Task 4: 验证与冒烟测试
  - [x] SubTask 4.1: `python -c "import ast; ast.parse(open('boss_auto_apply.py',encoding='utf-8').read())"` 输出无语法错误
  - [x] SubTask 4.2: 确认 `AI_CONFIG` 加载后 `jd_relevance_filter_enabled` 为 True，启动日志中体现 AI JD 筛选开关状态
  - [x] SubTask 4.3: 代码审查确认：筛选环节位于适配分检查之后、沟通按钮查找之前；API 失败默认放行；test_mode 下判定结果可见

# Task Dependencies
- Task 3 依赖 Task 1、Task 2 完成
- Task 4 依赖 Task 1、Task 2、Task 3 全部完成

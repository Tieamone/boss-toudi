# Tasks

- [x] Task 1: 新增 PROVIDER_CONFIGS 与 ACTIVE_PROVIDER 开关，派生 AI_CONFIG
  - [x] 在 AI 配置区顶部新增 `ACTIVE_PROVIDER = "glm"` 切换开关（带醒目注释）
  - [x] 新增 `PROVIDER_CONFIGS` 字典，含 `mimo`（从 env 读取，保留原逻辑）与 `glm`（内置 key/model/base_url/thinking/token_field）两个条目
  - [x] `AI_CONFIG` 改为从 `PROVIDER_CONFIGS[ACTIVE_PROVIDER]` 派生，合并通用字段（api_timeout、api_retry、trust_env、post_send_delay、typing_char_delay、blog_url、enabled、jd_relevance_filter_enabled）
  - [x] 验证：加载模块后打印 AI_CONFIG 确认 provider/model/base_url 正确（输出 glm/glm-4.7-flash/正确 base_url）

- [x] Task 2: 新增 _build_chat_payload 辅助函数
  - [x] 实现 `_build_chat_payload(messages, max_tokens, temperature, top_p)` 返回 dict
  - [x] GLM 分支：用 `max_tokens` 字段，附 `extra_body={"thinking":{"type":"enabled"}}`
  - [x] MiMo 分支：用 `max_completion_tokens` 字段，无 extra_body
  - [x] 公共字段：model、messages、temperature、top_p、stream=False、frequency_penalty、presence_penalty

- [x] Task 3: 重构三处 payload 构造统一走 _build_chat_payload
  - [x] `call_mimo_api` 的 payload 改用 `_build_chat_payload`
  - [x] `judge_job_relevance_by_ai` 的 payload 改用 `_build_chat_payload`
  - [x] `_test_api_connection` 的 test_payload 改用 `_build_chat_payload`，system prompt 改为 provider 中性（"You are a helpful assistant."）

- [x] Task 4: 启动 banner 与错误提示 provider 感知化
  - [x] 入口 banner 增加 `ACTIVE_PROVIDER` 显示行
  - [x] `_mimo_error_hint` 按 `AI_CONFIG["provider"]` 返回对应 env 变量名提示（GLM→GLM_API_KEY，MiMo→MIMO_API_KEY）
  - [x] 连通性测试日志显示 provider 名称

- [x] Task 5: 真实 API 调用测试验证
  - [x] 直接调用 `_call_mimo_api` 发一条 GLM 请求
  - [x] 确认返回非空 content、思考模式生效（返回"可以"，102 reasoning_tokens）
  - [x] 确认 `call_mimo_api` 能生成有效招呼语（重试后成功生成 183 字 GLM 招呼语）
  - [x] 语法检查：`python -m py_compile boss_auto_apply.py` 通过

# Task Dependencies
- Task 2 依赖 Task 1（需要 AI_CONFIG 中的 provider 信息）
- Task 3 依赖 Task 2（需要 _build_chat_payload）
- Task 4 依赖 Task 1
- Task 5 依赖 Task 1-4 全部完成

# 新增 GLM 模型切换功能 Spec

## Why
当前项目 AI 打招呼/JD 筛选仅支持小米 MiMo 模型，而 MiMo 套餐即将过期。需要接入智谱 GLM-4.7-Flash（200K 上下文、128K 最大输出、开启思考模式）作为替代，并提供一个一目了然的切换开关，让用户在代码中一行切换使用哪个模型。

## What Changes
- 在 AI 配置区新增 `PROVIDER_CONFIGS` 字典，包含 `mimo` 与 `glm` 两个 provider 的完整配置（api_key、model、base_url、token 字段名、thinking 开关）。
- 新增 `ACTIVE_PROVIDER` 常量作为模型切换开关，置于 AI 配置区顶部，注释醒目，改这一行即可切换。
- `AI_CONFIG` 改为从 `PROVIDER_CONFIGS[ACTIVE_PROVIDER]` 派生，保留原有通用字段（timeout、retry、typing_char_delay 等）。
- 新增 `_build_chat_payload()` 辅助函数，按当前 provider 构造请求体：GLM 注入 `extra_body={"thinking":{"type":"enabled"}}` 并使用 `max_tokens`；MiMo 保持原 `max_completion_tokens`。
- 重构 `call_mimo_api`、`judge_job_relevance_by_ai`、`_test_api_connection` 三处 payload 构造，统一走 `_build_chat_payload()`。
- `_test_api_connection` 的 system prompt 改为 provider 中性（去掉 "You are MiMo, developed by Xiaomi" 硬编码）。
- 启动 banner 与 `_mimo_error_hint` 的提示文案改为 provider 感知（显示当前 provider 名称与对应 env 变量名）。

## Impact
- Affected code: `boss_auto_apply.py`（AI 配置区 ~233 行、`_call_mimo_api`/`_get_mimo_client` ~695 行、`call_mimo_api` ~968 行、`judge_job_relevance_by_ai` ~1108 行、`_test_api_connection` ~1531 行、入口 banner ~3795 行）。
- 不改变任何投递流程、简历画像、过滤逻辑，仅替换底层 AI 调用通道。
- 保留 MiMo 配置不删除，切换开关回 `mimo` 即可恢复原行为。

## ADDED Requirements

### Requirement: 模型切换开关
系统 SHALL 在 AI 配置区提供一个 `ACTIVE_PROVIDER` 常量，取值 `"glm"` 或 `"mimo"`，用户修改该单行即可切换底层 AI 模型，无需改动其他代码。

#### Scenario: 切换到 GLM
- **WHEN** `ACTIVE_PROVIDER = "glm"`
- **THEN** AI_CONFIG 使用 GLM 的 api_key/model/base_url，所有 AI 请求走智谱 GLM-4.7-Flash，并自动开启思考模式

#### Scenario: 切换回 MiMo
- **WHEN** `ACTIVE_PROVIDER = "mimo"`
- **THEN** AI_CONFIG 使用原 MiMo 配置（从 env 读取），行为与改动前完全一致

### Requirement: GLM-4.7-Flash 配置
系统 SHALL 内置 GLM provider 配置：
- model: `glm-4.7-flash`
- base_url: `https://open.bigmodel.cn/api/paas/v4`
- api_key: 默认使用用户提供的 key，可被 `GLM_API_KEY` 环境变量覆盖
- 思考模式: `thinking.type = enabled`（通过 OpenAI SDK 的 `extra_body` 传递）
- token 限制字段: `max_tokens`
- 上下文窗口 200K，最大输出 128K

### Requirement: Provider 感知的 payload 构造
系统 SHALL 通过 `_build_chat_payload(messages, max_tokens, temperature, top_p, **extra)` 统一构造请求体：
- GLM: 使用 `max_tokens` 字段，并注入 `extra_body={"thinking":{"type":"enabled"}}`
- MiMo: 使用 `max_completion_tokens` 字段，无 extra_body

## MODIFIED Requirements

### Requirement: 启动连通性测试
`_test_api_connection` SHALL 使用 provider 中性的 system prompt 进行连通性测试，并在日志中显示当前 provider 名称与模型名。连通失败时仍自动关闭 AI 并给出对应 provider 的修复提示。

### Requirement: 启动 banner
入口 banner SHALL 显示当前 `ACTIVE_PROVIDER`、模型名、base_url，让用户一眼确认正在使用哪个模型。

## REMOVED Requirements
无。MiMo 相关配置与函数名保留不变，仅作为可切换的 provider 之一。

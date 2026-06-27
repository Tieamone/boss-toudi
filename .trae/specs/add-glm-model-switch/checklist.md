# Checklist

- [x] AI 配置区存在 `ACTIVE_PROVIDER` 开关，且注释说明「改这一行即可切换模型」
- [x] `PROVIDER_CONFIGS` 同时包含 `mimo` 与 `glm` 两个条目
- [x] GLM 配置：model=`glm-4.7-flash`、base_url=`https://open.bigmodel.cn/api/paas/v4`、思考模式 enabled、token 字段为 `max_tokens`
- [x] GLM api_key 默认为用户提供的 key，且可被 `GLM_API_KEY` 环境变量覆盖
- [x] `AI_CONFIG` 从 `PROVIDER_CONFIGS[ACTIVE_PROVIDER]` 派生，保留原通用字段
- [x] `_build_chat_payload` 对 GLM 注入 `extra_body={"thinking":{"type":"enabled"}}`，对 MiMo 不注入
- [x] `call_mimo_api`、`judge_job_relevance_by_ai`、`_test_api_connection` 均改用 `_build_chat_payload`
- [x] `_test_api_connection` 的 system prompt 不再硬编码 "MiMo developed by Xiaomi"
- [x] 入口 banner 显示 `ACTIVE_PROVIDER` 与模型名
- [x] `_mimo_error_hint` 提示文案按 provider 指向正确的 env 变量名
- [x] `python -m py_compile boss_auto_apply.py` 通过
- [x] 真实调用 GLM-4.7-Flash 成功返回非空中文内容
- [x] MiMo 配置未被删除，`ACTIVE_PROVIDER="mimo"` 时行为与改动前一致

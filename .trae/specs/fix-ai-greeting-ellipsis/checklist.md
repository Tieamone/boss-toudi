# AI 招呼语省略号 Bug 修复 Checklist

## max_completion_tokens 调整
- [x] call_mimo_api() 中 max_completion_tokens 从 256 改为 1024

## 文本截断优化
- [x] _shorten_text() 截断结尾从 "..." 改为 "。"
- [x] _build_local_fallback_greeting() 中 proof 的 max_len 从 42 提升到 60

## 日志诊断
- [x] AI 返回空内容且 finish_reason=length 时，日志提示 max_completion_tokens 可能过小

## 语法验证
- [x] python ast.parse 语法检查通过

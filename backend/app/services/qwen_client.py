"""
Qwen API Client — DashScope 通义千问 API 客户端封装

负责与阿里云 DashScope 通信，支持 Function Calling。
作为 Agent 系统的核心通信层，被上层 Agent 调度器调用。

关键设计：
  - 异步调用（基于 dashscope AioGeneration）
  - tenacity 重试：网络异常重试 2 次，指数退避 1s → 2s
  - API 错误（如参数错误、模型不存在）不重试，直接抛出
  - 超时抛出 TimeoutError
  - 自定义 QwenAPIError 封装 API 业务错误

依赖：dashscope, tenacity
"""

from __future__ import annotations

import json
import logging
import platform
from dataclasses import dataclass, field
from typing import Optional

import dashscope
from dashscope.aigc.generation import AioGeneration
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import settings

logger = logging.getLogger(__name__)


# ── 自定义异常 ────────────────────────────────────────────

class QwenAPIError(Exception):
    """DashScope API 返回业务错误时抛出。

    Attributes:
        status_code: API 返回的 HTTP 状态码。
        code: API 返回的错误码字符串。
        message: 错误描述信息。
        request_id: 请求 ID，用于排查问题。
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        request_id: str = "",
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id
        super().__init__(
            f"Qwen API Error [{status_code}] {code}: {message} "
            f"(request_id={request_id})"
        )


# ── 数据类 ────────────────────────────────────────────────

@dataclass
class ToolCall:
    """Qwen 返回的单个函数调用。"""

    id: str = ""                               # 调用 ID（DashScope 分配）
    name: str = ""                             # 函数名称，如 "get_elo_rating"
    arguments: dict = field(default_factory=dict)  # 函数参数（已解析为 dict）


@dataclass
class DashScopeResponse:
    """DashScope API 调用的标准化返回结果。"""

    content: str = ""                              # Qwen 文本回复
    tool_calls: list[ToolCall] = field(default_factory=list)  # 函数调用列表
    finish_reason: str = ""                        # "stop" 或 "tool_calls"
    usage: dict = field(default_factory=dict)      # {"input_tokens": N, "output_tokens": N, "total_tokens": N}
    request_id: str = ""                           # 请求 ID


# ── Windows 事件循环兼容 ──────────────────────────────────

if platform.system() == "Windows":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# ── 客户端 ────────────────────────────────────────────────

class QwenClient:
    """DashScope Qwen API 客户端。

    Usage:
        client = QwenClient()

        messages = [
            {"role": "system", "content": "你是世界杯预测专家..."},
            {"role": "user", "content": "预测巴西 vs 德国"},
        ]
        tools = tool_registry.get_tools()

        response = await client.chat_with_tools(messages, tools)
        if response.tool_calls:
            for tc in response.tool_calls:
                print(f"调用工具: {tc.name}({tc.arguments})")
        else:
            print(f"回复: {response.content}")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        """初始化客户端。

        Args:
            api_key: DashScope API Key，默认从 settings 读取。
            model: 模型名称，默认从 settings 读取（qwen-max）。
            timeout: 单次请求超时秒数，默认从 settings 读取。
        """
        self._api_key = api_key or settings.qwen_api_key
        self._model = model or settings.qwen_model
        self._timeout = timeout or settings.agent_timeout_seconds

    # ── 核心调用 ─────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=2),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> DashScopeResponse:
        """异步调用 DashScope Qwen API，支持 Function Calling。

        Args:
            messages: 对话消息列表，格式 [{"role": "user", "content": "..."}]。
            tools: 工具定义列表，来自 ToolRegistry.get_tools()。

        Returns:
            DashScopeResponse 包含文本回复、工具调用、token 消耗等。

        Raises:
            QwenAPIError: API 返回业务错误（不重试）。
            TimeoutError: 请求超时（重试后仍失败）。
            ConnectionError: 网络错误（重试后仍失败）。
        """
        if not self._api_key:
            raise QwenAPIError(
                status_code=401,
                code="InvalidApiKey",
                message="QWEN_API_KEY 未配置，请设置环境变量",
            )

        logger.info(
            "调用 Qwen API: model=%s, messages=%d, tools=%d",
            self._model,
            len(messages),
            len(tools),
        )

        try:
            # 调用 DashScope AioGeneration（异步）
            response = await AioGeneration.call(
                api_key=self._api_key,
                model=self._model,
                messages=messages,
                tools=tools if tools else None,
                result_format="message",
                timeout=self._timeout,
            )

        except Exception as exc:
            # 区分可重试和不可重试的异常
            err_name = type(exc).__name__
            if any(keyword in err_name.lower() for keyword in ("timeout", "timedout")):
                logger.error("Qwen API 超时: %s", exc)
                raise TimeoutError(f"Qwen API 请求超时: {exc}") from exc
            if any(keyword in err_name.lower() for keyword in ("connection", "network", "oserror")):
                logger.error("Qwen API 网络错误: %s", exc)
                raise ConnectionError(f"Qwen API 网络错误: {exc}") from exc
            # 其他未知异常也抛出，交由上层处理
            logger.error("Qwen API 未知异常: %s: %s", err_name, exc)
            raise

        return self._parse_response(response)

    # ── 响应解析 ─────────────────────────────────────────

    def _parse_response(self, response) -> DashScopeResponse:
        """解析 DashScope GenerationResponse 为标准化 DashScopeResponse。

        Args:
            response: dashscope GenerationResponse 原始对象。

        Returns:
            标准化的 DashScopeResponse。
        """
        # 检查 HTTP 状态码
        status_code = getattr(response, "status_code", 0)
        request_id = getattr(response, "request_id", "")

        if status_code != 200:
            code = getattr(response, "code", "UnknownError")
            message = getattr(response, "message", "未知错误")
            logger.error(
                "Qwen API 返回错误: status=%d, code=%s, message=%s, request_id=%s",
                status_code, code, message, request_id,
            )
            raise QwenAPIError(
                status_code=status_code,
                code=code,
                message=message,
                request_id=request_id,
            )

        # 解析 output
        output = getattr(response, "output", {})
        choices = output.get("choices", []) if isinstance(output, dict) else []

        content = ""
        tool_calls: list[ToolCall] = []
        finish_reason = ""

        if choices:
            first_choice = choices[0]
            message = first_choice.get("message", {}) if isinstance(first_choice, dict) else {}
            finish_reason = first_choice.get("finish_reason", "")

            # 文本内容
            raw_content = message.get("content", "")
            content = raw_content if isinstance(raw_content, str) else ""

            # 工具调用
            raw_tool_calls = message.get("tool_calls", [])
            if raw_tool_calls:
                for raw_tc in raw_tool_calls:
                    try:
                        func = raw_tc.get("function", {})
                        args_str = func.get("arguments", "{}")
                        # arguments 可能是 JSON 字符串或已解析的 dict
                        if isinstance(args_str, str):
                            arguments = json.loads(args_str) if args_str else {}
                        else:
                            arguments = args_str if isinstance(args_str, dict) else {}

                        tool_calls.append(ToolCall(
                            id=raw_tc.get("id", ""),
                            name=func.get("name", ""),
                            arguments=arguments,
                        ))
                    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
                        logger.warning("解析 tool_call 失败: %s, raw=%s", exc, raw_tc)

        # 解析 usage
        raw_usage = getattr(response, "usage", {})
        usage = {}
        if isinstance(raw_usage, dict):
            usage = {
                "input_tokens": raw_usage.get("input_tokens", 0),
                "output_tokens": raw_usage.get("output_tokens", 0),
                "total_tokens": raw_usage.get("total_tokens", 0),
            }
        elif hasattr(raw_usage, "input_tokens"):
            usage = {
                "input_tokens": getattr(raw_usage, "input_tokens", 0),
                "output_tokens": getattr(raw_usage, "output_tokens", 0),
                "total_tokens": getattr(raw_usage, "total_tokens", 0),
            }

        result = DashScopeResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            request_id=request_id,
        )

        logger.info(
            "Qwen API 响应: finish_reason=%s, tool_calls=%d, tokens=%s, request_id=%s",
            result.finish_reason,
            len(result.tool_calls),
            result.usage,
            result.request_id,
        )

        return result

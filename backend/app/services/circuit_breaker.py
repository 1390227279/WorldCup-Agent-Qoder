"""
Circuit Breaker — 熔断器模块

Agent 系统的第三层容错防线：
当 Qwen API 连续失败达到阈值时自动熔断，后续请求跳过 Agent，
直接走泊松统计兜底模型。熔断超时后进入半开状态尝试恢复。

状态机：
  CLOSED（正常）──连续失败达阈值──→ OPEN（熔断）
  OPEN ──超时到达──→ HALF_OPEN（试探恢复）
  HALF_OPEN ──成功──→ CLOSED
  HALF_OPEN ──失败──→ OPEN

线程安全：使用 threading.Lock 保护状态转换。
"""

import time
import logging
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


# ── 状态枚举 ──────────────────────────────────────────────

class CircuitState(str, Enum):
    """熔断器状态。"""
    CLOSED = "CLOSED"          # 正常，请求通过 Agent
    OPEN = "OPEN"              # 熔断，请求走泊松兜底
    HALF_OPEN = "HALF_OPEN"    # 试探恢复，允许一次请求通过 Agent


# ── 统计数据 ──────────────────────────────────────────────

@dataclass
class CircuitStats:
    """熔断器当前状态快照。"""
    state: str                           # 当前状态字符串
    failure_count: int                   # 连续失败次数
    success_count: int                   # 连续成功次数（HALF_OPEN 后）
    last_failure_time: Optional[float]   # 最近一次失败的时间戳
    opened_at: Optional[float]           # 熔断触发的时间戳
    total_failures: int                  # 累计失败次数
    total_successes: int                 # 累计成功次数


# ── 熔断器 ────────────────────────────────────────────────

class CircuitBreaker:
    """Qwen API 熔断器。

    当 Agent 调用 Qwen API 连续失败时自动熔断，
    保护系统不被级联故障拖垮。

    Usage:
        breaker = CircuitBreaker()

        # 在调用 Qwen 前检查
        if breaker.is_open():
            # 走泊松兜底
            result = poisson_predictor.predict_score(...)
        else:
            try:
                result = await call_qwen_agent(...)
                breaker.record_success()
            except Exception:
                breaker.record_failure()

        # 查看状态
        stats = breaker.get_stats()
    """

    def __init__(
        self,
        failure_threshold: Optional[int] = None,
        recovery_timeout: Optional[int] = None,
    ) -> None:
        """初始化熔断器。

        Args:
            failure_threshold: 连续失败几次触发熔断，默认从 settings 读取。
            recovery_timeout: 熔断多久后尝试恢复（秒），默认从 settings 读取。
        """
        self._failure_threshold = (
            failure_threshold
            if failure_threshold is not None
            else settings.circuit_breaker_failure_threshold
        )
        self._recovery_timeout = (
            recovery_timeout
            if recovery_timeout is not None
            else settings.circuit_breaker_recovery_seconds
        )

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: Optional[float] = None
        self._opened_at: Optional[float] = None
        self._total_failures: int = 0
        self._total_successes: int = 0
        self._lock = threading.Lock()

    # ── 公开方法 ─────────────────────────────────────────

    def record_success(self) -> None:
        """记录一次成功调用。

        - CLOSED 状态：重置失败计数
        - HALF_OPEN 状态：恢复到 CLOSED
        - OPEN 状态：不应到达（is_open 已拦截），但仍安全处理
        """
        with self._lock:
            self._total_successes += 1

            if self._state == CircuitState.HALF_OPEN:
                logger.info("熔断器 HALF_OPEN → CLOSED：Agent 恢复正常")
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 1
                self._opened_at = None

            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0
                self._success_count += 1

    def record_failure(self) -> None:
        """记录一次失败调用。

        - CLOSED 状态：累加失败计数，达到阈值则熔断
        - HALF_OPEN 状态：试探失败，重新熔断
        - OPEN 状态：不应到达，但仍安全处理
        """
        now = time.time()
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = now
            self._total_failures += 1

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    "熔断器 HALF_OPEN → OPEN：试探失败，重新熔断 %d 秒",
                    self._recovery_timeout,
                )
                self._state = CircuitState.OPEN
                self._opened_at = now

            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self._failure_threshold:
                    logger.warning(
                        "熔断器 CLOSED → OPEN：连续失败 %d 次达到阈值，熔断 %d 秒",
                        self._failure_count,
                        self._recovery_timeout,
                    )
                    self._state = CircuitState.OPEN
                    self._opened_at = now

    def is_open(self) -> bool:
        """检查熔断器是否处于开启（熔断）状态。

        自动恢复逻辑：
        - OPEN 状态下，若距上次熔断已超过 recovery_timeout，
          自动进入 HALF_OPEN（允许一次请求通过 Agent 试探）
        - HALF_OPEN 不算 open，返回 False

        Returns:
            True = 熔断中（请求应走泊松兜底）
            False = 正常或试探恢复中（请求可通过 Agent）
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return False

            if self._state == CircuitState.HALF_OPEN:
                return False

            # OPEN 状态：检查是否超时
            if self._state == CircuitState.OPEN and self._opened_at is not None:
                elapsed = time.time() - self._opened_at
                if elapsed >= self._recovery_timeout:
                    logger.info(
                        "熔断器 OPEN → HALF_OPEN：已过 %.1f 秒，尝试恢复",
                        elapsed,
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    return False

            return True

    def get_stats(self) -> dict:
        """返回当前状态的字典快照。

        Returns:
            包含 state, failure_count, success_count,
            last_failure_time, opened_at 等字段的字典。
        """
        with self._lock:
            # 先触发自动恢复检查（不改变返回值语义）
            if self._state == CircuitState.OPEN and self._opened_at is not None:
                elapsed = time.time() - self._opened_at
                if elapsed >= self._recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0

            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
                "opened_at": self._opened_at,
                "total_failures": self._total_failures,
                "total_successes": self._total_successes,
                "failure_threshold": self._failure_threshold,
                "recovery_timeout": self._recovery_timeout,
            }

    def reset(self) -> None:
        """手动重置熔断器到 CLOSED 状态。

        用于管理接口或测试。
        """
        with self._lock:
            logger.info("熔断器手动重置 → CLOSED")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._opened_at = None

    @property
    def state(self) -> CircuitState:
        """当前状态（只读）。"""
        with self._lock:
            return self._state

    @property
    def failure_count(self) -> int:
        """当前连续失败次数（只读）。"""
        with self._lock:
            return self._failure_count

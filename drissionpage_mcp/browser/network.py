"""Network listener operations for a browser tab."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from time import monotonic
from typing import TYPE_CHECKING, Any

from ..network_payload import _network_packet_payload
from ..response_errors import ErrorCode

if TYPE_CHECKING:
    from ..tab import PageTab

logger = logging.getLogger(__name__)


class NetworkUnsupportedError(RuntimeError):
    """Raised when DrissionPage does not expose a usable network listener."""

    code = ErrorCode.UNSUPPORTED_OPERATION


class NetworkOperations:
    """Own DrissionPage listener state and bounded packet serialization."""

    def __init__(self, tab: PageTab) -> None:
        self._tab = tab
        # Listener state is one DrissionPage object per tab.  Keep its
        # start/wait/stop lifecycle serialized even when server-level waits
        # are allowed to overlap unrelated tools.
        self._state_lock = asyncio.Lock()
        self._started_at = ""
        self._filters: dict[str, Any] = {}

    @property
    def _page(self) -> Any:
        return self._tab.page

    async def start(
        self,
        *,
        targets: list[str] | None = None,
        is_regex: bool = False,
        method: str = "",
        resource_type: str = "",
        clear: bool = True,
    ) -> dict[str, Any]:
        async with self._state_lock:
            return await self._start(
                targets=targets,
                is_regex=is_regex,
                method=method,
                resource_type=resource_type,
                clear=clear,
            )

    async def _start(
        self,
        *,
        targets: list[str] | None,
        is_regex: bool,
        method: str,
        resource_type: str,
        clear: bool,
    ) -> dict[str, Any]:
        listener = self._listener()
        if clear and bool(getattr(listener, "listening", False)):
            self._safe_stop(listener)
        elif clear and callable(getattr(listener, "clear", None)):
            listener.clear()

        target_arg: Any = None
        if targets:
            target_arg = targets[0] if len(targets) == 1 else list(targets)

        kwargs: dict[str, Any] = {
            "targets": target_arg,
            "is_regex": is_regex if target_arg is not None else None,
            "method": method or None,
            "res_type": resource_type or None,
        }
        try:
            listener.start(**kwargs)
        except TypeError:
            listener.start(target_arg, is_regex if target_arg is not None else None)

        self._started_at = datetime.now(timezone.utc).isoformat()
        self._filters = {
            "targets": list(targets or []),
            "is_regex": bool(is_regex),
            "method": method,
            "resource_type": resource_type,
        }
        return {
            "listening": bool(getattr(listener, "listening", False)),
            "filters": dict(self._filters),
            "started_at": self._started_at,
            "tab_id": self._tab.mcp_tab_id,
            "cleared": bool(clear),
        }

    async def wait(
        self,
        *,
        timeout: float = 5.0,
        limit: int = 10,
        include_headers: bool = False,
        include_body: bool = False,
        max_body_chars: int = 2000,
    ) -> dict[str, Any]:
        async with self._state_lock:
            return await self._wait(
                timeout=timeout,
                limit=limit,
                include_headers=include_headers,
                include_body=include_body,
                max_body_chars=max_body_chars,
            )

    async def _wait(
        self,
        *,
        timeout: float,
        limit: int,
        include_headers: bool,
        include_body: bool,
        max_body_chars: int,
    ) -> dict[str, Any]:
        listener = self._listener()
        if not bool(getattr(listener, "listening", False)):
            raise NetworkUnsupportedError("Network listener is not listening.")

        deadline = monotonic() + timeout
        first_timeout = timeout if timeout > 0 else _MIN_LISTENER_POLL_SECONDS
        raw_packets = await _await_listener_call(
            listener.wait,
            count=1,
            timeout=first_timeout,
            fit_count=False,
            raise_err=False,
        )
        packets = _packet_list(raw_packets)
        if packets and len(packets) < limit and timeout > 0:
            drain_deadline = min(deadline, monotonic() + _PACKET_DRAIN_SECONDS)
            while len(packets) < limit:
                remaining = drain_deadline - monotonic()
                if remaining <= 0:
                    break
                next_packet = await _await_listener_call(
                    listener.wait,
                    count=1,
                    timeout=remaining,
                    fit_count=False,
                    raise_err=False,
                )
                drained = _packet_list(next_packet)
                if not drained:
                    break
                packets.extend(drained[: limit - len(packets)])
        timed_out = not packets

        normalized = [
            _network_packet_payload(
                packet,
                index=index,
                include_headers=include_headers,
                include_body=include_body,
                max_body_chars=max_body_chars,
            )
            for index, packet in enumerate(packets[:limit])
        ]
        return {
            "listening": bool(getattr(listener, "listening", False)),
            "timed_out": bool(timed_out),
            "count": len(normalized),
            "limit": limit,
            "packets": normalized,
        }

    async def stop(self, *, clear: bool = True) -> dict[str, Any]:
        async with self._state_lock:
            listener = self._listener()
            was_listening = bool(getattr(listener, "listening", False))
            if was_listening:
                self._safe_stop(listener, clear=clear)
            elif clear and callable(getattr(listener, "clear", None)):
                listener.clear()
            return {
                "listening": bool(getattr(listener, "listening", False)),
                "was_listening": was_listening,
                "cleared": bool(clear),
            }

    async def set_blocked_urls(self, urls: list[str]) -> dict[str, Any]:
        """Replace the current tab's blocked URL patterns."""

        self._page.set.blocked_urls(urls)
        return {"count": len(urls), "urls": urls, "set": True}

    def _listener(self) -> Any:
        listener = getattr(self._page, "listen", None)
        if listener is None:
            raise NetworkUnsupportedError(
                "Network listener is unavailable on this browser tab."
            )
        required = ("start", "wait", "stop")
        missing = [
            name for name in required if not callable(getattr(listener, name, None))
        ]
        if missing:
            raise NetworkUnsupportedError(
                "Network listener is unsupported; missing: " + ", ".join(missing)
            )
        return listener

    @staticmethod
    def _safe_stop(listener: Any, *, clear: bool = True) -> None:
        try:
            if clear:
                listener.stop()
            else:
                pause = getattr(listener, "pause", None)
                if callable(pause):
                    pause(clear=False)
                else:
                    listener.stop()
        except AttributeError:
            logger.debug(
                "Network listener stop hit a partial driver state"
            )
        except Exception:
            logger.debug("Network listener stop failed")
            raise


def _packet_list(value: Any) -> list[Any]:
    if value is False or value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


async def _await_listener_call(call: Any, /, **kwargs: Any) -> Any:
    """Keep listener ownership until an uncancellable worker call has finished."""

    worker = asyncio.create_task(asyncio.to_thread(call, **kwargs))
    cancellation: asyncio.CancelledError | None = None
    try:
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError as exc:
                cancellation = exc
        result = worker.result()
    except BaseException:
        if cancellation is not None:
            raise cancellation from None
        raise
    if cancellation is not None:
        raise cancellation
    return result


_MIN_LISTENER_POLL_SECONDS = 0.001
_PACKET_DRAIN_SECONDS = 0.05

"""Helper functions for the LRT Wallbox integration."""

import asyncio
import itertools
import logging
from asyncio import PriorityQueue
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from lrt_wallbox import WallboxError
from lrt_wallbox.msg_types import TransactionStopResponse
from requests.exceptions import ConnectionError, ReadTimeout

from .const import DOMAIN, ATTR_MAX_CURRENT, ATTR_ESP_FW, ATTR_SETUP_STATUS_NETWORK, ATTR_ATMEL_ERROR, \
    ATTR_NETWORK_STATUS_ETHERNET, ATTR_NETWORK_STATUS_WLAN, ATTR_CHARGER_STATUS, ATTR_CHARGING_IS_ON, \
    ATTR_CHARGER_CURRENT_RATE, ATTR_CHARGER_SECONDS_SINCE_START, ATTR_TRANSACTION_CURRENT_ENERGY, \
    ATTR_ATMEL_FW, ATTR_LAST_5_TRANSACTIONS, ATTR_SETUP_STATUS_AMBIENT_LIGHT, ATTR_SETUP_STATUS_MAX_CHARGING_POWER

_LOGGER = logging.getLogger(__name__)


def tag_id_to_hex(tag_id: list[int]) -> str:
    """Convert a list of tag ID bytes to a hexadecimal string."""
    return "".join(f"{b:02X}" for b in tag_id)


class WallboxClientExecutor:
    """Serializes access to WallboxClient using asyncio.Queue."""

    def __init__(
            self, client: Any, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Initialize the WallboxClientExecutor."""
        self._client = client
        self._hass = hass
        self._store = Store(hass, 1, f"{DOMAIN}_last_transaction_data.json")
        self.config_entry = config_entry
        self.data: dict[str, Any] = {}
        self.last_update_success = True
        self._counter = itertools.count()
        self._queue: PriorityQueue[
            tuple[int, int, str, tuple, dict, asyncio.Future]
        ] = PriorityQueue()
        self._task: asyncio.Task | None = None
        self.start()

    def start(self) -> None:
        """Start the background task processing the queue."""
        if self._task is None:
            self._task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        while True:
            priority, seq, method_name, args, kwargs, future = await self._queue.get()

            if future.cancelled():
                continue

            if method_name == "__shutdown__":
                if not future.done():
                    future.set_result(True)
                break

            try:
                method: Callable = getattr(self._client, method_name)
                result = await self._hass.async_add_executor_job(
                    method, *args, **kwargs
                )

            except (ConnectionError, ReadTimeout) as e:
                if method_name == "util_restart":
                    _LOGGER.warning(
                        "Wallbox likely restarted during util_restart (timeout), ignoring."
                    )
                    if not future.done():
                        future.set_result(None)
                else:
                    _LOGGER.warning(
                        "Connection error while calling '%s': %s", method_name, e
                    )
                    if not future.done():
                        future.set_exception(e)
            except Exception as e:
                _LOGGER.exception("Unexpected error in method '%s'", method_name)
                if not future.done() and not future.cancelled():
                    future.set_exception(e)
            else:
                if not future.done() and not future.cancelled():
                    future.set_result(result)

    async def call(
            self, method_name: str, *args, priority: int = 5, timeout: int = 10, **kwargs
    ) -> Any:
        """Call a method on the WallboxClient with priority and timeout."""
        future: asyncio.Future = self._hass.loop.create_future()
        seq = next(self._counter)
        await self._queue.put((priority, seq, method_name, args, kwargs, future))

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as e:
            _LOGGER.warning("Timeout while calling '%s'", method_name)
            if not future.done() and not future.cancelled():
                future.set_exception(e)
            raise
        except asyncio.CancelledError as e:
            _LOGGER.warning("Call to '%s' was cancelled", method_name)
            if not future.done() and not future.cancelled():
                future.set_exception(e)
            raise

    async def shutdown(self) -> None:
        """Shutdown the executor gracefully."""
        if self._task:
            future: asyncio.Future = self._hass.loop.create_future()
            seq = next(self._counter)
            await self._queue.put((0, seq, "__shutdown__", (), {}, future))
            try:
                await asyncio.wait_for(future, timeout=5)
            except TimeoutError:
                _LOGGER.warning("Timeout while shutting down WallboxClientExecutor")
            await self._task
            self._task = None


def get_last_5_transactions(transaction_log: list[TransactionStopResponse]) -> list[dict[str, int | Any]]:
    """Get the last 5 transactions from the transaction log."""

    def _norm_ts(ts):
        """Normalize timestamp to ISO format with UTC timezone."""
        return ts.replace(" UTC", "Z")

    def _sort_key(t: TransactionStopResponse) -> str:
        """Sort key for transactions based on end time."""
        return _norm_ts(t.endTime)

    tx_sorted = sorted(transaction_log, key=_sort_key, reverse=True)
    last5_objs = tx_sorted[:5]

    return [{
        "startTime": _norm_ts(t.startTime),
        "endTime": _norm_ts(t.endTime),
        "energy": int(t.energy),
    } for t in last5_objs]


async def update_status(executor: WallboxClientExecutor) -> dict[str, Any]:
    """Fetch status from the Wallbox and update shared executor state."""
    try:
        load_get = await executor.call("config_load_get", priority=10)
        transaction_status = await executor.call("transaction_get", priority=10)

        is_error = await executor.call("atmel_error_get", priority=10)
        network_status = await executor.call("config_network_status", priority=10)

        transaction_log = await executor.call("transaction_log_get", priority=10)
        last_5 = get_last_5_transactions(transaction_log)

        result = dict(executor.data)
        result.update({
            ATTR_SERIAL_NUMBER: executor.data.get(ATTR_SERIAL_NUMBER),
            ATTR_ESP_FW: executor.data.get(ATTR_ESP_FW),
            ATTR_ATMEL_FW: executor.data.get(ATTR_ATMEL_FW),
            ATTR_SETUP_STATUS_NETWORK: not executor.data.get(ATTR_SETUP_STATUS_NETWORK),
            ATTR_SETUP_STATUS_AMBIENT_LIGHT: not executor.data.get(ATTR_SETUP_STATUS_AMBIENT_LIGHT),
            ATTR_SETUP_STATUS_MAX_CHARGING_POWER: not executor.data.get(ATTR_SETUP_STATUS_MAX_CHARGING_POWER),
            ATTR_MAX_CURRENT: load_get.maxCurrent,
            ATTR_ATMEL_ERROR: bool(is_error.error),
            ATTR_NETWORK_STATUS_ETHERNET: network_status.ethernet == "Connected",
            ATTR_NETWORK_STATUS_WLAN: network_status.wlan == "Connected",
            ATTR_CHARGER_STATUS: transaction_status.ocppCpState,
            ATTR_CHARGING_IS_ON: transaction_status.ocppCpState != "Available",
            ATTR_CHARGER_CURRENT_RATE: transaction_status.currentChargeRate,
            ATTR_CHARGER_SECONDS_SINCE_START: transaction_status.secondsSinceChargeStart,
            ATTR_TRANSACTION_CURRENT_ENERGY: transaction_status.currentTransactionEnergy,
            ATTR_LAST_5_TRANSACTIONS: last_5,
        })

        executor.data = result
        executor.last_update_success = True
        _LOGGER.debug("Finished update_status: %s", result)
        return result  # noqa: TRY300

    except (TimeoutError, ReadTimeout, ConnectionError) as e:
        executor.last_update_success = True  # Keep not disabled on timeout
        _LOGGER.warning("Transient during update_status: %s", e)
        return executor.data

    except WallboxError:
        executor.last_update_success = False
        _LOGGER.warning("WallboxError during update_status, retrying...")
        raise

    except Exception as e:
        executor.last_update_success = False
        _LOGGER.warning("update_status failed: %s", e)
        raise

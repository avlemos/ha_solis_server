"""
TCP listener + DataUpdateCoordinator for Solis/Ginlong packets.
Adapted from the original code by @planetmarshall
and https://github.com/planetmarshall/solis-service/pull/8
and https://github.com/Rapsssito/local-solis-ginglong-inverter
"""

from __future__ import annotations

import asyncio
import binascii
import logging
import re
import datetime
from functools import reduce
from struct import pack
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.solis_client.const import DEFAULT_TCP_PORT

START_BYTE = 0xA5
END_BYTE = 0x15

_LOGGER = logging.getLogger(__name__)


def _checksum_byte(buffer: bytes) -> int:
    return reduce(lambda lrc, x: (lrc + x) & 255, buffer) & 255

class SolisTCPProtocol(asyncio.Protocol):
    """Protocol to handle a single TCP connection and forward received data to coordinator."""

    def __init__(self, coordinator: "SolisDataUpdateCoordinator"):
        self.coordinator = coordinator
        self.transport: Optional[asyncio.Transport] = None
        self._buffer = bytearray()

    def connection_made(self, transport: asyncio.Transport) -> None:
        self.transport = transport
        peer = transport.get_extra_info("peername")
        _LOGGER.debug("TCP connection from %s", peer)

    def data_received(self, data: bytes) -> None:
        # Append incoming bytes and try to decode/parse. Use ignore to avoid exceptions on bad bytes.
        try:
            hexdata = binascii.hexlify(data).decode()
        except Exception:
            _LOGGER.exception("Failed to decode TCP packet")
            return


        _LOGGER.debug("Received TCP text: %s", hexdata)
        # if data[0] != 0x68:
        #     _LOGGER.debug("Not what we were expecting. sending mock")
        #     try:
        #         response = self.coordinator._mock_server_response({}, data)
        #         if self.transport:
        #             self.transport.write(response)
        #     except Exception:
        #         _LOGGER.exception("Failed to build/send mock response")
        # else:    
        parsed = {}

        # try to extract numeric current power from the raw hex payload
        try:
            # hexdata = binascii.hexlify(data).decode()
            # this is the packet size. if you have a different version
            # feel free to extend here
            if len(hexdata) == 206:
                aPo_t1 = float(int(hexdata[118:122], 16))
                dv1 = int(hexdata[66:70], 16) / 10
                dv2 = int(hexdata[70:74], 16) / 10
                a_fo1 = float(int(hexdata[114:118], 16)) / 100
                # use the normalized key your sensor expects
                parsed["current_power_apo_t1_W"] = aPo_t1
                parsed["dv1"] = dv1
                parsed["dv2"] = dv2
                parsed["a_fo1"] = a_fo1

                # serial_start = 30
                # serial_len = 32

                # pos = serial_start + serial_len + 4
                                
            else:
                _LOGGER.debug("Unexpected packet size: %d", len(hexdata))
                return
        except Exception:
            _LOGGER.debug("Failed to parse APo_t1 from hex payload", exc_info=True)

        # update coordinator data so entities receive the new parsed payload
        try:
            _LOGGER.debug("Setting updated data on coordinator: %s", parsed)
            result = self.coordinator.async_set_updated_data(parsed)
            # if the coordinator method returned a coroutine, schedule it
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
        except Exception:
            _LOGGER.exception("Failed to set updated data on coordinator")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if exc:
            _LOGGER.debug("TCP connection lost with error: %s", exc)
        else:
            _LOGGER.debug("TCP connection closed")


class SolisDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator that owns the TCP server and current parsed data."""

    def __init__(self, hass: HomeAssistant, entry, port: int = DEFAULT_TCP_PORT):
        super().__init__(hass, _LOGGER, name="solis_client", update_interval=None)
        self._entry = entry
        # keep backward-compatible default constant name — this is the TCP listen port now
        self.port = port
        self._server: Optional[asyncio.base_events.Server] = None

    async def _async_update_data(self):
        """Return the last known data. No periodic polling; coordinator is push-driven."""
        # DataUpdateCoordinator expects this method when async_request_refresh() is used.
        return self.data if self.data is not None else {}

    async def async_start(self) -> None:
        """Start listening on TCP port."""
        loop = asyncio.get_running_loop()
        try:
            server = await loop.create_server(
                lambda: SolisTCPProtocol(self),
                host="0.0.0.0",
                port=self.port,
            )
            self._server = server
            _LOGGER.info("Listening for Solis TCP connections on port %s", self.port)
        except Exception:
            _LOGGER.exception("Failed to open TCP listener on port %s", self.port)
            raise

    async def async_stop(self) -> None:
        """Stop listening / close server."""
        if self._server:
            self._server.close()
            try:
                await self._server.wait_closed()
            except Exception:
                _LOGGER.exception("Error while waiting for TCP server to close")
            self._server = None
            _LOGGER.info("Stopped Solis TCP listener")
            
    def _mock_server_response(self, header: Optional[dict] = None, request_payload: bytes = b"") -> bytes:
        """Build a mock response for unexpected incoming packets.

        This is defensive: missing header fields are supplied with sensible defaults.
        """
        header = header or {}
        unix_time = int(datetime.datetime.now(tz=datetime.UTC).timestamp())

        first_byte = request_payload[0] if request_payload else 0x00
        payload = pack("<BBIBBBB", first_byte, 0x01, unix_time, 0xAA, 0xAA, 0x00, 0x00)

        msg_type = int(header.get("msg_type", 0x30))
        req_idx = int(header.get("req_idx", 0))
        serialno = int(header.get("serialno", 0))

        resp_type = (msg_type - 0x30) & 0xFF
        header_bytes = pack(
            "<BHBBBBI", START_BYTE, len(payload), 0x10, resp_type, req_idx, req_idx, serialno
        )
        message = header_bytes + payload
        message += pack("BB", _checksum_byte(message[1:]), END_BYTE)
        return message
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
import datetime
from functools import reduce
from struct import pack
from typing import Optional

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.solis.const import DEFAULT_TCP_PORT, STALE_TIMEOUT

START_BYTE = 0xA5
END_BYTE = 0x15

# Instantaneous readings that no longer mean anything once the inverter has
# stopped reporting; they become unknown when the data goes stale.
_STALE_UNKNOWN_KEYS = ("inv_t0", "dv1", "dv2", "av1", "a_fo1", "dc1_current", "dc2_current")
# Power readings drop to zero (the inverter is not producing), which also makes
# the Inverter Status sensor report STANDBY.
_STALE_ZERO_KEYS = ("current_power_apo_t1_W", "dp1_power", "dp2_power")
# Everything else (serial, lifetime energy, lifetime hours, raw status) keeps
# its last value.

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

        try:
            # this is the packet size. if you have a different version
            # feel free to extend here
            if len(hexdata) == 206:
                serial = str(binascii.unhexlify(hexdata[30:62]), "ascii").strip()
                inv_t0 = float(int(hexdata[62:66], 16)) / 10
                dv1 = int(hexdata[66:70], 16) / 10
                dv2 = int(hexdata[70:74], 16) / 10
                
                # DYNAMIC ANCHORS (To prevent data sliding)
                m_pos = hexdata.find("13", 100) # Frequency Marker
                f_pos = hexdata.find("ffff")    # Footer Marker
                
                # a_fo1 = float(int(hexdata[114:118], 16)) / 100
                # aPo_t1 = float(int(hexdata[118:122], 16))
                # et_ge0 = float(int(hexdata[142:150], 16))/10
                # hr_ege_t1 = float((int(hexdata[154:156],16) << 8) | int(hexdata[156:158],16))
                # Without both anchors we can't trust any of the AC/production
                # values. Drop the packet rather than publishing zeros: the
                # energy/hours sensors are total_increasing, so a 0 would be
                # recorded as a meter reset.
                if m_pos == -1 or f_pos < 28:
                    _LOGGER.warning("Packet missing frequency/footer markers, ignoring: %s", hexdata)
                    return

                # EXTRACT AC DATA (Using Frequency Anchor)
                if m_pos % 2 != 0: m_pos -= 1
                # AC Voltage (12 chars before 13xx)
                av1 = int(hexdata[m_pos-12:m_pos-8], 16) / 10
                # Frequency
                a_fo1 = float(int(hexdata[m_pos:m_pos+4], 16)) / 100
                # Current Power
                aPo_t1 = float(int(hexdata[m_pos+4:m_pos+8], 16))

                # EXTRACT PRODUCTION DATA (Using Footer Anchor)
                # Total Energy (28 chars before ffff)
                et_ge0 = float(int(hexdata[f_pos-28:f_pos-20], 16)) / 10
                # Total Hours (20 chars before ffff)
                hr_ege_t1 = float(int(hexdata[f_pos-20:f_pos-12], 16))
                # Inverter Status (12 chars before ffff)
                inv_st1 = int(hexdata[f_pos-12:f_pos-8], 16)

                # CALCULATE ESTIMATED DC VALUES (For HA Dashboards)
                # Assumes ~97% efficiency to guess DC side metrics
                total_dc_power = aPo_t1 / 0.97
                v_total = dv1 + dv2
                if v_total > 0:
                    dp1 = round((dv1 / v_total) * total_dc_power, 2)
                    dp2 = round((dv2 / v_total) * total_dc_power, 2)
                    dc1 = round(dp1 / dv1, 2) if dv1 > 0 else 0.0
                    dc2 = round(dp2 / dv2, 2) if dv2 > 0 else 0.0
                else:
                    dp1 = dp2 = dc1 = dc2 = 0.0

                
                parsed["serialno"] = serial
                parsed["inv_t0"] = inv_t0
                parsed["dv1"] = dv1
                parsed["dv2"] = dv2
                parsed["av1"] = av1
                parsed["a_fo1"] = a_fo1
                parsed["current_power_apo_t1_W"] = aPo_t1
                parsed["et_ge0"] = et_ge0
                parsed["hr_ege_t1"] = hr_ege_t1
                parsed["inverter_status"] = inv_st1
                parsed["dc1_current"] = dc1
                parsed["dc2_current"] = dc2
                parsed["dp1_power"] = dp1
                parsed["dp2_power"] = dp2

                # serial_start = 30
                # serial_len = 32

                # pos = serial_start + serial_len + 4
                                
            else:
                _LOGGER.debug("Unexpected packet size: %d", len(hexdata))
                return
        except Exception:
            # Don't fall through: publishing a partial/empty dict would wipe
            # the last good readings.
            _LOGGER.warning("Failed to parse hex payload, ignoring packet: %s", hexdata, exc_info=True)
            return

        # update coordinator data so entities receive the new parsed payload
        try:
            _LOGGER.debug("Setting updated data on coordinator: %s", parsed)
            self.coordinator.async_handle_packet(parsed)
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
        self._stale_unsub: Optional[CALLBACK_TYPE] = None

    async def _async_update_data(self):
        """Return the last known data. No periodic polling; coordinator is push-driven."""
        # DataUpdateCoordinator expects this method when async_request_refresh() is used.
        return self.data if self.data is not None else {}

    @callback
    def async_handle_packet(self, parsed: dict) -> None:
        """Publish freshly parsed data and restart the staleness watchdog."""
        self.async_set_updated_data(parsed)
        self._cancel_stale_timer()
        self._stale_unsub = async_call_later(self.hass, STALE_TIMEOUT, self._async_mark_stale)

    @callback
    def _async_mark_stale(self, _now) -> None:
        """No packet for STALE_TIMEOUT: the inverter is asleep, stop showing old readings."""
        self._stale_unsub = None
        if not self.data:
            return
        _LOGGER.info("No packet from the inverter for %s s, marking readings as stale", STALE_TIMEOUT)
        stale = dict(self.data)
        for key in _STALE_UNKNOWN_KEYS:
            stale[key] = None
        for key in _STALE_ZERO_KEYS:
            stale[key] = 0.0
        self.async_set_updated_data(stale)

    def _cancel_stale_timer(self) -> None:
        if self._stale_unsub:
            self._stale_unsub()
            self._stale_unsub = None

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
        self._cancel_stale_timer()
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
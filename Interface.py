"""
Interface.py 3DS memory read/write over UDP.

This speaks the exact protocol of the CTRPluginFramework memory-pipe plugin used
by A Link Between Worlds (LittleCube's albw-ap-plugin). That plugin is entirely
game-agnostic: it binds UDP :45987 and services Ping / Read / Write / ProcessList
/ SetGetProcess requests against the running title's memory. The same plugin,
rebuilt with Robobot's title id (00040000001BB800), drives this integration so
no game code is modified at runtime; all logic lives in the client below.

Packet layout (little-endian):
    header  = u32 version, u32 request_id, u32 request_type, u32 data_len
    Read    data = u32 address, u32 size        -> reply data = the bytes
    Write   data = u32 address, u32 size, bytes  -> reply header only
    ProcessList data = u32 start, u32 max        -> reply = u32 count, then
                                                    [u32 proc_id, u64 title_id]*
    SetGetProcess data = u32 op(1=set), u32 proc_id
"""
import asyncio
import enum
import socket
import struct
from typing import Optional


class ConnectionLost(Exception):
    pass


class RequestType(enum.IntEnum):
    Ping = 0
    Read = 1
    Write = 2
    ProcessList = 3
    SetGetProcess = 4


class N3DSInterface:
    PACKET_VERSION = 1
    HEADER_SIZE = 0x10
    MAX_PACKET_SIZE = 0x410
    TIMEOUT = 1.0
    PORT = 45987

    def __init__(self):
        self.id = 0
        self.max_request_size = 32
        self.sock: Optional[socket.socket] = None

    def _max_read_size(self) -> int:
        return self.max_request_size

    def _max_write_size(self) -> int:
        return self.max_request_size - 8

    async def _send_packet(self, request_type: RequestType, request_data: bytes,
                           retry: bool = True) -> bytes:
        loop = asyncio.get_running_loop()
        tries = 4 if retry else 1
        for _ in range(tries):
            try:
                request_id = self.id
                self.id = (self.id + 1) & 0xffffffff
                request = struct.pack("=IIII", self.PACKET_VERSION, request_id,
                                      request_type, len(request_data)) + request_data
                await asyncio.wait_for(loop.sock_sendall(self.sock, request), self.TIMEOUT)
                for _ in range(16):
                    response = await asyncio.wait_for(
                        loop.sock_recv(self.sock, self.MAX_PACKET_SIZE), self.TIMEOUT)
                    if not response or len(response) < self.HEADER_SIZE:
                        break
                    version, rid, rtype, size = struct.unpack("=IIII", response[:self.HEADER_SIZE])
                    if version == self.PACKET_VERSION and rid == request_id and rtype == request_type:
                        return response[self.HEADER_SIZE:]
            except Exception:
                continue
        raise ConnectionLost("Lost connection to game")

    async def _set_process(self, title: int) -> bool:
        start_process = 0
        while True:
            request_data = struct.pack("=II", start_process, 0x7fffffff)
            try:
                response = await self._send_packet(RequestType.ProcessList, request_data, retry=False)
                if len(response) < 4:
                    self.max_request_size = 32
                    return True
                count = struct.unpack("=I", response[0:4])[0]
                if count == 0:
                    return False
                start_process += count
                for i in range(count):
                    proc_id, title_id = struct.unpack(
                        "=IQ", response[i * 0x14 + 4: i * 0x14 + 0x10])
                    if title_id == title:
                        await self._send_packet(
                            RequestType.SetGetProcess, struct.pack("=II", 1, proc_id), retry=False)
                        self.max_request_size = 1024
                        return True
            except ConnectionLost:
                # Older plugin without process list: assume the game is the target.
                self.max_request_size = 32
                return True

    async def connect(self, address: str, title: int) -> bool:
        self.disconnect()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.connect((address, self.PORT))
        self.sock.setblocking(False)
        try:
            await self._send_packet(RequestType.Ping, b"", retry=False)
            return await self._set_process(title)
        except ConnectionLost:
            return False

    def disconnect(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    async def read(self, address: int, size: int) -> bytes:
        out = b""
        start = 0
        while start < size:
            chunk = min(size - start, self._max_read_size())
            data = await self._send_packet(
                RequestType.Read, struct.pack("=II", address + start, chunk))
            out += data[:chunk]
            start += chunk
        return out

    async def write(self, address: int, data: bytes) -> None:
        start = 0
        while start < len(data):
            end = min(len(data), start + self._max_write_size())
            payload = struct.pack("=II", address + start, end - start) + data[start:end]
            await self._send_packet(RequestType.Write, payload)
            start = end

    async def read_u8(self, address: int) -> int:
        return (await self.read(address, 1))[0]

    async def read_u16(self, address: int) -> int:
        return struct.unpack("<H", await self.read(address, 2))[0]

    async def read_u32(self, address: int) -> int:
        return struct.unpack("<I", await self.read(address, 4))[0]

    async def write_u8(self, address: int, value: int) -> None:
        await self.write(address, struct.pack("<B", value & 0xFF))

    async def write_u32(self, address: int, value: int) -> None:
        await self.write(address, struct.pack("<I", value & 0xFFFFFFFF))

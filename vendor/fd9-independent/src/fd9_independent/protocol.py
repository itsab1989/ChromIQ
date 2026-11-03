# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded framing and typed raw messages from documented wire observations."""
from dataclasses import dataclass
import math
import struct


class ProtocolError(ValueError):
    pass


def encode_request(payload):
    if not 4 <= len(payload) <= 65535:
        raise ProtocolError('Request payload must contain a command and fit uint16')
    return struct.pack('<BBH', 0, 0, len(payload)) + payload


class MessageDecoder:
    """Incremental, bounded chunk decoder; accepts arbitrary TCP fragmentation."""
    def __init__(self, maximum_message=1024*1024):
        self.maximum_message = maximum_message
        self.buffer = bytearray()
        self.message = bytearray()
        self.failed = False

    def feed(self, data):
        if self.failed:
            raise ProtocolError('Decoder is unusable after a framing error')
        output=[]
        try:
            # Process bounded slices so an unexpectedly large read cannot grow
            # an unvalidated staging buffer without limit.
            for offset in range(0, len(data), 8192):
                self.buffer.extend(data[offset:offset+8192])
                while len(self.buffer)>=4:
                    side, continuation, length=struct.unpack_from('<BBH', self.buffer)
                    if side!=1 or continuation not in (0,1) or not 1<=length<=8192:
                        raise ProtocolError('Invalid device chunk header')
                    if len(self.message)+length>self.maximum_message:
                        raise ProtocolError('Message exceeds the configured bound')
                    if len(self.buffer)<4+length:
                        break
                    self.message.extend(self.buffer[4:4+length]);del self.buffer[:4+length]
                    if not continuation:
                        if len(self.message)<4:
                            raise ProtocolError('Message lacks a command identifier')
                        output.append(bytes(self.message));self.message.clear()
            return output
        except ProtocolError:
            self.failed=True;self.buffer.clear();self.message.clear();raise

    def finish(self):
        if self.buffer or self.message:
            self.failed=True
            raise ProtocolError('Connection ended inside a message')


@dataclass(frozen=True)
class SheetStatus:
    level: int
    job: int
    connection: int
    stop: int
    mechanism: int
    paper: int
    fatal: int
    warning: int

    @classmethod
    def decode(cls, payload):
        if len(payload)!=36 or struct.unpack_from('<I',payload)[0]!=0x300:
            raise ProtocolError('Malformed sheet-status message')
        return cls(*struct.unpack_from('<8I',payload,4))


@dataclass(frozen=True)
class ImageRow:
    index: int
    pixels: bytes

    @classmethod
    def decode(cls,payload):
        if len(payload)!=3648 or struct.unpack_from('<II',payload)!=(0x304,3640):
            raise ProtocolError('Malformed image-row message')
        return cls(struct.unpack_from('<h',payload,8)[0],payload[10:])


@dataclass(frozen=True)
class RawSpectrum:
    header: tuple
    blocks: tuple

    @classmethod
    def decode(cls,payload):
        if len(payload)!=620 or struct.unpack_from('<I',payload)[0]!=0x305:
            raise ProtocolError('Malformed raw spectral message')
        blocks=tuple(struct.unpack_from('<38f',payload,12+152*i) for i in range(4))
        if not all(math.isfinite(v) for block in blocks for v in block):
            raise ProtocolError('Non-finite raw instrument values')
        return cls(struct.unpack_from('<4H',payload,4),blocks)

    def reflectance(self):
        raise NotImplementedError('Independent calibration/conversion is not validated; raw blocks are not M0 reflectance')

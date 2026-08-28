"""CR30 reference implementation.

Layer A per CLAUDE.md: knows about the device, knows nothing about ChromIQ.

Import layering, which the tests enforce:

    frame, identity          -- pure decoding. No OS, no I/O, no pyserial.
    transport                -- Transport ABC + SerialTransport + ReplayTransport
    session                  -- commands, on top of any Transport
    discovery                -- the ONLY OS-aware module; optional import

`import cr30` never imports pyserial: `SerialTransport` and `discovery` import
it lazily, so the whole decoder and every replay test run on a machine that has
never seen a CR30.
"""
from .frame import (CHECKSUM, FRAME_SIZE, MARKER, ChecksumError, Frame, FrameError,
                    ShortFrameError, START_COMMAND, START_IDENTITY, checksum)
from .identity import Identity, parse_identity
from .session import (CheckStatus, EchoedCommandError, Session, device_written_bytes,
                      is_echo)
from .transport import (DEFAULT_TIMEOUT_S, Exchange, NOMINAL_BAUD, ReplayTransport,
                        SerialTransport, Transport, TransportError, TransportTimeout)

__all__ = [
    "Frame", "FrameError", "ChecksumError", "ShortFrameError", "checksum",
    "FRAME_SIZE", "MARKER", "CHECKSUM", "START_IDENTITY", "START_COMMAND",
    "Identity", "parse_identity",
    "Transport", "SerialTransport", "ReplayTransport", "Exchange",
    "TransportError", "TransportTimeout", "NOMINAL_BAUD", "DEFAULT_TIMEOUT_S",
    "Session", "CheckStatus", "EchoedCommandError", "is_echo",
    "device_written_bytes",
]

try:                       # optional: needs pyserial / bleak at runtime
    from .device import CR30
    from .measurement import Measurement, MeasurementError
    __all__ = list(__all__) + ["CR30", "Measurement", "MeasurementError"]
except ImportError:        # driver deps absent -> the rest of ChromIQ still imports
    CR30 = None

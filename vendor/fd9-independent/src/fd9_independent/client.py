# SPDX-License-Identifier: GPL-3.0-or-later
"""Single-owner read-only session; no job, display, priority or motion commands."""
import hashlib
import json
from pathlib import Path
import socket
import struct
import threading
import time
from .protocol import MessageDecoder, ProtocolError, encode_request


class OperationCancelled(RuntimeError):
    """Operator cancelled; connection closes without additional motion commands."""


class Instrument:
    def __init__(self, host, port=49152, timeout=5, socket_factory=socket.create_connection, cancelled=None):
        if timeout<=0:raise ValueError('Timeout must be positive')
        self.host,self.port,self.timeout=host,port,timeout
        self.socket_factory=socket_factory;self.socket=None;self.registered=False
        self.cancelled=cancelled
        self.decoder=MessageDecoder();self.pending=[];self.events=[]
        self.sent=bytearray();self.received=bytearray();self.lock=threading.Lock()
        self._row_callback_rpc_blocked=False

    def _check_cancel(self):
        if self.cancelled is not None and self.cancelled():
            raise OperationCancelled('Operator stopped the FD9 session; no further commands sent')

    def _recv(self,deadline):
        while True:
            self._check_cancel()
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('Instrument receive deadline expired')
            self.socket.settimeout(min(.25,remaining) if self.cancelled is not None else remaining)
            try:return self.socket.recv(8192)
            except socket.timeout:
                if self.cancelled is None:raise

    def connect(self, name='Independent FD9'):
        raw=name.encode('ascii')
        if not 1<=len(raw)<=20 or b'\0' in raw:raise ValueError('Registration name must be 1..20 ASCII bytes without NUL')
        if self.socket is not None:raise RuntimeError('Already connected')
        self.decoder=MessageDecoder();self.pending=[];self.events=[]
        self.socket=self.socket_factory((self.host,self.port),self.timeout)
        try:
            reply=self._exchange(struct.pack('<I',3)+raw.ljust(20,b'\0'),3)
            if len(reply)!=8 or struct.unpack_from('<I',reply,4)[0]!=0:
                raise ProtocolError('Normal registration was declined or malformed')
            self.registered=True;return self
        except Exception:self.close();raise

    def _exchange(self,payload,expected):
        if self._row_callback_rpc_blocked:
            raise RuntimeError('Nonfinal row callbacks must not issue instrument commands; continue the row sequence')
        if self.socket is None:raise RuntimeError('Instrument is disconnected')
        if not self.lock.acquire(blocking=False):raise RuntimeError('A request is already in progress')
        try:
            self._check_cancel()
            deadline=time.monotonic()+self.timeout
            self.socket.settimeout(self.timeout)
            frame=b''.join(encode_request(p) for p in payload) if isinstance(payload,(tuple,list)) else encode_request(payload)
            self.socket.sendall(frame);self.sent.extend(frame)
            while True:
                while self.pending:
                    response=self.pending.pop(0)
                    if struct.unpack_from('<I',response)[0]==expected:return response
                    if len(self.events)>=512 or sum(map(len,self.events))+len(response)>1024*1024:
                        raise ProtocolError('Unconsumed notification queue exceeded its bound')
                    self.events.append(response)
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('Instrument response deadline expired')
                data=self._recv(deadline)
                if not data:
                    self.decoder.finish();raise ConnectionError('Instrument closed the connection')
                self.received.extend(data);self.pending.extend(self.decoder.feed(data))
        except Exception:self.close();raise
        finally:self.lock.release()

    def receive_event(self,timeout=None):
        """Drain asynchronous notifications without issuing another command."""
        if not self.registered:raise RuntimeError('Register before receiving notifications')
        duration=self.timeout if timeout is None else timeout
        if duration<=0:raise ValueError('Event timeout must be positive')
        if not self.lock.acquire(blocking=False):raise RuntimeError('A request is already in progress')
        try:
            self._check_cancel()
            if self.events:return self.events.pop(0)
            deadline=time.monotonic()+duration
            while not self.pending:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('Notification deadline expired')
                data=self._recv(deadline)
                if not data:self.decoder.finish();raise ConnectionError('Instrument closed the connection')
                self.received.extend(data);self.pending.extend(self.decoder.feed(data))
            message=self.pending.pop(0)
            if struct.unpack_from('<I',message)[0]<0x300:raise ProtocolError('Unexpected command reply without an outstanding request')
            return message
        except (socket.timeout,TimeoutError):
            # A quiet interval is not a framing error. Retain any partial bytes.
            raise TimeoutError('No notification arrived before the deadline')
        except Exception:self.close();raise
        finally:self.lock.release()

    def status(self):
        if not self.registered:raise RuntimeError('Register before requesting status')
        reply=self._exchange(struct.pack('<I',0),0)
        if len(reply)!=40 or struct.unpack_from('<I',reply,4)[0]!=0:
            self.close();raise ProtocolError('Status response failed or has an unexpected size')
        return {'raw_words':list(struct.unpack_from('<8I',reply,8))}

    def calibration_blob(self):
        """Preserve instrument-supplied bytes; no guessed calibration interpretation."""
        if not self.registered:raise RuntimeError('Register before requesting calibration')
        reply=self._exchange(struct.pack('<II',1,0),1)
        if len(reply)!=7348 or struct.unpack_from('<I',reply,4)[0]!=0:
            self.close();raise ProtocolError('Calibration-data response failed or has an unexpected size')
        return reply[8:]

    def sensor_factory_data(self, kind=7):
        """Read the spectral sensor's own record without writing calibration."""
        from .factory import SensorFactoryRecord, sensor_factory_request, SENSOR_FACTORY_COMMAND
        if not self.registered:raise RuntimeError('Register before reading sensor factory data')
        request=sensor_factory_request(kind)
        try:
            return SensorFactoryRecord.from_reply(
                self._exchange(request, SENSOR_FACTORY_COMMAND), kind)
        except Exception:
            self.close()
            raise

    def sensor_status(self):
        """Read sensor state/counts without exposure, motion or factory writes."""
        from .sensor_status import SensorStatus, sensor_status_request, COMMAND
        if not self.registered:raise RuntimeError('Register before requesting sensor status')
        try:
            return SensorStatus.from_reply(self._exchange(sensor_status_request(), COMMAND))
        except ProtocolError:
            self.close()
            raise

    def cached_sensor_data(self, selector=0, controls=(1,0,0,0)):
        """Read numeric cached data; use NativeReader for checked condition reads."""
        from .sensor_data import CachedSensorData, cached_data_request, COMMAND
        if not self.registered:raise RuntimeError('Register before reading cached sensor data')
        request=cached_data_request(selector,controls)
        try:
            reply=self._exchange(request,COMMAND)
            return CachedSensorData.from_reply(reply,selector,controls)
        except ProtocolError:
            self.close()
            raise

    def factory_characterization(self):
        """Read and check the sensor's records; never change factory data."""
        from .factory import FactoryCharacterization, RECORD_SIZES
        try:
            return FactoryCharacterization(tuple(self.sensor_factory_data(k) for k in RECORD_SIZES))
        except Exception:
            self.close()
            raise

    def close(self):
        connection,self.socket=self.socket,None;self.registered=False
        if connection is not None:connection.close()

    def save_transcript(self, directory):
        path=Path(directory);path.mkdir(parents=True,exist_ok=False)
        for name,data in [('sent.bin',self.sent),('received.bin',self.received)]:
            (path/name).write_bytes(data)
        (path/'manifest.json').write_text(json.dumps({'host':self.host,'port':self.port,'sent_sha256':hashlib.sha256(self.sent).hexdigest(),'received_sha256':hashlib.sha256(self.received).hexdigest(),'host_spectral_conversion':'none; see caller metadata for native or external-profile results'},indent=2)+'\n')

    def __enter__(self):return self.connect()
    def __exit__(self,*args):self.close()

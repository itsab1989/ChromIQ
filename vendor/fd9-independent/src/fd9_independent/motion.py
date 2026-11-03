# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental explicit-geometry raw acquisition; opt-in and offline tested.

No numerical spectral conversion is performed. No automatic retry or forced
device registration is implemented. Supervised twelve-patch and automatic 300-patch runs have completed on one
device; cancellation and repeatability hardware validation remain pending. The existing
experimental backend remains separate.
"""
from enum import Enum
from functools import wraps
import math
import struct
import time
from .client import Instrument
from .display import chunks
from .protocol import ProtocolError,SheetStatus,ImageRow,RawSpectrum


class Phase(Enum):
    NEW='new'
    WAITING='waiting'
    READY='ready'
    SCANNED='scanned'
    MEASURING='measuring'
    DONE='done'
    FAILED='failed'


class DeviceStopped(RuntimeError):pass


def failed_on_error(operation):
    @wraps(operation)
    def guarded(self,*args,**kwargs):
        try:return operation(self,*args,**kwargs)
        except Exception:
            self.phase=Phase.FAILED;self.instrument.close();raise
    return guarded


def line_command(points,calibrate,more):
    if not 1<=len(points)<=64:raise ValueError('Line envelope is 1..64 points')
    packed=[]
    for x,y in points:
        if not all(math.isfinite(v) for v in (x,y)) or not 12<x<3625 or not 12<y<19000:
            raise ValueError('Measurement point exceeds explicit geometry envelope')
        packed.append(struct.pack('<4f',x,y,0,0))
    if any(points[i][0]>=points[i+1][0] for i in range(len(points)-1)):raise ValueError('Points must be ordered by sensor X')
    return struct.pack('<9I',0x106,1,130,150,int(calibrate),0,65,int(more),len(points))+b''.join(packed)


class RawAcquisition:
    def __init__(self,instrument,*,enable_experimental_motion=False):
        if not enable_experimental_motion:raise ValueError('Experimental motion requires explicit opt-in')
        if not isinstance(instrument,Instrument):raise TypeError('Use an independent Instrument session')
        self.instrument=instrument;self.phase=Phase.NEW;self.last_status=None;self.image={};self.raw_samples=[];self.calibration=b''

    def _reply(self,payload,command,size):
        reply=self.instrument._exchange(payload,command)
        if len(reply)!=size or struct.unpack_from('<I',reply,4)[0]!=0:
            self.phase=Phase.FAILED;raise ProtocolError(f'Command {command:#x} failed or has an unexpected reply size')
        # Examine status events received ahead of the acknowledgement.
        for event in self.instrument.events:
            if struct.unpack_from('<I',event)[0]==0x300:self._check_state(event)
        return reply

    def _check_state(self,message):
        state=SheetStatus.decode(message);self.last_status=state
        if state.stop or state.fatal:
            self.phase=Phase.FAILED;raise DeviceStopped('FD-9 reported stop/fatal; no automatic retry')
        return state

    def _event(self,timeout):
        message=self.instrument.receive_event(timeout)
        if struct.unpack_from('<I',message)[0]==0x300:self._check_state(message)
        return message

    def _wait_state(self,target,seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if self.last_status and self.last_status.mechanism==target and self.last_status.paper==1:return
            try:self._event(min(2,deadline-time.monotonic()))
            except TimeoutError:self.instrument.status()
        self.phase=Phase.FAILED;raise TimeoutError('Sheet did not reach the expected mechanical state')

    @failed_on_error
    def prepare(self,name='FD9 RAW CHART',wait_seconds=180):
        if not 1<=wait_seconds<=86400:raise ValueError('Insertion wait must be 1..86400 seconds')
        self.begin_loading(name)
        self.wait_ready(wait_seconds)

    @failed_on_error
    def begin_loading(self,name='FD9 RAW CHART'):
        if self.phase!=Phase.NEW:raise RuntimeError('Prepare only once per acquisition')
        encoded=name.encode('ascii')
        if not 1<=len(encoded)<=16 or b'\0' in encoded:raise ValueError('Chart name must fit sixteen ASCII bytes')
        self.instrument.status();self.calibration=self.instrument.calibration_blob()
        self._reply(struct.pack('<II16sI',4,0,encoded,1),4,12)
        self._reply(chunks(1),5,8);self.phase=Phase.WAITING

    @failed_on_error
    def wait_ready(self,wait_seconds=180):
        if self.phase!=Phase.WAITING:raise RuntimeError('Begin loading before waiting for a sheet')
        if not 1<=wait_seconds<=86400:raise ValueError('Insertion wait must be 1..86400 seconds')
        self._wait_state(4,wait_seconds)
        self._reply(chunks(3),5,8);self._wait_state(5,30)
        self.phase=Phase.READY

    @failed_on_error
    def prescan(self,seconds=120):
        if self.phase!=Phase.READY:raise RuntimeError('A ready sheet is required')
        if not 1<=seconds<=600:raise ValueError('Pre-scan deadline must be 1..600 seconds')
        self._reply(struct.pack('<II',0x203,5),0x203,10)
        position=self._reply(struct.pack('<II',0x104,0),0x104,28)
        if not 1<=struct.unpack_from('<i',position,24)[0]<19000:raise ProtocolError('Unexpected loaded-sheet position')
        self.instrument.calibration_blob()
        self._reply(struct.pack('<5I',0x105,1,120,0,0),0x105,8)
        deadline=time.monotonic()+seconds;trailing=False
        while time.monotonic()<deadline:
            try:message=self._event(min(1,deadline-time.monotonic()))
            except TimeoutError:
                if trailing:break
                continue
            if struct.unpack_from('<I',message)[0]==0x304:
                row=ImageRow.decode(message)
                if row.index<0:trailing=True
                else:
                    if row.index>=19000:raise ProtocolError('Image exceeds maximum sheet length')
                    if row.index in self.image and self.image[row.index]!=row.pixels:raise ProtocolError('Conflicting image row')
                    self.image[row.index]=row.pixels
        else:raise TimeoutError('Pre-scan did not finish')
        if not trailing or not self.image or set(self.image)!=set(range(max(self.image)+1)):
            self.phase=Phase.FAILED;raise ProtocolError('Incomplete image; no spectral measurement sent')
        if self.instrument.decoder.buffer or self.instrument.decoder.message:
            raise ProtocolError('Quiet interval occurred inside an incomplete frame')
        self._reply(struct.pack('<II',0x104,0),0x104,28);self.instrument.status()
        self.phase=Phase.SCANNED
        return b''.join(self.image[i] for i in range(len(self.image)))

    @failed_on_error
    def measure(self,rows,seconds_per_row=150,on_row=None,on_point=None):
        """Acquire rows; nonfinal callbacks may record progress but not issue RPCs.

        The controller expects the next line during a continued acquisition.
        Sensor diagnostics must wait until after the final row, outside that
        continuation sequence. Long callbacks may still exceed its deadline.
        """
        if self.phase!=Phase.SCANNED:raise RuntimeError('Retained pre-scan required')
        if not 1<=seconds_per_row<=300:raise ValueError('Row deadline must be 1..300 seconds')
        if not 1<=len(rows)<=128:raise ValueError('Explicit geometry supports 1..128 rows')
        commands=[line_command(p,i%6==0,i<len(rows)-1) for i,p in enumerate(rows)]
        if not self.image or any(not 12<p[1]<len(self.image)-13 for row in rows for p in row):
            raise ValueError('Measurement geometry must fit the complete pre-scan image')
        if any(min(p[1] for p in rows[i])>=min(p[1] for p in rows[i+1]) for i in range(len(rows)-1)):raise ValueError('Rows must follow forward acquisition order')
        position=self._reply(struct.pack('<II',0x104,0),0x104,28)
        if not -1000<=struct.unpack_from('<i',position,24)[0]<=0:raise ProtocolError('Sheet is not in retained pre-scan position')
        self.instrument.calibration_blob();target=round(min(p[1] for p in rows[0])+110)
        self._reply(struct.pack('<5I',0x105,0,120,0,target),0x105,8);self.phase=Phase.MEASURING
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            message=self._event(max(.001,deadline-time.monotonic()))
            if struct.unpack_from('<I',message)[0]==0x304 and ImageRow.decode(message).index>=target:break
        else:raise TimeoutError('Forward capture did not reach first row')
        for row_index, (command, points) in enumerate(zip(commands, rows)):
            self._reply(command,0x106,8);deadline=time.monotonic()+seconds_per_row;count=0
            while count<len(points):
                message=self._event(max(.001,deadline-time.monotonic()))
                if struct.unpack_from('<I',message)[0]==0x305:
                    self.raw_samples.append(RawSpectrum.decode(message));count+=1
                    if on_point is not None:
                        old=self.instrument._row_callback_rpc_blocked
                        self.instrument._row_callback_rpc_blocked=True
                        try:on_point(len(self.raw_samples),sum(map(len,rows)))
                        finally:self.instrument._row_callback_rpc_blocked=old
                if time.monotonic()>deadline:raise TimeoutError('Spectral row did not finish')
            if on_row is not None:
                self.instrument._row_callback_rpc_blocked=row_index<len(rows)-1
                try:on_row(len(self.raw_samples),sum(map(len,rows)))
                finally:self.instrument._row_callback_rpc_blocked=False
        # Old pre-scan/measurement state must not satisfy the homing barrier.
        self.last_status=None
        self.instrument.events=[p for p in self.instrument.events if struct.unpack_from('<I',p)[0]!=0x300]
        self._reply(struct.pack('<I',0x100),0x100,8)
        deadline=time.monotonic()+30
        while True:
            time.sleep(.1);self.instrument.status()
            for message in self.instrument.events:
                if struct.unpack_from('<I',message)[0]==0x300:self._check_state(message)
            if self.last_status and self.last_status.mechanism!=11:break
            if time.monotonic()>deadline:raise TimeoutError('Sensor homing timeout; ejection not sent')
        self._reply(struct.pack('<II',0x101,1),0x101,8);self.phase=Phase.DONE
        return tuple(self.raw_samples)

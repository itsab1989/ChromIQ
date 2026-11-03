import socket,struct,unittest
from unittest.mock import patch
from fd9_independent.client import Instrument
from fd9_independent.display import chunks,raster
from fd9_independent.motion import RawAcquisition,Phase,DeviceStopped,line_command
from fd9_independent.protocol import ProtocolError


def frame(payload):return struct.pack('<BBH',1,0,len(payload))+payload
def reply(command,size=8):return struct.pack('<II',command,0)+bytes(size-8)
def state(mechanism,paper=1,stop=0):return struct.pack('<9I',0x300,1,1,1,stop,mechanism,paper,0,0)
def image(row):return struct.pack('<IIh',0x304,3640,row)+b'\x7f'*3638
def position(row):return reply(0x104,24)+struct.pack('<i',row)
def spectrum():return struct.pack('<I4H',0x305,1,2,3,4)+struct.pack('<152f',*([.75]*152))


class SocketScript:
    def __init__(self,messages):self.events=[frame(p) if p is not None else None for p in messages];self.active=b'';self.sent=[];self.closed=False
    def recv(self,size):
        if not self.active:
            if not self.events:return b''
            event=self.events.pop(0)
            if event is None:raise socket.timeout()
            self.active=event
        result=self.active[:min(size,61)];self.active=self.active[len(result):];return result
    def sendall(self,data):self.sent.append(data)
    def settimeout(self,value):pass
    def close(self):self.closed=True


def commands(sent):
    result=[]
    for batch in sent:
        offset=0
        while offset<len(batch):
            length=struct.unpack_from('<H',batch,offset+2)[0];result.append(struct.unpack_from('<I',batch,offset+4)[0]);offset+=4+length
    return result


class MotionTests(unittest.TestCase):
    def test_nonfinal_progress_cannot_interrupt_the_next_row_with_a_sensor_query(self):
        script=[reply(3),position(-1),reply(1,7348),reply(0x105),image(400),reply(0x106),spectrum()]
        sock=SocketScript(script)
        instrument=Instrument('synthetic',socket_factory=lambda *_:sock).connect()
        workflow=RawAcquisition(instrument,enable_experimental_motion=True)
        workflow.phase=Phase.SCANNED;workflow.image={i:b'' for i in range(400)}
        def query(count,total):instrument.sensor_status()
        with self.assertRaisesRegex(RuntimeError,'Nonfinal row callbacks'):
            workflow.measure([[(100,200)],[(100,240)]],on_row=query)
        self.assertNotIn(0x200,commands(sock.sent))
        self.assertEqual(len(workflow.raw_samples),1)
        self.assertFalse(instrument._row_callback_rpc_blocked)
        self.assertTrue(sock.closed)

    def test_passive_multirow_progress_and_final_diagnostic_remain_allowed(self):
        sensor=struct.pack('<IIBBHIII',0x200,0,3,4,5,0,0,0)
        script=[reply(3),position(-1),reply(1,7348),reply(0x105),image(400),
                reply(0x106),spectrum(),reply(0x106),spectrum(),sensor,
                reply(0x100),state(11),reply(0,40),state(0,0),reply(0,40),reply(0x101)]
        sock=SocketScript(script)
        instrument=Instrument('synthetic',socket_factory=lambda *_:sock).connect()
        workflow=RawAcquisition(instrument,enable_experimental_motion=True)
        workflow.phase=Phase.SCANNED;workflow.image={i:b'' for i in range(400)}
        progress=[]
        def record(count,total):
            progress.append((count,total))
            if count==total:self.assertEqual(instrument.sensor_status().measurement_sum_count,5)
        with patch('fd9_independent.motion.time.sleep'):
            workflow.measure([[(100,200)],[(100,240)]],on_row=record)
        self.assertEqual(progress,[(1,2),(2,2)])
        self.assertEqual(commands(sock.sent).count(0x106),2)
        self.assertEqual(commands(sock.sent).count(0x200),1)
        self.assertEqual(workflow.phase,Phase.DONE)

    def test_original_artwork_and_new_serialization(self):
        for kind in (1,3):
            parts=chunks(kind);self.assertEqual(len(parts),29);self.assertEqual(len(parts[0]),8064);self.assertEqual(len(parts[-1]),1344)
            pixels=raster(kind);self.assertEqual(len(pixels),320*352);self.assertEqual(set(pixels),{0,255})
            self.assertEqual(b''.join(p[64:] for p in parts),b''.join(b'\xff\xff' if p else b'\0\0' for p in pixels))
            for i,p in enumerate(parts):self.assertEqual(struct.unpack_from('<I',p,60)[0],i)
        self.assertNotEqual(raster(1),raster(3))

    def test_opt_in_and_geometry_checks_precede_commands(self):
        instrument=Instrument('synthetic')
        with self.assertRaises(ValueError):RawAcquisition(instrument)
        with self.assertRaises(ValueError):line_command([(float('nan'),20)]*12,True,False)
        with self.assertRaises(ValueError):line_command([(20,20)]*12,True,False)
        with self.assertRaises(ValueError):line_command([(i,20) for i in range(12)],True,False)

    def test_complete_single_connection_raw_workflow(self):
        # Invented messages only; no capture, SDK result, graphics or calibration fixture.
        script=[reply(3),reply(0,40),reply(1,7348),reply(4,12),reply(5),state(4),reply(5),state(5),reply(0x203,10),position(4),reply(1,7348),reply(0x105)]+[image(i) for i in range(400)]+[image(-1),None,position(-1),reply(0,40),position(-1),reply(1,7348),reply(0x105),image(400),reply(0x106)]+[spectrum()]*12+[reply(0x100),state(11),reply(0,40),state(0,0),reply(0,40),reply(0x101)]
        sock=SocketScript(script);factory=[]
        def connect(*args):factory.append(args);return sock
        with patch('fd9_independent.motion.time.sleep'):
            with Instrument('synthetic',socket_factory=connect) as instrument:
                workflow=RawAcquisition(instrument,enable_experimental_motion=True);workflow.prepare('SYNTHETIC');self.assertEqual(len(workflow.prescan()),3638*400)
                progress=[]
                values=workflow.measure([[(100+80*i,200) for i in range(12)]],on_row=lambda n,total:progress.append((n,total)))
                self.assertEqual(progress,[(12,12)])
                self.assertEqual(len(values),12);self.assertEqual(workflow.phase,Phase.DONE)
        ids=commands(sock.sent);self.assertEqual(len(factory),1);self.assertEqual(ids.count(3),1);self.assertEqual(ids.count(0x105),2);self.assertEqual(ids.count(0x101),1);self.assertGreater(ids.index(0x101),ids.index(0x106));self.assertTrue(sock.closed)

    def test_device_cancel_prevents_capture(self):
        sock=SocketScript([reply(3),reply(0,40),reply(1,7348),reply(4,12),reply(5),state(4,stop=1)])
        instrument=Instrument('synthetic',socket_factory=lambda *_:sock).connect();workflow=RawAcquisition(instrument,enable_experimental_motion=True)
        with self.assertRaises(DeviceStopped):workflow.prepare('SYNTHETIC')
        self.assertNotIn(0x105,commands(sock.sent));self.assertTrue(sock.closed);self.assertEqual(workflow.phase,Phase.FAILED)

    def test_automatic_readiness_requires_paper_then_scan_ready_state(self):
        class ReadinessSocket(SocketScript):
            def recv(self,size):
                if not self.active and self.events:
                    event=self.events[0]
                    if event==frame(state(4,paper=0)):
                        self_outer.assertEqual(commands(self.sent).count(5),29)
                    if event==frame(state(5)):
                        self_outer.assertEqual(commands(self.sent).count(5),58)
                return super().recv(size)
        self_outer=self
        sock=ReadinessSocket([reply(3),reply(0,40),reply(1,7348),reply(4,12),reply(5),state(4,paper=0),state(4),reply(5),state(5)])
        with Instrument('synthetic',socket_factory=lambda *_:sock) as instrument:
            workflow=RawAcquisition(instrument,enable_experimental_motion=True)
            workflow.begin_loading();self.assertEqual(workflow.phase,Phase.WAITING)
            workflow.wait_ready(60);self.assertEqual(workflow.phase,Phase.READY)
            self.assertNotIn(0x105,commands(sock.sent))

    def test_incomplete_image_prevents_measurement(self):
        sock=SocketScript([reply(3),reply(0x203,10),position(4),reply(1,7348),reply(0x105),image(1),image(-1),None])
        instrument=Instrument('synthetic',socket_factory=lambda *_:sock).connect();workflow=RawAcquisition(instrument,enable_experimental_motion=True);workflow.phase=Phase.READY
        with self.assertRaises(ProtocolError):workflow.prescan()
        self.assertNotIn(0x106,commands(sock.sent));self.assertTrue(sock.closed)

    def test_unknown_homing_state_never_ejects(self):
        script=[reply(3),position(-1),reply(1,7348),reply(0x105),image(400),reply(0x106)]+[spectrum()]*12+[reply(0x100),reply(0,40)]
        sock=SocketScript(script);instrument=Instrument('synthetic',socket_factory=lambda *_:sock).connect();workflow=RawAcquisition(instrument,enable_experimental_motion=True);workflow.phase=Phase.SCANNED
        workflow.image={i:b'' for i in range(400)}
        with patch('fd9_independent.motion.time.sleep'):
            with self.assertRaises(ConnectionError):workflow.measure([[(100+80*i,200) for i in range(12)]])
        self.assertNotIn(0x101,commands(sock.sent));self.assertEqual(len(workflow.raw_samples),12)

    def test_invalid_geometry_does_not_register_or_create_output(self):
        from fd9_independent.acquire import capture_raw
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'capture'
            with patch('fd9_independent.acquire.Instrument') as instrument:
                with self.assertRaises(ValueError):capture_raw('synthetic',[[(0,0)]*12],root,enable_experimental_motion=True)
                instrument.assert_not_called();self.assertFalse(root.exists())

    def test_failure_evidence_records_raw_not_reflectance(self):
        from fd9_independent.acquire import capture_raw
        import tempfile,json
        from pathlib import Path
        sock=SocketScript([reply(3),reply(0,40),reply(1,7348),reply(4,12),reply(5),state(4,stop=1)])
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'capture';result=capture_raw('synthetic',[[(100+80*i,200) for i in range(12)]],root,enable_experimental_motion=True,socket_factory=lambda *_:sock)
            self.assertFalse(result['success']);self.assertFalse(result['calibrated_reflectance']);self.assertTrue((root/'SHA256SUMS').exists());self.assertTrue((root/'wire/received.bin').exists())
            self.assertEqual(json.loads((root/'result.json').read_text())['phase'],'failed')


if __name__=='__main__':unittest.main()

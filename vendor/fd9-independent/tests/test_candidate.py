import ast
import math
from pathlib import Path
import struct
import tempfile
import unittest
from fd9_independent import Instrument,ProtocolError,RawSpectrum,SheetStatus,ImageRow
from fd9_independent.protocol import MessageDecoder


def frame(payload, more=0):return struct.pack('<BBH',1,more,len(payload))+payload


class FakeSocket:
    def __init__(self,data,fragment=3):self.data=data;self.fragment=fragment;self.sent=[];self.closed=False
    def recv(self,size):
        n=min(size,self.fragment,len(self.data));result=self.data[:n];self.data=self.data[n:];return result
    def sendall(self,data):self.sent.append(data)
    def settimeout(self,value):pass
    def close(self):self.closed=True


class CandidateTests(unittest.TestCase):
    def test_fragmentation_and_multichunk_message(self):
        a=struct.pack('<I',0x1234)+b'abc';b=struct.pack('<I',0x5678)+b'xyz';wire=frame(a[:4],1)+frame(a[4:])+frame(b)
        for step in (1,2,4,9,8192):
            decoder=MessageDecoder();result=[]
            for i in range(0,len(wire),step):result.extend(decoder.feed(wire[i:i+step]))
            decoder.finish();self.assertEqual(result,[a,b])

    def test_malformed_and_bounded_messages_fail_closed(self):
        for wire in (b'\0\0\4\0',b'\1\2\4\0',b'\1\0\0\0',b'\1\0\1 '+b'x'):
            decoder=MessageDecoder()
            with self.assertRaises(ProtocolError):decoder.feed(wire)
            with self.assertRaises(ProtocolError):decoder.feed(frame(struct.pack('<I',0)))
        decoder=MessageDecoder(maximum_message=8)
        with self.assertRaises(ProtocolError):decoder.feed(frame(b'12345678',1)+frame(b'9'))
        decoder=MessageDecoder();decoder.feed(frame(struct.pack('<I',1))[:-1])
        with self.assertRaises(ProtocolError):decoder.finish()

    def test_registration_status_and_async_notifications(self):
        notification=struct.pack('<9I',0x300,*range(8));status=struct.pack('<10I',0,0,*range(8))
        sock=FakeSocket(frame(struct.pack('<II',3,0))+frame(notification)+frame(status))
        client=Instrument('test',socket_factory=lambda *_:sock)
        with client:self.assertEqual(client.status()['raw_words'],list(range(8)))
        self.assertTrue(sock.closed);self.assertEqual(len(client.events),1)
        self.assertEqual(SheetStatus.decode(client.events[0]).mechanism,4)
        self.assertEqual([struct.unpack_from('<I',p,4)[0] for p in sock.sent],[3,0])
        with tempfile.TemporaryDirectory() as t:
            output=Path(t)/'session';client.save_transcript(output)
            self.assertTrue((output/'manifest.json').exists())
            with self.assertRaises(FileExistsError):client.save_transcript(output)

    def test_declined_registration_and_nonzero_status_close(self):
        sock=FakeSocket(frame(struct.pack('<II',3,201)))
        client=Instrument('test',socket_factory=lambda *_:sock)
        with self.assertRaises(ProtocolError):client.connect()
        self.assertTrue(sock.closed)
        sock=FakeSocket(frame(struct.pack('<II',3,0))+frame(struct.pack('<10I',0,201,*range(8))))
        client=Instrument('test',socket_factory=lambda *_:sock).connect()
        with self.assertRaises(ProtocolError):client.status()
        self.assertTrue(sock.closed)

    def test_eof_inside_reply_closes_connection(self):
        sock=FakeSocket(frame(struct.pack('<II',3,0))[:-2]);client=Instrument('test',socket_factory=lambda *_:sock)
        with self.assertRaises(ProtocolError):client.connect()
        self.assertTrue(sock.closed)

    def test_instrument_data_is_opaque_not_a_bundled_table(self):
        blob=b'\x55'*7340;sock=FakeSocket(frame(struct.pack('<II',3,0))+frame(struct.pack('<II',1,0)+blob),fragment=4096)
        with Instrument('test',socket_factory=lambda *_:sock) as client:self.assertEqual(client.calibration_blob(),blob)

    def test_raw_parsers_do_not_claim_reflectance(self):
        payload=struct.pack('<I4H',0x305,1,2,3,4)+struct.pack('<152f',*([.5]*152));raw=RawSpectrum.decode(payload)
        self.assertEqual(len(raw.blocks),4);self.assertEqual(len(raw.blocks[0]),38)
        with self.assertRaises(NotImplementedError):raw.reflectance()
        invalid=payload[:12]+struct.pack('<f',math.nan)+payload[16:]
        with self.assertRaises(ProtocolError):RawSpectrum.decode(invalid)
        row=ImageRow.decode(struct.pack('<IIh',0x304,3640,-12)+b'\x7f'*3638);self.assertEqual(row.index,-12)
        with self.assertRaises(ProtocolError):ImageRow.decode(b'x')

    def test_source_has_no_external_imports_or_vendor_assets(self):
        root=Path(__file__).resolve().parents[1];allowed={'argparse','bisect','dataclasses','enum','functools','hashlib','json','math','pathlib','socket','shlex','struct','threading','time','types','uuid'}
        for path in (root/'src').rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node,ast.Import):self.assertTrue(all(a.name.split('.')[0] in allowed for a in node.names),path)
                if isinstance(node,ast.ImportFrom) and node.level==0:self.assertIn(node.module.split('.')[0],allowed,path)
        self.assertEqual(list((root/'src').rglob('*.bin')),[]);self.assertEqual(list((root/'src').rglob('*.json')),[])


if __name__=='__main__':unittest.main()

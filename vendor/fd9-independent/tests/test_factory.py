import struct
import unittest

from fd9_independent import Instrument, ProtocolError
from fd9_independent.factory import FactoryCharacterization, SensorFactoryRecord, sensor_factory_request, RECORD_SIZES
from test_candidate import FakeSocket, frame


class FactoryTests(unittest.TestCase):
    def test_checked_fingerprint_does_not_mistake_mutable_records_for_identity(self):
        def checked(data):return data+struct.pack('<I',(~sum(data))&0xffffffff)
        raw={kind:bytes(size) for kind,size in RECORD_SIZES.items()}
        for kind in (0,7,10):raw[kind]=checked(bytes(RECORD_SIZES[kind]-4))
        combined=checked(bytes(sum(RECORD_SIZES[k] for k in range(1,7))-4))
        start=0
        for kind in range(1,7):
            raw[kind]=combined[start:start+RECORD_SIZES[kind]];start+=RECORD_SIZES[kind]
        def snapshot():return FactoryCharacterization(tuple(SensorFactoryRecord(v,k) for k,v in raw.items()))
        original=snapshot()
        raw[8]=b'x'*RECORD_SIZES[8];raw[9]=b'y'*RECORD_SIZES[9]
        changed=snapshot()
        self.assertNotEqual(original.sha256,changed.sha256)
        self.assertEqual(original.verified_sections_sha256,changed.verified_sections_sha256)
        raw[7]=checked(b'z'*(RECORD_SIZES[7]-4))
        self.assertNotEqual(changed.verified_sections_sha256,snapshot().verified_sections_sha256)

    def test_read_only_request_and_private_record(self):
        raw = bytes(range(256)) * 9 + bytes(range(208))
        reply = struct.pack('<IIBBH', 0x206, 0, 0, 7, 0) + raw
        sock = FakeSocket(frame(struct.pack('<II', 3, 0)) + frame(reply), fragment=13)
        with Instrument('test', socket_factory=lambda *_: sock) as instrument:
            result = instrument.sensor_factory_data()
        self.assertEqual(result.raw, raw)
        self.assertEqual(len(result.sha256), 64)
        self.assertEqual(sock.sent[-1], b'\0\0\6\0' + sensor_factory_request())
        self.assertEqual(sensor_factory_request(), b'\6\2\0\0\0\7')
        self.assertTrue(sock.closed)

    def test_identification_record_and_unadmitted_kinds(self):
        raw = bytes(range(28))
        result = SensorFactoryRecord.from_reply(struct.pack('<IIBBH', 0x206, 0, 0, 0, 0)+raw, 0)
        self.assertEqual(result.kind, 0)
        self.assertEqual(result.raw, raw)
        for kind in (-1, 11, 256, True):
            with self.assertRaises(ValueError):sensor_factory_request(kind)

    def test_bad_reply_is_not_accepted_as_characterization(self):
        raw = b'x' * 2512
        for header in [(0x206, 1, 0, 7, 0), (0x206, 0, 1, 7, 0),
                       (0x206, 0, 0, 6, 0), (0x206, 0, 0, 7, 1)]:
            with self.assertRaises(ProtocolError):
                SensorFactoryRecord.from_reply(struct.pack('<IIBBH', *header) + raw)
        for bad in (b'', raw, struct.pack('<IIBBH', 0x206, 0, 0, 7, 0) + raw + b'x'):
            with self.assertRaises(ProtocolError):SensorFactoryRecord.from_reply(bad)

    def test_characterization_checks_joined_data_and_sensor_identity(self):
        def checked(data):return data+struct.pack('<I', (~sum(data))&0xffffffff)
        raw={k:b'\0'*size for k,size in RECORD_SIZES.items()}
        for k in (0,7,10):raw[k]=checked(bytes([k+1])*(RECORD_SIZES[k]-4))
        combined=checked(bytes(i%251 for i in range(sum(RECORD_SIZES[k] for k in range(1,7))-4)))
        start=0
        for k in range(1,7):
            raw[k]=combined[start:start+RECORD_SIZES[k]];start+=RECORD_SIZES[k]
        records=[SensorFactoryRecord(v,k) for k,v in raw.items()]
        snapshot=FactoryCharacterization(tuple(reversed(records)))
        self.assertEqual(snapshot.primary_data,combined[:-4])
        self.assertEqual(snapshot.sha256,FactoryCharacterization(tuple(records)).sha256)
        changed=records.copy();b=bytearray(raw[2]);b[123]^=1;changed[2]=SensorFactoryRecord(bytes(b),2)
        with self.assertRaises(ProtocolError):FactoryCharacterization(tuple(changed))
        with self.assertRaises(ValueError):FactoryCharacterization(tuple(records[:-1]))
        with self.assertRaises(ValueError):FactoryCharacterization(tuple(records+[records[0]]))


if __name__ == '__main__':unittest.main()

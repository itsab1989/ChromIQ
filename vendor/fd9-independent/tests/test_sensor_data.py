import math
import struct
import unittest

from fd9_independent import Instrument, ProtocolError
from fd9_independent.sensor_data import CachedSensorData, SensorDataUnavailable, cached_data_request
from test_candidate import FakeSocket, frame


def reply(selector=0, values=None, flags=0):
    if values is None:values=[.25]*(152 if selector==0 else 36)
    return struct.pack('<IIB3sHHI',0x205,0,0,b'abc',1,len(values),flags)+struct.pack(f'<{len(values)}f',*values)


class SensorDataTests(unittest.TestCase):
    def test_reads_two_shapes_and_preserves_unknown_metadata(self):
        sock=FakeSocket(frame(struct.pack('<II',3,0))+frame(reply())+frame(reply(1)))
        with Instrument('test',socket_factory=lambda *_:sock) as instrument:
            self.assertEqual(len(instrument.cached_sensor_data().values),152)
            native=instrument.cached_sensor_data(1)
            self.assertEqual(native.values,(.25,)*36)
            self.assertEqual(native.opaque_header,b'abc')
        self.assertEqual(sock.sent[1],b'\0\0\6\0\5\2\0\0\0\1')
        self.assertEqual(sock.sent[2],b'\0\0\11\0\5\2\0\0\1\1\0\0\0')

    def test_sensor_error_is_preserved_without_retry_or_disconnect(self):
        error_reply=struct.pack('<II2B',0x205,0,7,10)
        status=struct.pack('<10I',0,0,*range(8))
        sock=FakeSocket(frame(struct.pack('<II',3,0))+frame(error_reply)+frame(status))
        with Instrument('test',socket_factory=lambda *_:sock) as instrument:
            with self.assertRaises(SensorDataUnavailable) as caught:instrument.cached_sensor_data(1)
            self.assertEqual(caught.exception.sensor_result,7)
            self.assertEqual(instrument.status()['raw_words'],list(range(8)))
        self.assertEqual(len(sock.sent),3)

    def test_bad_data_and_unknown_controls_are_not_measurements(self):
        for bad in (reply()[:-1],reply(values=[math.nan]*152),reply(1)):
            with self.assertRaises(ProtocolError):CachedSensorData.from_reply(bad)
        with self.assertRaises(SensorDataUnavailable):CachedSensorData.from_reply(reply(flags=1))
        for selector,controls in [(2,(1,0,0,0)),(True,(1,0,0,0)),(0,(1,2,0,0)),(1,(1,0,0,256)),(1,(1,0))]:
            with self.assertRaises(ValueError):cached_data_request(selector,controls)


if __name__=='__main__':unittest.main()

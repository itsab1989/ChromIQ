import socket,struct,threading,unittest
from fd9_independent.client import Instrument,OperationCancelled
from test_candidate import FakeSocket,frame


class CancellationTests(unittest.TestCase):
    def test_cancel_before_command_sends_nothing(self):
        stop=threading.Event();sock=FakeSocket(frame(struct.pack('<II',3,0)))
        c=Instrument('test',socket_factory=lambda *_:sock,cancelled=stop.is_set).connect()
        stop.set();before=len(sock.sent)
        with self.assertRaises(OperationCancelled):c.status()
        self.assertEqual(len(sock.sent),before);self.assertTrue(sock.closed)
    def test_cancel_interrupts_quiet_notification_wait(self):
        stop=threading.Event()
        class Quiet(FakeSocket):
            def recv(self,n):
                if self.data:return super().recv(n)
                stop.set();raise socket.timeout()
        sock=Quiet(frame(struct.pack('<II',3,0)),fragment=100)
        c=Instrument('test',socket_factory=lambda *_:sock,cancelled=stop.is_set).connect()
        with self.assertRaises(OperationCancelled):c.receive_event(120)
        self.assertTrue(sock.closed);self.assertEqual(len(sock.sent),1)
    def test_quiet_event_timeout_keeps_connection_for_next_event(self):
        class Quiet(FakeSocket):
            def recv(self,n):
                if self.data:return super().recv(n)
                raise socket.timeout()
        sock=Quiet(frame(struct.pack('<II',3,0)),fragment=100)
        c=Instrument('test',socket_factory=lambda *_:sock,cancelled=lambda:False).connect()
        with self.assertRaises(TimeoutError):c.receive_event(.001)
        self.assertFalse(sock.closed)
        sock.data=frame(struct.pack('<9I',0x300,*range(8)))
        self.assertEqual(struct.unpack_from('<I',c.receive_event())[0],0x300)
        c.close()

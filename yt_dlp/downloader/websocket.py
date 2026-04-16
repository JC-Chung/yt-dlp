import contextlib
import os
import signal
import threading

from .common import FileDownloader
from .external import FFmpegFD
from ..networking import Request


class FFmpegSinkFD(FileDownloader):
    """ A sink to ffmpeg for downloading fragments in any form """

    def real_download(self, filename, info_dict):
        info_copy = info_dict.copy()
        info_copy['url'] = '-'

        def call_conn(proc, stdin):
            try:
                self.real_connection(stdin, info_dict)
            except OSError:
                pass
            finally:
                with contextlib.suppress(OSError):
                    stdin.flush()
                    stdin.close()
                os.kill(os.getpid(), signal.SIGINT)

        class FFmpegStdinFD(FFmpegFD):
            @classmethod
            def get_basename(cls):
                return FFmpegFD.get_basename()

            def on_process_started(self, proc, stdin):
                thread = threading.Thread(target=call_conn, daemon=True, args=(proc, stdin))
                thread.start()

        return FFmpegStdinFD(self.ydl, self.params or {}).download(filename, info_copy)

    def real_connection(self, sink, info_dict):
        """ Override this in subclasses """
        raise NotImplementedError('This method must be implemented by subclasses')


class WebSocketFragmentFD(FFmpegSinkFD):
    def real_connection(self, sink, info_dict):
        with self.ydl.urlopen(Request(
            info_dict['url'],
            headers=info_dict.get('http_headers', {}),
        )) as ws:
            while True:
                recv = ws.recv()
                if isinstance(recv, str):
                    recv = recv.encode('utf8')
                sink.write(recv)

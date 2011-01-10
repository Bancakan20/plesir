import tornado
import tornado.options
import tornado.httpserver
import tornado.ioloop as ioloop
import tornado.web
import simplejson as json

from struct import *
import zlib

import socket
import fcntl
import logging
try:
    import multiprocessing
except ImportError:
    multiprocessing = None
import time
import errno

def _cpu_count():
    if multiprocessing is not None:
        try:
            return multiprocessing.cpu_count()
        except NotImplementedError:
            pass
    try:
        return os.sysconf("SC_NPROCESSORS_CONF")
    except ValueError:
        pass

    logging.error("Could not detect number of processors; "
                  "running with one process")
    return 1

def pack_json( json_object ):
    format = "!II"
    compressed_data = zlib.compress(json.dumps(json_string))
    crc32 = zlib.crc32(json_string)
    return pack(format, crc32, len(compressed_data)) + compressed_data

def unpack_json( packed_json ):
    format = "!II"
    crc32, length = unpack( format, packed_json[:8] )
    compressed_data = packed_json[8:length+8]
    return json.loads(zlib.decompress(compressed_data))

class PlesirServer(object):
    def __init__( self, io_loop=None ):
        self.io_loop = io_loop
        self._socket = None
        self._started = False

    def listen( self, port, address=""):
        self.bind( port, address )
        self.start( 1 )

    def bind( self, port, address=""):
        assert not self._socket
        self._socket = socket.socket( socket.AF_INET, socket.SOCK_STREAM, 0 )
        flags = fcntl.fcntl(self._socket.fileno(), fcntl.F_GETFD)
        flags |= fcntl.FD_CLOEXEC
        fcntl.fcntl( self._socket.fileno(), fcntl.F_SETFD, flags )
        self._socket.setsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 )
        self._socket.setblocking( 0 )
        self._socket.bind((address, port))
        self._socket.listen( 128 )

    def start( self, num_processes=1 ):
        assert not self._started
        self._started = True
        if num_processes is None or num_processes <= 0:
            num_processes = 1
        if num_processes > 1 and ioloop.IOLoop.initialized():
            logging.error("Cannot run multiple IOLOOP")
            num_processes = 1
        if num_processes > 1:
            logging.info("Pre-forking %d server processes", num_processes)
            for i in range(num_processes):
                if os.fork() == 0:
                    import random
                    from binascii import hexlify
                    try:
                        seed = long( hexlify(os.urandom(16)), 16)
                    except NotImplementedError:
                        seed(int(time.time() * 1000) * os.getpid())
                    random.seed( seed )
                    self.io_loop = ioloop.IOLoop.instance()
                    self.io_loop.add_handler(
                        self._socket.fileno(), self._handle_events, ioloop.IOLoop.READ )
                    return
            os.waitpid(-1, 0)
        else:
            if not self.io_loop:
                self.io_loop = ioloop.IOLoop.instance()
                self.io_loop.add_handler( self._socket.fileno(), self._handle_events, ioloop.IOLoop.READ )

    def stop( self ):
        self.io_loop.remove_handler( self._socket.fileno() )
        self._socket.close()

    def _handle_events( self, fd, events ):
        while True:
            try:
                connection, address = self._socket.accept()
            except socket.error, e:
                if e.args[0] in (errno.EWOULDBLOCK, errno.EAGAIN):
                    return
                raise
            stream = iostream.IOStream(connection, io_loop = self.io_loop)
            PlesirConnection(stream, address)
        
        
class PlesirConnection(object):
    def __init__( self, stream, address ):
        self.stream = stream
        self.address = address

    def write( self, json_object ):
        if not self.stream.closed():
            packed_json = pack_json( json_data )
            self.stream.write( packed_json )


class StreamHandler( tornado.web.RequestHandler ):
    def get(self):
        format = self.get_argument("format", None)
        if format in ("html", None, ""):
            items = ["a", "b", "c"]
            self.render("templates/stream_view.html", items=items)
        elif format == "json":
            self.set_header("Content-Type", "application/json")
            self.write({"response":"ok", "data": {"foo":"bar"}})
    def post(self):
        pass

def main():
    application = tornado.web.Application([
            (r"/", StreamHandler),
        ])
    io_loop = ioloop.IOLoop.instance()
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    plesir_server = PlesirServer(io_loop)
    plesir_server.bind(50000)
    plesir_server.start(-1)
    io_loop.start()


if __name__ == "__main__":
    main()

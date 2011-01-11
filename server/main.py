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
import asyncmongo
import microtron
import lxml
import lxml.html
import lxml.etree

version_string = "1.0b"
version_info   = (0,9,9)
credits        = {"name"   : "Plesir Server",
                  "author" : "Bancakan Committee"}

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

def prefixed_json( json_object ):
    format = "!I"
    json_string = json.dumps(json_object)
    return pack(format, len(json_string)) + json_string

def compress_json( json_object ):
    format = "!II"
    json_string = json.dumps(json_object)
    compressed_data = zlib.compress(json_string)
    crc32 = zlib.crc32(json_string)
    return pack(format, len(compressed_data), crc32) + compressed_data

def decompress_json( packed_json ):
    format = "!II"
    length, crc32 = unpack( format, packed_json[:8] )
    compressed_data = packed_json[8:length+8]
    return json.loads(zlib.decompress(compressed_data))

class PlesirServer(object):
    def __init__( self, io_loop=None ):
        self.io_loop = io_loop
        self._socket = None
        self._started = False
        self.connections = []

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
        logging.info("Starting Plesir Server...")
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
            logging.info("Server runs on single thread mode.")
            if not self.io_loop:
                self.io_loop = ioloop.IOLoop.instance()
            self.io_loop.add_handler( self._socket.fileno(), self._handle_events, ioloop.IOLoop.READ )
    def stop( self ):
        self.io_loop.remove_handler( self._socket.fileno() )
        self._socket.close()

    def _close_callback( self, *args, **kwargs ):
        for conn in self.connections:
            if conn.stream.closed():
                logging.info("Client %s: %d disconnected" % conn.address)
                self.connections.remove(conn)
                
    
    def _handle_events( self, fd, events ):
        while True:
            try:
                connection, address = self._socket.accept()
                logging.info( "Connection coming from %s port %d", address[0], address[1])
            except socket.error, e:
                if e.args[0] in (errno.EWOULDBLOCK, errno.EAGAIN):
                    return
                raise
            stream = tornado.iostream.IOStream(connection, io_loop = self.io_loop)
            stream.set_close_callback( self._close_callback )
            conn = PlesirConnection(stream, address)
            self.connections.append( conn )
        
        
class PlesirConnection(object):
    def __init__( self, stream, address ):
        self.stream = stream
        self.address = address
        #self.stream.write(prefixed_json({"status":"ok","data":{}}))
    def write( self, json_object, prefixed=False, compressed=False ):
        if not self.stream.closed():
            if not prefixed:
                stream_out = json.dumps( json_object )+"\r\n\r\n"
            else:
                if not compressed:
                    stream_out = prefixed_json( json_object )
                else:
                    stream_out = compress_json( json_object )
            self.stream.write( stream_out )
        
class StreamHandler( tornado.web.RequestHandler ):
    out_channel = None
    def __init__(self, application, request, **kwargs):
        tornado.web.RequestHandler.__init__(self, application, request)
        self.out_channel = kwargs["out_channel"]
        
    def get(self):
        format = self.get_argument("format", None)
        #if self.out_channel is not None and len(self.out_channel.streaminfo) > 0:
        #    for stream, address in self.out_channel.streaminfo:
        #        stream.write("Hellowwww %s:%d" % address)
        if format in ("html", None, ""):
            items = ["a", "b", "c"]
            self.render("templates/stream_view.html", items=items)
        elif format == "json":
            self.set_header("Content-Type", "application/json")
            self.write({"response":"ok", "data": {"foo":"bar"}})

    def post(self):
        post_id = self.get_argument("format", None)
        title = self.get_argument("title", None)
        contents = self.get_argument("contents", None)
        tree = lxml.html.document_fromstring(contents)
        parser = microtron.Parser(tree)
        review = parser.parse_format("hreview")[0]
        hcards = parser.parse_format("hcard")
        
        '''
        Save Format on MongoDB and packet
        {
            title: <title>,
            dtreviewed: <datetime>,
            photos: [<url>,<url>,<url>]
            geo:
                lat: <lat>
                long: <long>
            url: <string>
            reviewer: <string>
            address:
                country:
                locality:
                postal-code:
                region:
                street-address:
                tel:
            name:
            
        }
        '''

        place_hcard = hcards[0]
        place_photo = place_hcard["photo"]
        photo_list = [ {"src":s["src"], "alt":s["alt"]} for s in place_photo ]  
        item = review["item"]
        address = item["adr"][0]
        date_obj = review["dtreviewed"]["date"]
        date_dict = {"day": date_obj.day, "month": date_obj.month, "year":date_obj.year}
        sdata = {"title": title,
                 "dtreviewed": date_dict,
                 "photos": photo_list,
                 "geo": {"lat":float(item["geo"]["latitude"]),
                         "long":float(item["geo"]["longitude"])},
                 "url": "http://www.masdab.com",
                 "reviewer": review["reviewer"]["fn"],
                 "description":review["description"]}

        db = asyncmongo.Client(pool_id="plesir", host="127.0.0.1",
                               port=27017, dbname="plesir")
        
        def insert_log_cb(response, error):
            assert len(response) == 1
            
        db.posts.insert(sdata, callback=insert_log_cb)

        json_string = json.dumps(sdata)+"\r\n\r\n"

        if self.out_channel is not None and len(self.out_channel.connections) > 0:
            for conn in self.out_channel.connections:
                # conn.stream.write(pack("!I", 56))
                conn.write(sdata, True, False)

        self.set_header("Content-Type", "application/json")
        self.write({"response":"ok"})


def main():
    print '''
 ____                                      __                                                                                                                                        
/\\  _`\\                                   /\\ \\                                                                                                                                       
\\ \\ \\L\\ \\     __      ___     ___     __  \\ \\ \\/'\\      __      ___                                                                                                                  
 \\ \\  _ <'  /'__`\\  /' _ `\\  /'___\\ /'__`\\ \\ \\ , <    /'__`\\  /' _ `\\                                                                                                                
  \\ \\ \\L\\ \\/\\ \\L\\.\\_/\\ \\/\\ \\/\\ \\__//\\ \\L\\.\\_\\ \\ \\\\`\\ /\\ \\L\\.\\_/\\ \\/\\ \\                                                                                                               
   \\ \\____/\\ \\__/.\\_\\ \\_\\ \\_\\ \\____\\ \\__/.\\_\\\\ \\_\\ \\_\\ \\__/.\\_\\ \\_\\ \\_\\                                                                                                              
    \\/___/  \\/__/\\/_/\\/_/\\/_/\\/____/\\/__/\\/_/ \\/_/\\/_/\\/__/\\/_/\\/_/\\/_/

             ----------------------------------------------
             %s - (c) 2010 %s
             version %s
             ----------------------------------------------\n\n''' % \
        (credits["name"], credits["author"], version_string)

    plesir_server = PlesirServer(ioloop.IOLoop.instance())
    plesir_server.bind(50000)
    
    application = tornado.web.Application([
            (r"/", StreamHandler, {"out_channel":plesir_server}),
        ])
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    plesir_server.start(1)
    try:
        ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        logging.info("Stopping...")
        logging.info("Stopping Plesir Socket Server...")
        plesir_server.stop()
        logging.info("Stopping Plesir HTTP Server...")
        http_server.stop()
        logging.info("Stopping I/O Loop...")
        ioloop.IOLoop.instance().stop()
        logging.info("Stopping complete!")

if __name__ == "__main__":
    main()

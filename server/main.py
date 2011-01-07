import tornado
import tornado.options
import tornado.httpserver
import tornado.ioloop
import tornado.web
import simplejson as json

from struct import *
import zlib

def pack_json( json_string ):
    format = "!II"
    compressed_data = zlib.compress(json_string)
    crc32 = zlib.crc32(json_string)
    return pack(format, crc32, len(compressed_data)) + compressed_data



class PlesirConnection(object):
    def __init__( self, stream, address ):
        self.stream = stream
        self.address = address
    


class StreamHandler( tornado.web.RequestHandler ):
    def __init__(self, out_channel=None):
        super(StreamHandler, self).__init__()
        self.out_channel = out_channel
    def get(self):
        format = self.get_argument("format", None)
        if format in ("html", None, ""):
            items = ["a", "b", "c"]
            self.render("templates/stream_view.html", items=items)
        elif format == "json":
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({"response":"ok", "data": {"foo":"bar"}}))
    def post(self):
        pass

def main():
    application = tornado.web.Application([
            (r"/", StreamHandler)
        ])
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()

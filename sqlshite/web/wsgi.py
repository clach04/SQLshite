#!/usr/bin/env python
# -*- coding: us-ascii -*-
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab
#
"""wsgi based Web UI
"""

import json
import logging
import os
import sys



import mimetypes
from pprint import pprint

import socket
import struct
import sys
import time


from wsgiref.simple_server import make_server

try:
    import bjoern
except ImportError:
    bjoern = None

try:
    import cheroot  # CherryPy Server https://cheroot.cherrypy.dev/en/latest/pkg/cheroot.wsgi/
except ImportError:
    cheroot = None

try:
    import meinheld  # https://github.com/mopemope/meinheld
except ImportError:
    meinheld = None

import stache

import sqlshite



log = logging.getLogger(__name__)
logging.basicConfig()
log.setLevel(level=logging.DEBUG)

DEFAULT_SERVER_PORT = 8777

def serve_file(path, content_type=None):
    """returns file type and file object, assumes file exists (and readable), returns [] for file on read error"""
    if content_type is None:
        content_type = mimetypes.guess_type(path)[0]
    try:
        #f = open(path, 'rb')  # for supporting streaming
        fp = open(path, 'rb')
        f = [fp.read()]  # hack so we can get length at expensive of no streaming and reading entire file in to memory
        fp.close()
    except IOError:
        f = []
    return content_type, f

def to_bytes(in_str):
    # could choose to only encode for Python 3+
    return in_str.encode('utf-8')

def not_found(environ, start_response):
    """serves 404s."""
    #start_response('404 NOT FOUND', [('Content-Type', 'text/plain')])
    #return ['Not Found']
    start_response('404 NOT FOUND', [('Content-Type', 'text/html')])
    return [to_bytes('''<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
<html><head>
<title>404 Not Found</title>
</head><body>
<h1>Not Found</h1>
<p>The requested URL /??????? was not found on this server.</p>
</body></html>''')]


# Weekday and month names for HTTP date/time formatting; always English!
_weekdayname = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_monthname = [None, # Dummy so we can use 1-based month numbers
              "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def header_format_date_time(timestamp):
    year, month, day, hh, mm, ss, wd, y, z = time.gmtime(timestamp)
    return "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
        _weekdayname[wd], day, _monthname[month], year, hh, mm, ss
    )

def current_timestamp_for_header():
    return header_format_date_time(time.time())


def determine_local_ipaddr():
    local_address = None

    # Most portable (for modern versions of Python)
    if hasattr(socket, 'gethostbyname_ex'):
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith('127.'):
                local_address = ip
                break
    # may be none still (nokia) http://www.skweezer.com/s.aspx/-/pypi~python~org/pypi/netifaces/0~4 http://www.skweezer.com/s.aspx?q=http://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib has alonger one

    if sys.platform.startswith('linux'):
        import fcntl

        def get_ip_address(ifname):
            ifname = ifname.encode('latin1')
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            return socket.inet_ntoa(fcntl.ioctl(
                s.fileno(),
                0x8915,  # SIOCGIFADDR
                struct.pack('256s', ifname[:15])
            )[20:24])

        if not local_address:
            for devname in os.listdir('/sys/class/net/'):
                try:
                    ip = get_ip_address(devname)
                    if not ip.startswith('127.'):
                        local_address = ip
                        break
                except IOError:
                    pass

    # Jython / Java approach
    if not local_address and InetAddress:
        addr = InetAddress.getLocalHost()
        hostname = addr.getHostName()
        for ip_addr in InetAddress.getAllByName(hostname):
            if not ip_addr.isLoopbackAddress():
                local_address = ip_addr.getHostAddress()
                break

    if not local_address:
        # really? Oh well lets connect to a remote socket (Google DNS server)
        # and see what IP we use them
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 53))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith('127.'):
            local_address = ip

    return local_address



def my_start_server(callable_app):
    print('Python %s on %s' % (sys.version, sys.platform))
    server_port = int(os.environ.get('PORT', DEFAULT_SERVER_PORT))

    print("Serving on port %d..." % server_port)
    local_ip = os.environ.get('LISTEN_ADDRESS', determine_local_ipaddr())
    log.info('open : http://%s:%d', 'localhost', server_port)
    log.info('open : http://%s:%d', local_ip, server_port)
    log.info('Starting server: %r', (local_ip, server_port))
    simple_app = callable_app()
    # TODO modjy/Jython
    if bjoern:
        log.info('Using: bjoern')
        bjoern.run(simple_app, '', server_port)  # FIXME use local_ip?
    elif cheroot:
        # Untested
        server = cheroot.wsgi.Server(('0.0.0.0', server_port), my_crazy_app)  # '' untested for address
        server.start()
    elif meinheld:
        # Untested, Segmentation fault when serving a file :-(
        meinheld.server.listen(('0.0.0.0', server_port))  # does not accept ''
        meinheld.server.run(simple_app)
    else:
        log.info('Using: wsgiref.simple_server')
        httpd = make_server('', server_port, simple_app)  # FIXME use local_ip?
        httpd.serve_forever()


host_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'www')

global_config = {}
global_dbs = {}

def list_databases(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    result = []

    path_info = environ['PATH_INFO']
    path_info_list = [x for x in path_info.split('/') if x]
    database = path_info_list[1]
    dal = global_dbs[database]
    static_template = """{{#databases}}{{.}}</br>{{/databases}}
"""
    result.append(stache.render(static_template, {'databases': [table_name for table_name in dal.schema]}).encode('utf-8'))
    """
    for table_name in dal.schema:
        result.append(table_name.encode('utf-8'))
    """

    start_response(status, headers)
    return result

# WSGI application class
class DalWebApp:
    def __call__(self, environ, start_response):
        status = '200 OK'
        headers = [('Content-type', 'text/plain')]
        result= []

        path_info = environ['PATH_INFO']
        path_info_list = [x for x in path_info.split('/') if x]
        if path_info.startswith('/d/') and len(path_info_list) == 2:
            return list_databases(environ, start_response)

        # Returns a dictionary in which the values are lists
        if environ.get('QUERY_STRING'):
            get_dict = parse_qs(environ['QUERY_STRING'])
        else:
            get_dict = {}  # wonder if should make None to make clear its not there at all

        # dump out information about request
        #print(environ)
        #pprint(environ)
        print('PATH_INFO %r' % environ['PATH_INFO'])
        print('PATH_INFO split %r' % environ['PATH_INFO'].split('/'))
        print('PATH_INFO split2%r' % path_info_list)
        print('CONTENT_TYPE %r' % environ.get('CONTENT_TYPE'))  # missing under bjoern
        print('QUERY_STRING %r' % environ.get('QUERY_STRING'))  # missing under bjoern
        print('QUERY_STRING dict %r' % get_dict)
        print('REQUEST_METHOD %r' % environ['REQUEST_METHOD'])
        print('Filtered headers, HTTP*')
        for key in environ:
            if key.startswith('HTTP_'):  # TODO potentially startswith 'wsgi' as well
                # TODO remove leading 'HTTP_'?
                print('http header ' + key + ' = ' + repr(environ[key]))

        # TODO if not GET
        # POST values
        # the environment variable CONTENT_LENGTH may be empty or missing
        try:
            request_body_size = int(environ.get('CONTENT_LENGTH', 0))
        except (ValueError):
            request_body_size = 0
        request_body = None

        read_body_payload = True
        if environ['REQUEST_METHOD'] != 'GET' and read_body_payload:
            # Read POST, etc. body
            if request_body_size:
                print('read with size %r' % request_body_size)
                request_body = environ['wsgi.input'].read(request_body_size)
            else:
                print('read with NO size')
                #import pdb ; pdb.set_trace()
                request_body = environ['wsgi.input'].read()  # everything, seen on linux where zero param would return no bytes
                print('read with NO size completed')

        #if path_info and path_info.startswith('/'):

        print('body payload: %r' % request_body)
        if environ.get('CONTENT_TYPE') == 'application/json' and json and request_body:
            # 1. Validate the payload - with stacktrace on failure
            # 2. Pretty Print/display the payload
            print('POST json body\n-------------\n%s\n-------------\n' % json.dumps(json.loads(request_body), indent=4))
        #print('environ %r' % environ)
        if True:
            # Disable this to send 200 and empty body
            return not_found(environ, start_response)

        # see if there is a flat file on the filesystem
        if path_info and path_info.startswith('/'): # assuming ALWAYS_RETURN_404=false (or at least not true)
            filename = os.path.join(host_dir, path_info[1:])
            filename = os.path.abspath(filename)  # trim of trailing slashes, and handle relative paths ./ and ../
            print('check if we have %r file locally to serve' % filename)
        if os.path.exists(filename):
            content_type, result = serve_file(filename)
            print(content_type)
            if result:
                if content_type:
                    headers = [('Content-type', content_type)]
                if 1:
                    headers.append(('Content-Length', str(len(result[0]))))
                    #headers.append(('Last-Modified', 'Sun, 01 Jan 2023 18:53:39 GMT'))  # this is the format expected
                    headers.append(('Last-Modified', current_timestamp_for_header()))  # many clients will cache
                    # TODO 'Date'? bjoern does NOT include this by default where as wsgiref does

            print('serving static file %r' % path_info)
        else:
            # return 404 by default
            return not_found(environ, start_response)
            # over ride to change behavior
            pass  # return empty
            #result.append(to_bytes('hello'))  # or some dummy data


        start_response(status, headers)
        return result


def main(argv=None):
    if argv is None:
        argv = sys.argv

    print('Python %s on %s' % (sys.version, sys.platform))

    try:
        config_filename = argv[1]
    except IndexError:
        config_filename = None

    if config_filename:
        f = open(config_filename, 'rb')
        json_bytes = f.read()
        f.close()
        config = json.loads(json_bytes)
    else:
        config = {
            "databases": {
                "memory": ":memory:",
            },
        }
    print(host_dir)
    print(config)
    global_config.update(config)
    for database_name in config["databases"]:
        connection_string = config["databases"][database_name]
        db = sqlshite.DatabaseWrapper(connection_string)
        db.do_connect()
        dal = sqlshite.DataAccessLayer(db)
        global_dbs[database_name] = dal
    my_start_server(DalWebApp)

    return 0

if __name__ == "__main__":
    sys.exit(main())

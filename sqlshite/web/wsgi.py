#!/usr/bin/env python
# -*- coding: us-ascii -*-
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab
#
"""wsgi based Web UI
"""

import copy
import json
import logging
import os
import sys


try:
    # py 3.8+
    from html import escape as escape_html
except ImportError:
    # py2
    from cgi import escape as escape_html

try:
    # py2 (and <py3.8)
    from cgi import parse_qs
except ImportError:
    # py3
    from urllib.parse import parse_qs


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
#logging.basicConfig()
# post python 2.5
logging_fmt_str = "%(process)d %(thread)d %(asctime)s - %(name)s %(filename)s:%(lineno)d %(funcName)s() - %(levelname)s - %(message)s"
formatter = logging.Formatter(logging_fmt_str)
ch = logging.StreamHandler()  # use stdio
ch.setFormatter(formatter)
log.addHandler(ch)

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

def not_found_404(environ, start_response):
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

render_template_cache = {}
def render_template(template_filename, variables, use_cache=False):
    """Where use_cache means both lookup and store in cache
    Returns bytes
    """
    template_filename = os.path.join(host_dir, template_filename)
    if use_cache:
        template_string = render_template_cache.get(template_filename)
    else:
        template_string = None

    if not template_string:
        f = open(template_filename, 'rb')
        template_string = f.read().decode('utf-8')
        f.close()
        if use_cache:
            render_template_cache[template_filename] = template_string

    return stache.render(template_string, variables).encode('utf-8')

global_config = {}
global_dbs = {}

def list_databases(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    result = []

    path_info = environ['PATH_INFO']
    path_info_list = [x for x in path_info.split('/') if x]
    result.append(render_template('list_databases.html', {'databases': [database_name for database_name in global_dbs]}))
    start_response(status, headers)
    return result

def list_tables(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    result = []

    path_info = environ['PATH_INFO']
    path_info_list = [x for x in path_info.split('/') if x]
    #current_path = '/'.join(path_info_list)  # TODO current full URL
    database = path_info_list[1]
    dal = global_dbs.get(database)
    if not dal:
        return not_found_404(environ, start_response)
    result.append(render_template('list_tables.html', {'tables': [table_name for table_name in dal.schema]}))
    start_response(status, headers)
    return result

def jsonform(environ, start_response):
    """Serves a jsonform suitable for use with:
          * https://jsonform.github.io/jsonform/playground/
          * https://github.com/jsonform/jsonform
    """
    status = '200 OK'
    headers = [('Content-type', 'application/json')]
    result = []

    path_info = environ['PATH_INFO']
    path_info_list = [x for x in path_info.split('/') if x]
    #current_path = '/'.join(path_info_list)  # TODO current full URL
    database = path_info_list[1]
    table_name = path_info_list[2]
    dal = global_dbs.get(database)
    if not dal:
        return not_found_404(environ, start_response)
    jsonform_dict = dal.jsonform.get(table_name)
    if not jsonform_dict:
        return not_found_404(environ, start_response)
    result.append(json.dumps(jsonform_dict, indent=4))
    start_response(status, headers)
    return result

def view_row(environ, start_response, dal, table_name, schema, rowid):
    """View a single row
    TODO headers to avoid caching
    TODO serve html currently serves json, which can be used with https://jsonform.github.io/jsonform/playground/
    /view.json
    /edit.json....
    """
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    result = []

    jsonform_dict = dal.jsonform.get(table_name)
    if not jsonform_dict:
        return not_found_404(environ, start_response)

    sql = 'select * from "%s" where rowid=?' % table_name  # Assume table really exists from previous caller sanity checks
    cursor = dal.db.cursor
    cursor.execute(sql, (rowid,))
    column_names = list(x[0] for x in cursor.description)  # or use schema... has more detail (at least for SQLite)
    row = cursor.fetchone()
    if not row:
        return not_found_404(environ, start_response)
    row_dict = dict(zip(column_names, row))
    jsonform = copy.copy(jsonform_dict)
    jsonform['value'] = row_dict
    # FIXME this assumes, and deletes the buttons from the form
    #del(jsonform["form"][-1])  # FIXME

    result.append(json.dumps(jsonform, indent=4, default=str))
    start_response(status, headers)
    return result

def view_html(environ, start_response, dal, table_name, schema, rowid):
    """View a row, NOTE duplication of code with add and edit
    FIXME redirect if not ending in /
    """
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    result = []

    # TODO use rowid?
    filename = os.path.join(host_dir, 'viewform.html')
    start_response(status, headers)
    content_type, result = serve_file(filename)
    return result

def add_row(environ, start_response, dal, table_name, schema=None):
    """Explore a table
    """
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    result = []

    filename = os.path.join(host_dir, 'jsonform.html')
    start_response(status, headers)
    content_type, result = serve_file(filename)
    return result

def sql_editor(environ, start_response, dal):
    """Explore a table
    """
    status = '200 OK'
    headers = [('Content-type', 'text/html')]

    # form GET -- TODO POST support
    # Returns a dictionary in which the values are lists
    if environ.get('QUERY_STRING'):
        get_dict = parse_qs(environ['QUERY_STRING'])
    else:
        get_dict = {}  # wonder if should make None to make clear its not there at all

    sql = get_dict.get('sql_str')
    if sql:
        try:
            sql = sql[0]
        except IndexError:
            sql = None

    if sql:
        return table_rows(environ, start_response, dal, table_name=None, schema=None, sql=sql)  # TODO some way to indicate this query came from raw SQL
    # else
    filename = os.path.join(host_dir, 'sql_editor.html')
    start_response(status, headers)
    content_type, result = serve_file(filename)
    return result

def table_rows(environ, start_response, dal, table_name, schema=None, sql=None):
    """Explore a table
    """
    status = '200 OK'
    headers = [('Content-type', 'text/html')]

    if sql:
        generated_sql = False
    else:
        generated_sql = True
    sql = sql or 'select rowid as sqlite_rowid, * from "%s"' % table_name
    cursor = dal.db.cursor
    cursor.execute(sql)
    column_names = list(x[0] for x in cursor.description)  # or use schema... has more detail (at least for SQLite)
    if generated_sql:
        column_names = column_names[1:]
    row = cursor.fetchone()
    start_response(status, headers)
    yield b'WIP, no paging/offset support</br>'
    yield b'<table border>\n    <tr>'
    for column_name in column_names:
        tmp_str = "<th>" + escape_html(column_name) + "</th>"
        yield tmp_str.encode('utf-8')
    yield b'</tr>\n'
    while row:
        yield b'<tr>\n'
        if generated_sql:
            rowid = row[0]
            row = row[1:]
            column_value_template = '<a href="/d/%s/%s/view/%d/">%%s</a>' % (dal.name, table_name, rowid)  # TODO escaping?
        else:
            column_value_template = '%s'
        for column_value in row:
            tmp_str = "<td>" + column_value_template % escape_html(str(column_value)) + "</td>"  # FIXME string processng, for example boolean to check-box
            yield tmp_str.encode('utf-8')
        yield b'</tr>\n'
        row = cursor.fetchone()
    yield b'</table>\n'
    # TODO commit...

def table_explore(environ, start_response, path_info=None, path_info_list=None):
    """Explore a table
    TODO redirect if not ending in / and database view
    """
    log.debug('entry')
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    result = []

    path_info_list = path_info_list or [x for x in environ['PATH_INFO'].split('/') if x]
    log.debug('path_info %r', path_info)
    log.debug('path_info_list %r', path_info_list)

    if '?' not in path_info and not path_info.endswith('.json') and not path_info.endswith('/'):
        # dumb redirect
        log.debug('**** REDIRECT %r' % (path_info, ))
        start_response('302 Found', [('Location', path_info + '/')])
        return b'redirect with trailing /'

    if len(path_info_list) == 4:
        if path_info.endswith('/jsonform.json'):
            return jsonform(environ, start_response)

    #current_path = '/'.join(path_info_list)  # TODO current full URL
    database = path_info_list[1]
    table_name = path_info_list[2]
    dal = global_dbs.get(database)
    if not dal:
        return not_found_404(environ, start_response)
    if len(path_info_list) == 3 and path_info_list[2] == 'sql':
        # maybe http://localhost/d/DATABASE_NAME/sql
        return sql_editor(environ, start_response, dal)
    schema = dal.schema.get(table_name)
    if not schema:
        return not_found_404(environ, start_response)
    if len(path_info_list) == 4:
        if path_info_list[3] == 'rows':
            return table_rows(environ, start_response, dal, table_name, schema)
        elif path_info_list[3] == 'add':
            return add_row(environ, start_response, dal, table_name, schema)
        else:
            operation = path_info_list[3]
            try:
                # Assume SQLite3
                rowid = int(operation)
                return view_row(environ, start_response, dal, table_name, schema, rowid)
            except ValueError:
                pass  # just view table
    elif len(path_info_list) == 5:
        try:
            if path_info_list[3] == 'view':
                # http://localhost:8777/d/memory/kitchen_sink/view/1
                # http://localhost:8777/d/memory/kitchen_sink/view/1/
                operation = path_info_list[4]
                rowid = int(operation)
                return view_html(environ, start_response, dal, table_name, schema, rowid)
            elif path_info.endswith('/view.json'):  # TODO edit
                # http://localhost:8777/d/memory/kitchen_sink/1/view.json  # unused yet...
                # Assume SQLite3
                operation = path_info_list[3]
                rowid = int(operation)
                return view_row(environ, start_response, dal, table_name, schema, rowid)  # FIXME remove buttons
        except ValueError:
            pass  # just view table
    elif len(path_info_list) == 6:
        try:
            if path_info.endswith('/view.json'):  # TODO edit
                # http://localhost:8777/d/memory/kitchen_sink/view/1/view.json
                operation = path_info_list[4]
                rowid = int(operation)
                return view_row(environ, start_response, dal, table_name, schema, rowid)
        except ValueError:
            pass  # just view table

    result.append(b'WIP')
    result.append(b' <a href="jsonform.json">jsonform.json</a></br>')
    result.append(b' <a href="rows/">rows</a></br>')
    result.append(b' <a href="view/1/">view 1</a></br>')
    result.append(b' <a href="add/">add</a></br>')
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
        print('DalWebApp: path_info %r' % path_info)
        print('DalWebApp: path_info_list %r' % path_info_list)

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
            start_response(status, headers)
            return result

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

        print('body payload: %r' % request_body)  # e.g. from a form POST (looks like GET key/values)
        if environ.get('CONTENT_TYPE') == 'application/json' and json and request_body:
            # 1. Validate the payload - with stacktrace on failure
            # 2. Pretty Print/display the payload
            print('POST json body\n-------------\n%s\n-------------\n' % json.dumps(json.loads(request_body), indent=4))
        #print('environ %r' % environ)

        if path_info == '/d' or path_info.startswith('/d/'):
            if len(path_info_list) == 1:
                return list_databases(environ, start_response)
            elif len(path_info_list) == 2:
                return list_tables(environ, start_response)
            elif len(path_info_list) in (3, 4, 5, 6):
                return table_explore(environ, start_response, path_info=path_info, path_info_list=path_info_list)


        if True:
            # Disable this to send 200 and empty body
            return not_found_404(environ, start_response)

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
        print('No config file specified, defaulting to:')
        print('%s' % json.dumps(config, indent=4))
    print(host_dir)
    print(config)
    global_config.update(config)
    for database_name in config["databases"]:
        connection_string = config["databases"][database_name]
        db = sqlshite.DatabaseWrapper(connection_string)
        db.do_connect()
        dal = sqlshite.DataAccessLayer(db, name=database_name)
        global_dbs[database_name] = dal
    my_start_server(DalWebApp)

    return 0

if __name__ == "__main__":
    sys.exit(main())

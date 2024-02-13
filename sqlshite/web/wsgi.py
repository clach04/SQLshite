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
    # py3
    from urllib.parse import parse_qs
except ImportError:
    # py2 (and <py3.8)
    from cgi import parse_qs

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

is_jy = hasattr(sys, 'JYTHON_JAR') or str(copyright).find('Jython') > 0

log = logging.getLogger(__name__)
#logging.basicConfig()
# post python 2.5
logging_fmt_str = "%(process)d %(thread)d %(asctime)s - %(name)s %(filename)s:%(lineno)d %(funcName)s() - %(levelname)s - %(message)s"
formatter = logging.Formatter(logging_fmt_str)
ch = logging.StreamHandler()  # use stdio
ch.setFormatter(formatter)
log.addHandler(ch)

log.setLevel(level=logging.DEBUG)

try:
    unicode
except NameError:
    # Python 3
    unicode = str

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

    if is_jy:
        from java.net import InetAddress
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
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

render_template_cache = {}
def render_template(template_filename, variables, use_cache=False):
    """Where use_cache means both lookup and store in cache
    Returns bytes
    """
    template_filename = os.path.join(template_dir, template_filename)
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
    # TODO add option to rescan ALL databases
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
    result.append(render_template('list_tables.html', {'database_name': dal.name, 'tables': [table_name for table_name in dal.schema]}))
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
    result.append(json.dumps(jsonform_dict, indent=4, default=str).encode('utf-8'))
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

    result.append(json.dumps(jsonform, indent=4, default=str).encode('utf-8'))
    start_response(status, headers)
    return result

def view_html(environ, start_response, dal, table_name, schema, rowid, request_body=None):
    """View a row, NOTE duplication of code with add and edit
    FIXME redirect if not ending in /
    NOTE actually edit...
    """
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    result = []

    if request_body:
        #  {b'number=&str=qwertyuiop%5B&float=&date=&datetime=&bottles_of_beer=99&delimited+id='}
        print('view_html rowid %r request_body %r' % (rowid, request_body,))
        value_dict = parse_first_values(request_body)
        # Now figure out was this an ADD or EDIT/UPDATE? Assume as VIEW this is EDIT
        database_result = insert_update_row(dal, table_name, value_dict, schema=schema, update=True, rowid=rowid)
        rowid = database_result.get('rowid')
        if rowid:
            # redirect....
            #log.debug('**** REDIRECT %r' % (path_info, ))
            #start_response('302 Found', [('Location', path_info + '/')])
            start_response('302 Found', [('Location', '../%s' % unicode(rowid))])
            return [b'redirect to view']
        # TODO handle errors....
        print('view_html rowid %r database_result %r' % (rowid, database_result,))  # should be rowid, unless rowid/pk was updated...
        return return_json(environ, start_response, value_dict)  # DEBUG TODO do something

    # TODO use rowid?
    result.append(render_template('viewform.html', {'table_name': table_name}))
    start_response(status, headers)
    return result

def rescan(environ, start_response, dal):
    """Explore a table
    """
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    result = []

    dal.scan_schema()
    result.append(b'rescan complete')  # TODO/FIXME replace with a template, redirect to parent?
    start_response(status, headers)
    return result

def insert_update_row(dal, table_name, user_values_dict, schema=None, update=False, rowid=None):
    """schema required as do not trust column names in user_values_dict
    TODO error handling/reporting
    """
    row_value_dict = {}
    schema = schema or dal.schema.get(table_name)
    # TODO has table_name been validated?
    for metadata in schema:
        column_name, python_type = metadata[0], metadata[1]
        row_value_dict[column_name] = None
    for column_name in user_values_dict:
        row_value_dict[column_name] = user_values_dict[column_name]  # TODO catch missing items and return error
    # row_value_dict now contains values form user or None/NULL
    if not update:
        # have an INSERT, remove None/NULL values (let DBMS default)
        for column_name in list(row_value_dict.keys()):
            if row_value_dict[column_name] is None:
                del row_value_dict[column_name]

    columns_names_in_statement = []
    bind_parameters = []  # will become a tuple later
    for metadata in schema:
        column_name, python_type = metadata[0], metadata[1]
        if column_name in row_value_dict:
            columns_names_in_statement.append(column_name)
            bind_parameters.append(row_value_dict[column_name])

    if update:
        # TODO determine primary key and value
        if rowid:
            primary_key = '"rowid"'
            bind_parameters.append(rowid)
        else:
            raise NotImplemented()  # pick first column in schema? what about compound keys...
        sql = 'UPDATE "%s" SET "%s"=? WHERE %s=?' % (table_name, '"=?, "'.join(columns_names_in_statement), primary_key)
        # TODO detect zero row update and report back as an error
    else:
        # have an INSERT
        bind_markers_str = ', '.join(['?',] * len(bind_parameters))
        sql = 'INSERT INTO "%s" ("%s") VALUES (%s)' % (table_name, '", "'.join(columns_names_in_statement), bind_markers_str)  # FIXME delimited column names

    log.debug('sql: %s' % sql)
    cursor = dal.db.cursor
    cursor.execute(sql, tuple(bind_parameters))
    # TODO return pk / lastrowid
    return {'rowid': row_value_dict.get('rowid', rowid if rowid is not None else cursor.lastrowid)}

def return_json(environ, start_response, value):
    """return a json object
    """
    '''
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    result = []
    start_response(status, headers)
    return result
    '''
    status = '200 OK'
    headers = [('Content-type', 'application/json; charset=utf-8')]  # make Microsoft Edge happy by including explict character set
    start_response(status, headers)
    return [json.dumps(value, indent=4).encode('utf-8')]

def parse_first_values(request_body):
    """Where request_body is parameter list from GET, POST form, etc.
    """
    #  b'number=&str=qwertyuiop%5B&float=&date=&datetime=&bottles_of_beer=99&delimited+id='
    print('add row request_body %r' % (request_body,))
    value_dict = parse_qs(request_body.decode('utf-8'))
    print('form values %s' % json.dumps(value_dict, indent=4))
    for temp_key in value_dict:
        value_dict[temp_key] = value_dict[temp_key][0]  # throw away the rest
    print('form values %s' % json.dumps(value_dict, indent=4))
    return value_dict

def add_row(environ, start_response, dal, table_name, schema=None, request_body=None):
    """Explore a table
    """
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    result = []

    """TODO handle
PATH_INFO '/d/memory/kitchen_sink/add/'
PATH_INFO split ['', 'd', 'memory', 'kitchen_sink', 'add', '']
PATH_INFO split2['d', 'memory', 'kitchen_sink', 'add']
CONTENT_TYPE 'application/x-www-form-urlencoded'
REQUEST_METHOD 'POST'
body payload: b'number=99&str=read+ballows&float=&date=2024-02-17&datetime=2024-02-27T11%3A12&bottles_of_beer=99&delimited+id='
Forefox (dev) did NOT offer time selection... and secs are masked out/not-sent :-(
    try:
        request_body_size = int(environ.get('CONTENT_LENGTH', 0))
    except (ValueError):
        request_body_size = 0
    request_body = {}

    if environ['REQUEST_METHOD'] != 'GET':  # for now assume POST
        # Read POST, etc. body
        # assume CONTENT_TYPE 'application/x-www-form-urlencoded'
        if request_body_size:
            request_body = environ['wsgi.input'].read(request_body_size)
        else:
            # read with NO size
            #import pdb ; pdb.set_trace()
            request_body = environ['wsgi.input'].read()  # everything, seen on linux where zero param would return no bytes
        value_dict = parse_qs(environ['request_body'])
        print('form values %s' % json.dumps(value_dict, indent=4))
    """

    if request_body:
        #FIXME value_dict = parse_first_values(request_body)
        #  b'number=&str=qwertyuiop%5B&float=&date=&datetime=&bottles_of_beer=99&delimited+id='
        print('add row request_body %r' % (request_body,))
        value_dict = parse_qs(request_body.decode('utf-8'))
        print('form values %s' % json.dumps(value_dict, indent=4))
        for temp_key in value_dict:
            value_dict[temp_key] = value_dict[temp_key][0]  # throw away the rest
        print('form values %s' % json.dumps(value_dict, indent=4))
        database_result = insert_update_row(dal, table_name, value_dict, schema=schema)
        rowid = database_result.get('rowid')
        if rowid:
            # redirect....
            #log.debug('**** REDIRECT %r' % (path_info, ))
            start_response('302 Found', [('Location', '../view/%s' % unicode(rowid))])
            return [b'redirect to view']

        return return_json(environ, start_response, value_dict)  # DEBUG TODO do something
    else:
        result.append(render_template('add_form.html', {'table_name': table_name}))

        #filename = os.path.join(host_dir, 'jsonform.html')
        start_response(status, headers)
        #content_type, result = serve_file(filename)
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
        return table_rows(environ, start_response, dal, table_name=None, schema=None, sql=sql, show_sql=True)
    # else
    filename = os.path.join(host_dir, 'sql_editor.html')
    start_response(status, headers)
    content_type, result = serve_file(filename)
    return result

def table_rows(environ, start_response, dal, table_name, schema=None, sql=None, bind_parameters=None, rowid_first_column_in_result=False, show_sql=False, html_top_inject=None):
    #return table_rows_stream_html_table(environ, start_response, dal, table_name, schema=schema, sql=sql, bind_parameters=bind_parameters, rowid_first_column_in_result=rowid_first_column_in_result, show_sql=show_sql)
    return table_rows_template_html_table(environ, start_response, dal, table_name, schema=schema, sql=sql, bind_parameters=bind_parameters, rowid_first_column_in_result=rowid_first_column_in_result, show_sql=show_sql, html_top_inject=html_top_inject)

def table_row_html_generator(dal, cursor, rowid_first_column_in_result, table_name):
    row = cursor.fetchone()
    row_count = 0
    while row:
        row_count += 1
        yield '<tr>\n'
        if rowid_first_column_in_result:
            rowid = row[0]
            row = row[1:]
            column_value_template = '<a href="/d/%s/%s/view/%d/">%%s</a>' % (dal.name, table_name, rowid)  # TODO escaping?
        else:
            column_value_template = '%s'
        for column_value in row:
            tmp_str = "<td>" + column_value_template % escape_html(unicode(column_value)) + "</td>"  # FIXME string processng, for example boolean to check-box
            yield tmp_str
        yield '</tr>\n'
        row = cursor.fetchone()

def table_row_html_buffered(dal, cursor, rowid_first_column_in_result, table_name):
    result = []
    row = cursor.fetchone()
    row_count = 0
    while row:
        row_count += 1
        result.append('<tr>\n')
        if rowid_first_column_in_result:
            rowid = row[0]
            row = row[1:]
            column_value_template = '<a href="/d/%s/%s/view/%d/">%%s</a>' % (dal.name, table_name, rowid)  # TODO escaping?
        else:
            column_value_template = '%s'
        for column_value in row:
            tmp_str = "<td>" + column_value_template % escape_html(unicode(column_value)) + "</td>"  # FIXME string processng, for example boolean to check-box
            result.append(tmp_str)
        result.append('</tr>\n')
        row = cursor.fetchone()
    return ''.join(result), row_count

def table_rows_template_html_table(environ, start_response, dal, table_name, schema=None, sql=None, bind_parameters=None, rowid_first_column_in_result=False, show_sql=False, html_top_inject=None):
    """Buffer rows from table/arbitary SQL query in a html table into a template then return
    """
    status = '200 OK'
    headers = [('Content-type', 'text/html')]
    result = []

    if sql:
        rowid_first_column_in_result = rowid_first_column_in_result or False
    else:
        rowid_first_column_in_result = True
    # TODO see if can detect primary key, and not assume rowid (ala rowid_first_column_in_result)
    sql = sql or 'select rowid as sqlite_rowid, * from "%s"' % table_name
    cursor = dal.db.cursor
    if bind_parameters:
        cursor.execute(sql, bind_parameters)
    else:
        cursor.execute(sql)
    column_names = list(x[0] for x in cursor.description)  # or use schema... has more detail (at least for SQLite)
    if column_names[0] == 'rowid':
        rowid_first_column_in_result = True
    """ If we can determine table name, can check for rowid....
    if rowid_first_column_in_result:
        column_names = column_names[1:]
    """
    if rowid_first_column_in_result:
        del(column_names[0])
    if not show_sql:
        sql = None

    # rows_html = table_row_html_generator(dal, cursor, rowid_first_column_in_result, table_name)
    rows_html, row_count = table_row_html_buffered(dal, cursor, rowid_first_column_in_result, table_name)
    result.append(render_template('rows_html_table.html', {
        'database_name': dal.name,
        'table_name': table_name or 'user SQL query',
        'column_names': column_names,
        'rows_html': rows_html,
        #'rows_html': table_row_html_generator(dal, cursor, rowid_first_column_in_result, table_name),
        'row_count': row_count,  # cursor.rowcount,  # not set at this point in time
        'html_top_inject': html_top_inject,
    }))
    start_response(status, headers)
    return result

def table_rows_stream_html_table(environ, start_response, dal, table_name, schema=None, sql=None, bind_parameters=None, rowid_first_column_in_result=False, show_sql=False):
    """Stream rows in table/arbitary SQL query in a html table
    """
    status = '200 OK'
    headers = [('Content-type', 'text/html')]

    if sql:
        rowid_first_column_in_result = rowid_first_column_in_result or False
    else:
        rowid_first_column_in_result = True
    sql = sql or 'select rowid as sqlite_rowid, * from "%s"' % table_name
    cursor = dal.db.cursor
    start_response(status, headers)
    try:
        if bind_parameters:
            cursor.execute(sql, bind_parameters)
        else:
            cursor.execute(sql)
        column_names = list(x[0] for x in cursor.description)  # or use schema... has more detail (at least for SQLite)
        if rowid_first_column_in_result:
            column_names = column_names[1:]
        row = cursor.fetchone()
        yield '''<!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
        <meta name="description" content="">
        <meta name="author" content="">

      <title>{{table_name}} SQLshite rows</title>
      <link rel="stylesheet" type="text/css" href="/css/bootstrap.css" />
      <script type="text/javascript" src="/js/jquery.min.js"></script>
      <script type="text/javascript" src="/js/tablesort.min.js"></script>

        <style>
            th[role=columnheader]:not(.no-sort) {
                cursor: pointer;
            }

            th[role=columnheader]:not(.no-sort):after {
                content: '';
                float: right;
                margin-top: 7px;
                border-width: 0 4px 4px;
                border-style: solid;
                border-color: #404040 transparent;
                visibility: hidden;
                opacity: 0;
                -ms-user-select: none;
                -webkit-user-select: none;
                -moz-user-select: none;
                user-select: none;
            }

            th[aria-sort=ascending]:not(.no-sort):after {
                border-bottom: none;
                border-width: 4px 4px 0;
            }

            th[aria-sort]:not(.no-sort):after {
                visibility: visible;
                opacity: 0.4;
            }

            th[role=columnheader]:not(.no-sort):hover:after {
                visibility: visible;
                opacity: 1;
            }
        </style>
    </head>
    <body>
      <h1>{{table_name}} rows</h1>
      <a href="../../">databases</a>  <a href="../">tables</a>  <a href="../">SQL</a></br>
    '''.replace('{{table_name}}', escape_html(table_name or 'user SQL query')).encode('utf-8')
        yield b'WIP, no paging/offset support</br>'
        if show_sql:
            # TODO code block and/or syntax highlighting
            yield 'SQL: {{sql}}'.replace('{{sql}}', escape_html(sql)).encode('utf-8')
        #yield b'<table border>\n    <tr>'  # table does not work well with default Bootstrap (at least on desktop, much better on mobile)
        yield b'<table  class="table table-striped" id="sqlrows" name="sqlrows">\n'
        yield b'<thead class="thead-dark">'  # this is not working, Bootstrap 4.0 feature?
        yield b'    <tr>'
        for column_name in column_names:
            tmp_str = "<th>" + escape_html(column_name) + "</th>"
            yield tmp_str.encode('utf-8')
        yield b'</tr>\n'
        yield b'</thead>\n'
        yield b'<tbody>\n'
        row_count = 0
        while row:
            row_count += 1
            yield b'<tr>\n'
            if rowid_first_column_in_result:
                rowid = row[0]
                row = row[1:]
                column_value_template = '<a href="/d/%s/%s/view/%d/">%%s</a>' % (dal.name, table_name, rowid)  # TODO escaping?
            else:
                column_value_template = '%s'
            for column_value in row:
                tmp_str = "<td>" + column_value_template % escape_html(unicode(column_value)) + "</td>"  # FIXME string processng, for example boolean to check-box
                yield tmp_str.encode('utf-8')
            yield b'</tr>\n'
            row = cursor.fetchone()
        yield b'</tbody>\n'
        yield b'</table>\n'
        yield b'<script>\n'
        yield b'''
function onPageReady() {
  // http://tristen.ca/tablesort/demo/ and https://github.com/tristen/tablesort
  new Tablesort(document.getElementById('sqlrows'));
}

// Run the above function when the page is loaded & ready
// TODO search all classes with sortable, instead of per table-id
document.addEventListener('DOMContentLoaded', onPageReady, false);
        \n'''
        yield b'</script>\n'
        row_count_str= '%d rows\n' % (row_count, )
        yield row_count_str.encode('utf-8')
    except dal.db.driver.Error as info:  # better than Exception as info:
        log.error('sql error %r', info)
        error_str ='<br><br>\n\n<span style="color:red">** ERROR **</span><br><br>' + escape_html(repr(info)) + escape_html(str(info)) +'<br><br>'
        yield error_str.encode('utf-8')
    finally:
        yield b'''
</body>
</html>
'''
    # TODO commit...

def table_explore(environ, start_response, path_info=None, path_info_list=None, request_body=None):
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
        return [b'redirect with trailing /']

    if len(path_info_list) == 4:
        if path_info.endswith('/jsonform.json'):
            return jsonform(environ, start_response)

    # form GET -- TODO POST support
    # Returns a dictionary in which the values are lists
    if environ.get('QUERY_STRING'):
        get_dict = parse_qs(environ['QUERY_STRING'])
    else:
        get_dict = {}  # wonder if should make None to make clear its not there at all

    q = get_dict.get('q')
    if q:
        try:
            q = q[0]
        except IndexError:
            q = None

    #current_path = '/'.join(path_info_list)  # TODO current full URL
    database = path_info_list[1]
    dal = global_dbs.get(database)
    if not dal:
        return not_found_404(environ, start_response)

    if len(path_info_list) == 3:
        if path_info_list[2] == 'sql':
            # maybe http://localhost/d/DATABASE_NAME/sql
            return sql_editor(environ, start_response, dal)
        elif path_info_list[2] == 'rescan':
            return rescan(environ, start_response, dal)

    table_name = path_info_list[2]
    schema = dal.schema.get(table_name)
    if not schema:
        return not_found_404(environ, start_response)

    # TODO Full Text Search support
    if q:
        # we have a quick search query
        quick_search_column_name = None  # FIXME config lookup option
        if quick_search_column_name is None:
            # find first string type, and use that for simple like to TABLE scan the entire table
            for metadata in schema:
                column_name, python_type = metadata[0], metadata[1]
                if python_type is str:
                    quick_search_column_name = column_name
                    break
        log.debug('quick_search_column_name %r', quick_search_column_name)
        orig_q = q
        if not q.startswith('%'):
            q = '%' + q
        if not q.endswith('%'):
            q = q + '%'
        sql = 'select rowid as sqlite_rowid, * from "%s" where "%s" like ?' % (table_name, quick_search_column_name)
        html_top_inject = '''<form method="GET"  id="quick_search" name="quick_search">
    quick search: <input type="text" name="q" id="q" value="%s"/><br>
    <button class="btn btn-primary" value="Submit"  type="submit">Search</button>
</form>

''' % (escape_html(orig_q),)  # or q
        return table_rows(environ, start_response, dal, table_name=table_name, schema=schema, sql=sql, bind_parameters=(q, ), rowid_first_column_in_result=True, html_top_inject=html_top_inject)

    if len(path_info_list) == 4:
        if path_info_list[3] == 'rows':
            return table_rows(environ, start_response, dal, table_name, schema)
        elif path_info_list[3] == 'add':
            return add_row(environ, start_response, dal, table_name, schema, request_body=request_body)
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
            if path_info_list[3] == 'view':  # TODO 'edit'
                # http://localhost:8777/d/memory/kitchen_sink/view/1
                # http://localhost:8777/d/memory/kitchen_sink/view/1/
                operation = path_info_list[4]
                rowid = int(operation)
                return view_html(environ, start_response, dal, table_name, schema, rowid, request_body=request_body)
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

    result.append(render_template('table_explorer.html', {'table_name': table_name}))
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

        if path_info == '/':
            path_info = '/index.html'
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
                return table_explore(environ, start_response, path_info=path_info, path_info_list=path_info_list, request_body=request_body)


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
        # FIXME config lookup option quick_search_column_name in config for override
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

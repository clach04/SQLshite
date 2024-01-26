#!/usr/bin/env python
# -*- coding: us-ascii -*-
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab
#
"""SQLite3 database to jsonschema
"""

import logging
import os
import sqlite3
import sys

try:
    #raise ImportError  # DEBUG force pypyodbc usage
    import pyodbc
except ImportError:
    try:
    # try fallback; requires ctypes
        import pypyodbc as pyodbc
    except ImportError:
        pyodbc = None


__version__ = '0.0.0'

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
disable_logging = False
#disable_logging = True
if disable_logging:
    log.setLevel(logging.NOTSET)  # only logs; WARNING, ERROR, CRITICAL

ch = logging.StreamHandler()  # use stdio

formatter = logging.Formatter("logging %(process)d %(thread)d %(asctime)s - %(filename)s:%(lineno)d %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
log.addHandler(ch)


def bool_converter(in_value):
    return bool(in_value)

# TODO uuid
sqlite3.register_converter('bool', bool_converter)
sqlite3.register_converter('boolean', bool_converter)
# TODO reverse; sqlite3.register_adapter()


def con2driver(connection_string):
    if connection_string == ':memory:':
        return sqlite3
    # if looks like path, return sqlite3
    # file.db
    # .\file.db
    # ./file.db
    # /tmp/file.db
    # \tmp\file.db
    # C:\tmp\file.db
    # Z:\tmp\file.db
    # \\some_server\file.db
    if '=' in connection_string:
        return pyodbc
    return sqlite3


def main(argv=None):
    if argv is None:
        argv = sys.argv

    connection_string = argv[1]  # dbname
    print('db: %s' % connection_string)
    table_name = 'gamestest20240106'
    db_driver = sql = None
    db_driver = db_driver or con2driver(connection_string)
    print(db_driver)
    print(db_driver is sqlite3)
    print(db_driver == sqlite3)
    print(dir(db_driver))
    sql = sql or 'select * from "%s"' % table_name
    con = db_driver.connect(connection_string, detect_types=sqlite3.PARSE_DECLTYPES)  # FIXME sqlite3 only
    # if not-SQLite can use description for data types
    # for SQLite3, can not trust datatype in description :-( Options;
    #   1. select a single row and use those types, assuming not-NULL values
    #   2. get DDL, and parse
    #   3. sqlite pragma
    try:
        cur = con.cursor()
        cur.execute(sql)
        print('%r' % (cur.description,))
        column_names = list(x[0] for x in cur.description)
        print('%r' % column_names)

        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        print('%r' % (cur.description,))
        print(cur.fetchall())

        cur.execute("SELECT * FROM sqlite_master WHERE type='table';")
        print('%r' % (cur.description,))
        print(cur.fetchall())

        print('-' * 65)
        meta = cur.execute("PRAGMA table_info('%s')" % table_name)
        for r in meta:
            print(r)

        cur.close()
        con.commit()
    finally:
        con.close()

    return 0

if __name__ == "__main__":
    sys.exit(main())

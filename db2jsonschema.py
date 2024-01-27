#!/usr/bin/env python
# -*- coding: us-ascii -*-
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab
#
"""SQLite3 database to jsonschema
"""

from datetime import date, datetime
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

# Naive timezone-unaware https://docs.python.org/3/library/sqlite3.html#sqlite3-adapter-converter-recipes
def convert_date(val):
    """Convert ISO 8601 date to datetime.date object."""
    return date.fromisoformat(val.decode())

def convert_datetime(val):
    """Convert ISO 8601 datetime to datetime.datetime object."""
    return datetime.fromisoformat(val.decode())

def convert_timestamp_num_secs(val):
    """Convert Unix epoch timestamp to datetime.datetime object."""
    return datetime.fromtimestamp(int(val))

sqlite3.register_converter("date", convert_date)
sqlite3.register_converter("datetime", convert_datetime)
sqlite3.register_converter("timestamp", convert_datetime)
sqlite3.register_converter("epoch_seconds", convert_timestamp_num_secs)
# DeprecationWarning: The default timestamp converter is deprecated as of Python 3.12; see the sqlite3 documentation for suggested replacement recipes
#   https://docs.python.org/3/library/sqlite3.html#default-adapters-and-converters-deprecated
#   https://docs.python.org/3/library/sqlite3.html#sqlite3-adapter-converter-recipes
#   https://github.com/python/cpython/issues/90016

# TODO reverse; sqlite3.register_adapter()

def sqlite_type_to_python(datatype_name):
    """datatype definition string from SQLite pragma table info to Python type lookup
    Ignores length information, e.g. VARCHAR(10) is returned as a string type, max length is ignored.
    """
    sqlite_type_dict = {
        # recognized by SQLite3 types https://sqlite.org/datatype3.html
        'int': int,
        'integer': int,
        'real': float,
        'text': str,
        'timestamp': datetime,
        ## end of builtins?
        # TODO NUMBER
        # TODO NUMERIC
        # TODO BLOB - byte
        # TODO consider Decimal type support
        'char': str,
        'nchar': str,
        'varchar': str,
        'nvarchar': str,
        'string': str,
        'date': date,
        'datetime': datetime,
        'bool': bool,
        'boolean': bool,
        'float': float,
        # TODO Affinity Name Examples from https://sqlite.org/datatype3.html#affinity_name_examples
    }
    datatype_name = datatype_name.lower()
    open_paren_index = datatype_name.find('(')
    if open_paren_index >= 0:
        datatype_name = datatype_name[:open_paren_index]
    return sqlite_type_dict[datatype_name]  # TODO consider returning string for misses

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

class DatabaseWrapper:
    def __init__(self, connection_string, driver=None):
        self.connection_string = connection_string
        self.driver = driver
        self.connection = None
        self.cursor = None

    def is_open(self, hard_fail=True):
        if self.connection:
            return True
        if hard_fail:
            raise NotImplementedError('Database is not open')
        return False

    # TODO del method
    def do_disconnect(self):
        #if self.connection:
        if self.is_open():
            try:
                self.cursor.close()
                self.cursor = None
            finally:
                self.connection.close()
                self.connection = None

    def do_connect(self):
        if self.connection is None:
            connection_string = self.connection_string
            db_driver = self.driver or con2driver(self.connection_string)
            if db_driver == sqlite3:
                con = db_driver.connect(connection_string, detect_types=sqlite3.PARSE_DECLTYPES)  # sqlite3 only
            else:
                con = db_driver.connect(connection_string)
            cursor = con.cursor()
            self.driver = db_driver
            self.connection = con
            self.cursor = cursor
            if self.connection_string == ':memory:' :  #  sqlite3 only
                # demo objects
                cursor.execute("""
                    CREATE TABLE my_numbers (
                        -- assume rowid, integer, incrementing primary key
                        number integer PRIMARY KEY,
                        english string NOT NULL,
                        spanish varchar(10)
                    );
                """)
                cursor.execute("INSERT INTO my_numbers (number, english, spanish) VALUES (?, ?, ?)", (1, 'one', 'uno'))
                cursor.execute("INSERT INTO my_numbers (number, english, spanish) VALUES (?, ?, ?)", (2, 'two', 'dos'))
                cursor.execute("INSERT INTO my_numbers (number, english, spanish) VALUES (?, ?, ?)", (3, 'three', 'tres'))
                cursor.execute("INSERT INTO my_numbers (number, english, spanish) VALUES (?, ?, ?)", (4, 'four', 'cuatro'))
                cursor.execute("""
                    CREATE TABLE kitchen_sink (
                        -- assume rowid, integer, incrementing primary key
                        number integer PRIMARY KEY,
                        str string NOT NULL,
                        float float,
                        yes_no bool,
                        date date,
                        datetime timestamp
                    );
                """)
                cursor.execute("INSERT INTO kitchen_sink (number, str, float, yes_no, date, datetime) VALUES (?, ?, ?, ?, ?, ?)", (1, 'one', 1.234, True, '2000-01-01', '2000-01-01 00:00:00'))
                cursor.execute("INSERT INTO kitchen_sink (number, str, float, yes_no, date, datetime) VALUES (?, ?, ?, ?, ?, ?)", (2, 'two', 2.987, False, '2000-12-25', '2000-12-25 11:12:13'))
                con.commit()

    def table_list(self):
        # Assume single schema/current user with unqualified object names
        # TODO make this an attribute?
        if not self.is_open():
            raise NotImplementedError('Database is not open')
        if self.driver != sqlite3:
            raise NotImplementedError('non-SQLlite3 database %r' % self.driver)
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")  # ORDER BY?
        # alternatively https://www.sqlite.org/pragma.html#pragma_table_list
        return self.cursor.fetchall()

    def column_type_list(self, table_name):
        # Assume single schema/current user with unqualified object names
        # TODO make this an attribute?
        if not self.is_open():
            raise NotImplementedError('Database is not open')
        if self.driver != sqlite3:
            raise NotImplementedError('non-SQLlite3 database %r' % self.driver)
            # options:
            # 1. select from table with no rows and check description (SQLite3 does not populate description with type information)
            #       sql = 'select * from "%s" LIMIT 1' % table_name  # LIMIT/TOP/FIRST/etc. where 1 != 1, etc.
            #       column_names = list(x[0] for x in cur.description)  # repeat for column type
            # 2. for pyodbc, query metadata interface
        else:
            # SQLite3 ONLY
            result = []
            meta = self.cursor.execute("PRAGMA table_info('%s')" % table_name)
            for row in meta:
                column_id, column_name, column_type, column_notnull, column_default_value, column_primary_key = row
                column_primary_key = bool(column_primary_key)
                column_type = sqlite_type_to_python(column_type)
                #print(row)
                #print((column_id, column_name, column_type, column_notnull, column_default_value, column_primary_key))
                result.append((column_name, column_type, column_notnull, column_default_value, column_primary_key))
            return result
            # Alternative idea, pull a row back and look at Python type, only works for non-NULL values and needs at least one row in table


def main(argv=None):
    if argv is None:
        argv = sys.argv

    try:
        connection_string = argv[1]  # dbname
    except IndexError:
        connection_string = ':memory:'

    try:
        table_name = argv[2]
    except IndexError:
        table_name = None

    print('db: %s' % connection_string)
    db = DatabaseWrapper(connection_string)
    db.do_connect()
    table_list = db.table_list()
    print('table_list %r' % table_list)

    table_name = table_name or table_list[0]

    column_type_list = db.column_type_list(table_name)
    print('column_type_list %r' % column_type_list)

    sql = None
    sql = sql or 'select * from "%s"' % table_name
    try:
        con = db.connection
        cur = db.cursor

        sql = 'select * from "%s" LIMIT 1' % table_name
        print('SQL: %r' % (sql,))
        cur.execute(sql)
        print('%r' % (cur.description,))
        column_names = list(x[0] for x in cur.description)
        print('%r' % column_names)
        print(cur.fetchall())

        if db.driver == sqlite3:
            sql = 'select rowid, * from "%s" LIMIT 1' % table_name
            sql = 'select rowid, * from "%s"' % table_name
            print('SQL: %r' % (sql,))
            cur.execute(sql)
            print('%r' % (cur.description,))
            column_names = list(x[0] for x in cur.description)
            print('%r' % column_names)
            print(cur.fetchall())

        cur.close()
        con.commit()
    finally:
        db.do_disconnect()


    return 0

if __name__ == "__main__":
    sys.exit(main())

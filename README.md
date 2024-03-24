-*- coding: utf-8 -*-

# SQLshite

🗄💩 A terrible SQLite Web UI

Not ready for general consumption, right now only browsing/viewing SQLite3 databases/tables is supported (and then barely).

Aim is a simple UI, that works on mobile for quick search.
Focused on single table work, rather than fk/pk relationship display. this is mostly implemented, without write (INSERT, DELETE, UPDATE) support (and with UI/UX blemishes). Use cases, less than 100k rows, that would have previously been suitable for use with tools like [Pilot-DB](https://pilot-db.sourceforge.net/), MobileDB, JFile, HanDBase, [Easy Database for Android](https://play.google.com/store/apps/details?id=com.dsiastur.easy_database), etc.

Primary aim:

  * no security - did you pay attention to the name of this project?
  * Simple SQL queries (TODO determine transaction model - autocommit is the current plan)
  * view/edit record, using [jsonschema](https://json-schema.org/) / jsonforms (unlike above where transaction model is unclear, autocommit on save)
	  * https://www.google.com/search?q=jsonform
	  * TODO research Python libs
          * https://github.com/RussellLuo/jsonform
          * https://github.com/python-jsonschema/jsonschema
	  * https://github.com/jsonform/jsonform/ -  Bootstrap 3 (end of support as of 2019, https://blog.getbootstrap.com/2019/07/24/lts-plan/#:~:text=Starting%20today%2C%20Bootstrap%203%20will,security%20updates%2C%20and%20documentation%20updates.) https://getbootstrap.com/docs/3.3/
		* https://jsonform.github.io/jsonform/playground/index.html
		* https://jsonform.github.io/jsonform/
	  * https://github.com/eclipsesource/jsonforms - React, Angular and/or Vue
		* https://jsonforms.io/examples/basic
		* https://jsonforms.io/
  * quick search, with add (either on no match or no good match) using search term as initial value
	  * searching either a defined column, the first column, or all columns

## Alternatives

Local

  * GUI https://github.com/sqlitebrowser/sqlitebrowser?tab=readme-ov-file#what-it-is
  * https://github.com/dbcli/litecli

Web

  * https://github.com/jeffknupp/sandman2
  * https://github.com/cs91chris/flask_autocrud
  * https://github.com/mathesar-foundation/mathesar (only one DBMS supported)

## Getting Started

### From a source code checkout

    python -m pip install -r requirements.txt
    # TODO requirements_optional.txt
    #python -m pip install -e .

#### Usage

	python -m sqlshite.web.wsgi
	python -m sqlshite.web.wsgi config.json

Where `config.json` contains:

	{
		"databases": {
			"memory": ":memory:",
			"mydb": "mydb.sqlite3"
		}
	}

Then open:

  * http://localhost:8777/d/
  * http://localhost:8777/d/memory/ - etc.


## Design

### URLs

That have been implemented

	http://localhost/ - browse databases
	http://localhost/d - browse databases

	http://localhost/d/DATABASE_NAME - browse tables
	http://localhost/d/DATABASE_NAME/sql - issue SQL queries
	http://localhost/d/DATABASE_NAME/rescan - rescan metadata

	http://localhost/d/DATABASE_NAME/TABLE_NAME?q=SEARCH_TERM - quick search the first string column with automatic (pre and post) wild card

	http://localhost/d/DATABASE_NAME/TABLE_NAME/jsonform.json - schema in jsonform - format
	http://localhost/d/DATABASE_NAME/TABLE_NAME/rows - view (TODO cleanup and maybe edit for desktop view) rows in table
	http://localhost/d/DATABASE_NAME/TABLE_NAME/add - add TODO actually INSERT into table
	http://localhost/d/DATABASE_NAME/TABLE_NAME/rowid - currently dumps schema and value
	http://localhost/d/DATABASE_NAME/TABLE_NAME/view/rowid - view
	http://localhost/d/DATABASE_NAME/TABLE_NAME/view/rowid/view.json - jsonform with schema and data only

#### URLs TODO / TBD

	http://localhost/d/DATABASE_NAME/TABLE_NAME - browse table (rows)?

TBD

	http://localhost/d/DATABASE_NAME/TABLE_NAME/schema.json - schema in jsonform - format

	http://localhost/d/DATABASE_NAME/TABLE_NAME?rowid=A - view? where rowid is sqlite specific rowid?

    Where PRIMARY_KEY is not rowid (but it could be...)
	http://localhost/d/DATABASE_NAME/TABLE_NAME/PRIMARY_KEY - edit/view?
	http://localhost/d/DATABASE_NAME/TABLE_NAME/row/PRIMARY_KEY - view?
	http://localhost/d/DATABASE_NAME/TABLE_NAME/view/PRIMARY_KEY - view?

	http://localhost/d/DATABASE_NAME/TABLE_NAME/edit/PRIMARY_KEY - edit existing?
 need to use hidden field for PK (compound pk?) in case pk is updated. Potentially use readonly (especially for view)
	http://localhost/d/DATABASE_NAME/TABLE_NAME/edit/PRIMARY_KEY/jsonform.json - schema+data in jsonform - format with data


## Questions

  * Datatype support. date/datetime
  * how to handle add and edit errors, to avoid data loss:
      * from database
      * network?
      * temp store in local storeage until get confirmation back?

### Datatypes

    SQL             Python
    TIMESTAMP       DateTime
    bool/boolean    bool
    varchar         string
    string          string
    int             integer
    real            float

TODO consider Decimal support.
TODO consider datetime as a mapping.

-*- coding: utf-8 -*-

# SQLshite

🗄💩 A terrible SQLite Web UI

Aim is a simple UI, that works on mobile for quick search.
Focused on single table work, rather than fk/pk relationship display.

Primary aim:

  * no security - did you pay attention to the name of this project?
  * Simple SQL queries (TODO determine transaction model)
  * view/edit record, using [jsonschema](https://json-schema.org/) / jsonforms (unlike above where transaction model is unclear, autocommit on save)
	  * https://www.google.com/search?q=jsonform
	  * TODO research Python libs
          * https://github.com/RussellLuo/jsonform
          * https://github.com/python-jsonschema/jsonschema
	  * https://github.com/jsonform/jsonform/ -  Bootstrap 3
		* https://jsonform.github.io/jsonform/playground/index.html
		* https://jsonform.github.io/jsonform/
	  * https://github.com/eclipsesource/jsonforms - React, Angular and/or Vue
		* https://jsonforms.io/examples/basic
		* https://jsonforms.io/
  * view records, using https://github.com/olifolkerd/tabulator
      * inputFor at array - https://tabulator.info/docs/5.5/data#import-data
  * quick search, with add (either on no match or no good match) using search term as initial value
	  * searching either a defined column, the first column, or all columns

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

  * http://localhost:8777/d/memory/


## Design

AKA TODO

### URLs

	http://localhost/ - browse databases
	http://localhost/d - browse databases

	http://localhost/d/DATABASE_NAME - browse tables
	http://localhost/d/DATABASE_NAME/sql - issue SQL queries

	http://localhost/d/DATABASE_NAME/TABLE_NAME - browse table (rows)?

TBD

	http://localhost/d/DATABASE_NAME/TABLE_NAME/schema.json - schema in jsonform - format
	http://localhost/d/DATABASE_NAME/TABLE_NAME/jsonform.json - schema in jsonform - format

	http://localhost/d/DATABASE_NAME/TABLE_NAME?rowid=A - view? where rowid is sqlite specific rowid?

    Where PRIMARY_KEY is not rowid (but it could be...)
	http://localhost/d/DATABASE_NAME/TABLE_NAME/PRIMARY_KEY - edit/view?
	http://localhost/d/DATABASE_NAME/TABLE_NAME/row/PRIMARY_KEY - view?
	http://localhost/d/DATABASE_NAME/TABLE_NAME/view/PRIMARY_KEY - view?
	http://localhost/d/DATABASE_NAME/TABLE_NAME/add/PRIMARY_KEY - add/edit?

	http://localhost/d/DATABASE_NAME/TABLE_NAME/edit/PRIMARY_KEY - edit existing?
 need to use hidden field for PK (compound pk?) in case pk is updated. Potentially use readonly (especially for view)
	http://localhost/d/DATABASE_NAME/TABLE_NAME/edit/PRIMARY_KEY/jsonform.json - schema+data in jsonform - format with data

	http://localhost/d/DATABASE_NAME/TABLE_NAME/rows - view (maybe edit for desktop view) rows in table

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

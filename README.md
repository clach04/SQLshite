-*- coding: utf-8 -*-

# SQLshite

🗄💩 A terrible SQLite Web UI

Aim is a simple UI, that works on mobile for quick search.
Focused on single table work, rather than fk/pk relationship display.

Primary aim:

  * no security - did you pay attention to the name of this project?
  * Simple SQL queries (TODO determine transaction model)
  * view/edit record, using jsonforms (unlike above where transaction model is unclear, autocommit on save)
	  * https://www.google.com/search?q=jsonform
	  * TODO research https://github.com/RussellLuo/jsonform
	  * https://github.com/jsonform/jsonform/ -  Bootstrap 3
		* https://jsonform.github.io/jsonform/
	  * https://github.com/eclipsesource/jsonforms - React, Angular and/or Vue
		* https://jsonforms.io/
  * view records, using https://github.com/olifolkerd/tabulator
  * quick search, with add (either on no match or no good match) using search term as initial value
	  * searching either a defined column, the first column, or all columns

## Design

AKA TODO

### URLs

	http://localhost/ - browse databases
	http://localhost/d - browse databases

	http://localhost/d/DATABASE_NAME - browse tables

	http://localhost/d/DATABASE_NAME/TABLE_NAME - browse table (rows)?

TBD

	http://localhost/d/DATABASE_NAME/TABLE_NAME/PRIMARY_KEY - edit/view?
	http://localhost/d/DATABASE_NAME/TABLE_NAME/row/PRIMARY_KEY - view?
	http://localhost/d/DATABASE_NAME/TABLE_NAME/view/PRIMARY_KEY - view?
	http://localhost/d/DATABASE_NAME/TABLE_NAME/edit/PRIMARY_KEY - edit?
	http://localhost/d/DATABASE_NAME/TABLE_NAME/rows - view (maybe edit for desktop view) rows in table

## Questions

  * Datatype support. date/datetime

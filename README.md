-*- coding: utf-8 -*-

# SQLshite

🗄💩 A terrible SQLite Web UI

Aim is a simple UI, that works on mobile for quick search.

Primary aim:

  * no security - did you pay attention to the name of this project?
  * Simple SQL queries (TODO determine transaction model)
  * view/edit record, using https://github.com/jsonform/jsonform/ (unlike above where transaction model is unclear, autocommit on save)
  * view records, using https://github.com/olifolkerd/tabulator
  * quick search, with add (either on no match or no good match) using search term as initial value
	  * searching either a defined column, the first column, or all columns

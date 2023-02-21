# ietf-info
Query various IETF RFC / Datatracker information and produce statistics

This is a rewrite of https://github.com/martinduke/count-rfcs

Example (default) output:

```
ietf-info.py -n 'Paul Wouters'

Authored: 12
Shepherded: 1
Responsible AD: 3
Balloted: 115
Acknowledged: 45

finished in 1731.615835428238
```

Using verbose will also list all matching RFCs

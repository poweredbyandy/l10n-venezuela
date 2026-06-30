This module extends the Venezuela SENIAT audit stack with:

* ORM audit rules for accounting and withholding models (via OCA auditlog).
* Login attempts, HTTP sessions, validation errors and report access logs.
* PostgreSQL triggers that record INSERT, UPDATE and DELETE operations executed
  outside Odoo (psql, pgAdmin, scripts, etc.) on critical tables.
* Fiscal document event logs on ``auditlog.log`` with human-readable descriptions
  for invoice creation, posting, fiscal printing, digital dispatch, retentions
  and cancellations.
* PDF report of fiscal document events.

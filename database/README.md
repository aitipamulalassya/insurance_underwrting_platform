# YottaFlex Database Submission

This folder contains the PostgreSQL schema baseline, consolidated schema migrations, and a database design explanation. See `database_design.md` before applying scripts.

- `schema.sql`: initial schema for a new/empty project database.
- `migrations.sql`: later structural changes; inspect the current database before applying.
- `database_design.md`: tables, relationships and design rationale.

**Important:** Do not run `schema.sql` against a populated database as a reset. These scripts do not include your database records. Keep a backup before applying schema changes to any important database.

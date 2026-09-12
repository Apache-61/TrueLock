# database/seeds/

**Purpose:** scripts/data to load `data/fixtures/` and `data/synthetic/`
scenarios into a fresh database for local dev and demo.

**What goes here:** idempotent loader scripts. `001_demo.sql` contains the
small canonical fixture used by local development and integration tests.
Running a seed twice should not duplicate data or error.

**What does not go here:** the fixture data itself (-> `data/fixtures/`,
`data/synthetic/`) -- this directory only loads it.

**Depends on:** all files in `database/migrations/`, `data/fixtures/`.

Run seeds in filename order after all migrations:

```bash
for seed in database/seeds/*.sql; do
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$seed"
done
```

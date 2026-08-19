# How We Work: Verification and Debugging

This file exists because of a specific, repeated failure. Eighteen separate times, a signal reported success while the thing it was supposed to be watching was broken. Every instance cost real time, and every instance looked fine right up until someone checked by hand.

These are not style preferences. Each rule below is here because ignoring it already cost us something.

---

## 1. The recurring pattern: a green signal measuring something adjacent

The failure mode is always the same shape. Something reports success. The report is accurate about what it measured. What it measured was not the thing that mattered.

Eighteen instances so far:

1. **Unregistered expiry sweep.** The sweep was written, tested, and correct. It was never registered with the scheduler, so it never ran. Nothing errored, because nothing happened.
2. **Anniversary job logging ERROR under a successful scheduler.** The scheduler reported healthy. The job inside it was failing every run. Scheduler health and job health are different measurements.
3. **Masked TypeScript compiler.** The build passed. The compiler was not actually checking the files anyone cared about.
4. **Alembic reporting `(head)` with newer migrations on git.** `alembic current` reported head. It was head of what the local machine knew about, not head of the branch. Files on disk are not files in git.
5. **A test asserting a bug as correct expected behavior.** The test passed for years. It encoded the bug as the expectation, so fixing the bug would have turned it red.
6. **The model registry guard test passing against a broken `__init__.py`.** The guard was written to catch unimported models. It passed even with the registry deliberately broken, because `conftest.py` imports `app.main`, which pulls the missing modules in transitively through routers and services. Alembic does not load the app. It imports `app.models` and nothing else. The test and the failure were looking at two different processes.
7. **The test database schema diverging from production.** Seventeen timestamp columns were declared as naive `DateTime()` in the models while the migrations created them as `timestamptz`. Because `conftest.py` builds the test database with `create_all()` from the models, the test suite ran against `TIMESTAMP WITHOUT TIME ZONE` while dev and production ran `WITH TIME ZONE`. Every test passed. Any timezone bug in the affected code would have been invisible to the suite by construction.
8. **A restore command reporting success after silently failing.** During a negative control, the command that was supposed to restore a mutated file failed on a bad path and printed "restored" anyway. The mutation was still in the file. It was caught only by grepping for the mutation marker instead of trusting the message. This one is a different flavor from the others: not a tool measuring the wrong thing, but a command reporting on an outcome it never checked. Verification steps are themselves subject to this rule. Confirm a restore by inspecting the file, not by reading the message.
9. **The billed-time-entry delete guard with no test at all.** During the guard-unification refactor (Aug 11), the pre-change sweep for the existing safety net found that the only DELETE test for time entries was the success case. The guard had existed in the service path since it was written, and no test had ever exercised the refusal. It happened to work, but nothing would have gone red if any change had ever broken it, including the refactor about to be performed on it. Caught only because the session checked for the safety net before assuming it. This is a different flavor again: instances one through eight are signals that reported wrongly. This one is the absence of a signal mistaken for the absence of a problem. Nothing was green, because nothing was watching, and those two states are indistinguishable until you go looking for the watcher.
10. **The only frontend test, unrunnable in a fresh checkout.** During the Phase 0 Item 3 frontend quick fixes (Aug 11), the verification step asked for existing frontend tests to be run. There is exactly one, `frontend/src/lib/concierge/assembleSSEStream.test.ts`, a regression test locking in the SSE reassembly fix so words can never silently glue together across line boundaries again. Its header documents the command to run it: `node --test --import tsx`. But `tsx` is not in `devDependencies` and is not in `node_modules`, and there is no `test` script in `package.json`, so the documented command fails with `ERR_MODULE_NOT_FOUND` on a clean checkout. Forced through with a temporary runner, all seven tests pass, so the test itself is correct. It has simply never been executable by anyone who did not already happen to have `tsx`. A regression test that cannot execute in a fresh checkout is a watcher nobody is watching. This is instance nine's flavor rather than instances one through eight: the absence of a signal mistaken for the absence of a problem. The bug it guards could have returned at any time and nothing would have gone red, because nothing was capable of running.
11. **A migration compiler silently discarding a `use_alter` foreign key.** During Build 1 Session 2 (Aug 13), the autogenerated migration for the pricing tables emitted the circular parent-tier foreign key inline inside `op.create_table` with `use_alter=True`. SQLAlchemy's `CreateTable` compiler silently omits `use_alter` foreign keys from the DDL it produces, and unlike `create_all()`, nothing in a migration ever emits the deferred `ALTER TABLE ADD CONSTRAINT` afterward. The migration would have run green, `alembic current` would have said head, and the database would have had no parent-tier foreign key while the model insisted one existed. Worse, because `conftest.py` builds the test database with `create_all()`, which does emit deferred `use_alter` constraints, the test database would have had the constraint while every migrated database did not: instance seven's two-worlds divergence, created by the migration path itself. Caught before it shipped, the first instance on this list to be. It was caught only because the claim was tested instead of trusted: the DDL was compiled directly and inspected, and the constraint was absent. The fix is an explicit, named `op.create_foreign_key` after both tables exist, verified against the live database catalog rather than the migration's exit status.

12. **A stale local test database, kept stale by its own broken reset.** During Build 1 Session 2 (Aug 13), immediately after pulling Ben's branch, three tests in `tests/test_sequence_version_pinning.py` failed with `UndefinedColumn: column "unsubscribe_token_hash" of relation "enrollments" does not exist`. The obvious readings were both wrong: the merge had not broken anything and the incoming migration was fine. The columns were missing from the local **test** database only, and the reason is that `conftest.py` builds it with `Base.metadata.create_all(bind=engine, checkfirst=True)`. `create_all` creates tables that are absent; it never alters tables that are present. A new column on an existing table is therefore invisible to the test database forever, no matter how many times the suite runs.

    What normally papers over this is the `drop_all` in `pytest_unconfigure`, which wipes everything at session end so the next run rebuilds from current models. That reset had itself been broken for an unknown length of time. `drop_all` emits `DROP CONSTRAINT` using the name the *model* declares, and the stale `sequences` table still carried `sequences_current_version_id_fkey`, the name Postgres auto-generated back when the constraint was anonymous. The drop errored, teardown aborted, the tables survived, and the next `create_all` skipped them. A stale database that prevents its own cleanup, indefinitely.

    The part worth internalizing is why nobody noticed for so long. Teardown had been failing loudly the whole time, and everyone knew: the session's own task file said "overall pytest exit code is unreliable due to the known unnamed `use_alter` FK issue on sequences; read the pass/fail counts, not the exit code." That instruction was accurate when written. But it trained every reader to discard the entire teardown signal, so when the teardown error quietly changed identity from `CompileError: it has no name` to `UndefinedObject: constraint ... does not exist`, the change went unread. A known-issue exemption had grown wide enough to hide a second, different failure standing behind the first. Blanket permission to ignore a signal is itself a signal that stops being watched, and the moment a known issue gets a standing exemption it needs a note saying exactly what it may excuse, so anything else showing up in the same place still gets read.

    Only new *tables* were unaffected, which is why the session's own nine pricing tables and twenty-six tests were green throughout and the harness looked healthy. It surfaced by accident, because a colleague's pull happened to add columns to a table that already existed. Any wrong column type, default, or nullability on any existing table would have been equally invisible for as long as the condition lasted. Fixed by dropping and recreating the `public` schema in the test database only, guarded on database name, production markers, and non-identity with dev. CI was never affected: it starts an empty container and builds the schema with `alembic upgrade head`, so it has no stale state to inherit, which is exactly why CI being green proved nothing about this.

    **The practical rule: when a suite run follows a pull that changed existing models, a stale local test database is a suspect before the code is.** Check whether the columns actually exist in the test database before debugging anything else. It is a two-second query and it will save an hour of reading a correct diff looking for a bug that is not in it.

13. **A migration chain that could not build from empty, behind a CI step nobody read.** During the public config endpoint session (Aug 14), the first attempt to run `alembic upgrade head` against a scratch database failed at revision `0051_add_metadata_to_concierge_notifications` with `DuplicateTable: relation "ix_concierge_notification_firm_is_read" already exists`. Revision `0038`, an ancestor, already creates an index by that exact name. So did `0051`, and the two had been colliding since June 10, 2026.

    Nobody noticed for two months because the collision is invisible to every database that was already past `0051` when it landed. Dev was past it. Production was past it. `alembic current` said head on both, correctly. The only environment that runs the chain from empty is CI, whose `Run migrations` step therefore failed on every push, which also means the test job behind it never ran. Section 5 of this file said, in as many words, that CI proves the migration chain executes. That sentence was the signal, and it had been false for two months while being quoted as reassurance.

    The lesson is not about index names. It is that a claim of the form "CI proves X" is only worth the last time somebody looked at CI. Alembic runs the whole upgrade in one transaction by default, so the failure also rolled back cleanly and left no trace behind: a scratch database with zero tables and no `alembic_version` row, which reads as "nothing happened" rather than "something broke". Fixed with `if_not_exists=True` on the `0051` create, verified by running the chain from empty through to head and reading the resulting catalog rather than the exit status.

14. **A uniqueness rule that no test could ever have exercised.** Found in the same session, while writing the guard test for `uq_enrollment_active_lead_sequence` that the session opener asked for. The partial unique index is created by migration `f2g3h4i5j6k7` and is not declared on the `Enrollment` model. `tests/conftest.py` builds the test database with `Base.metadata.create_all()`, which emits only what the models declare. So the index has never existed in any test run, on any machine, and the rule it enforces (a lead cannot be enrolled twice in the same sequence concurrently) is unenforced for the entire duration of every suite.

    A search for a test asserting that rule found none, which is the only reason this did not surface as instance five: there was no test encoding the wrong expectation, because there was no test. Had anyone written the obvious one, "insert two active enrollments, expect IntegrityError", it would have failed locally against a database with no constraint, and the natural reading would have been that the constraint was broken rather than absent from this environment only.

    This is instance seven's two-worlds divergence and instance nine's missing watcher in the same object. It is also why the guard written for it does not read the pytest database at all: it provisions a scratch database, runs the migration chain into it, and reads `pg_index` there, because that is the world the index lives in. A guard aimed at the ordinary test database would have been red on a healthy repo and could never have gone green.

15. Instance fifteen (Aug 16, 2026. Origin: `tests/test_phase13c_extensions.py::test_deadline_watch_uses_extended_deadline_after_filing`). **A test whose pass/fail tracks the wall clock rather than the behavior it names.** The test hardcoded a 60-day window against a fixed Oct 15, 2026 deadline and asserted the deadline fell outside it; the assumption expired on Aug 16, 2026, exactly 60 days out, and the test went red with no code change. It would have gone silently green again on Oct 15 with no fix. This is the mirror of the usual shape in this file: a false RED rather than a false green. A false red is not harmless. It lengthens the tolerated-failure list, and a long tolerated list teaches people to stop reading red, which is how false greens later walk through the door. Rule: a test asserting date arithmetic computes its expectations from the same clock the code under test reads, or pins the clock. Any test that can change color with no code change is broken, regardless of which color it currently shows.

16. Instance sixteen (Aug 17, 2026. Origin: the `complexity_flags` survivorship ruling verification). **A column that counted as populated while containing nothing.** Two read-only queries minutes apart appeared to contradict each other. A count reported `1 / 1 / 1`: one engagement row, one non-NULL `complexity_flags`, one blob that was neither NULL nor `{}`. A `SELECT` of the same column on the same row, run immediately afterward, printed `None`. Neither result was stale and nothing wrote to the database in between. They disagreed because one asked Postgres and the other asked Python.

    `jsonb` can store the JSON scalar `null`, and that is a *present* value, not an absent one. `IS NOT NULL` passes it, so `COUNT(complexity_flags)` counted it. `<> '{}'::jsonb` passes it too, because the scalar `null` is not the empty object, so the filter meant to say "has real content" counted it as content. And psycopg2 deserializes it to Python `None`, which is indistinguishable from what it hands back for a genuine SQL NULL. Every layer was individually correct and the composite measurement was false: on the same value, `jsonb_typeof` returned `'null'` while `IS NULL` returned false, and a predicate intended to mean "this engagement has complexity data" answered 1 for a table whose true answer was 0.

    The write-path explanation is inference, not observation, and is recorded as such: a bare `JSONB` column with no `none_as_null=True` persists an assigned Python `None` as JSON `null` rather than SQL NULL, per SQLAlchemy's documented default. It was not exercised, because exercising it would have meant writing.

    The rule: existence predicates on `jsonb` columns test `jsonb_typeof(col) = 'object'` (or whichever type the column is actually meant to hold) rather than a bare `IS NOT NULL`, and new JSONB columns declare `none_as_null=True` unless a stored JSON `null` is deliberately meaningful — in which case the deliberateness belongs in a comment on the column, so the next reader knows the ambiguity was chosen rather than inherited.

    This is the same failure family as the August 15 password-policy bug, one layer down. There, a key present in the settings blob with a null value defeated a `.get(key, {})` fallback that only fires when the key is absent. Here, a column present with a null value defeats an `IS NOT NULL` that only fires when the column is absent. Present-but-null is not absent, at either layer. Section 7 applies exactly: of the two disagreeing measurements, the reassuring one — the tidy `1 / 1 / 1` — was the broken one.

17. Instance seventeen (Aug 17, 2026. Origin: `tests/test_database_url_prefix.py`). **A negative control silently defeated by an override living in another file.** The session that added the `DATABASE_URL` prefix tripwire ran its negative control exactly as the task file prescribed: override `DATABASE_URL` in the shell with a plain `postgresql://` value, run pytest, watch the test go red. The test passed. `tests/conftest.py` calls `load_dotenv(".env.test", override=True)` before any app import, and `override=True` outranks a shell environment variable, so the injected value never reached the settings object the test reads. The control was not weak or badly aimed. It was structurally incapable of failing, and the recipe that produced it had been written down in advance and looked correct.

    Had that green been taken at face value, the session would have reported "control run, test went red" on the strength of a control that controlled nothing, and the tripwire would have shipped in exactly the condition it was written to prevent: possibly working, never demonstrated. The bypass that did reach the settings object was `--noconftest`, which stops the dotenv override from loading at all. Under it the test failed on the scheme assertion, at the right line, for the right reason.

    The rule: watching a control go red is not the last step, because a control can also fail to fail. Confirm that the control actually reaches the thing it tests, since the override defeating it can live in a file nobody is looking at, loaded before the code under test ever runs. Section 2 says a guard is not finished until you have watched it fail. This instance adds that a guard is not finished until you have also confirmed that what you did to make it fail is what actually made it fail. Kin to instance six, where the check and the failure ran in two different processes, and to the Aug 15 sweep-gate rewrite, where a test was structurally incapable of catching the failure it existed for.

18. Instance eighteen (Aug 18, 2026. Origin: `tests/test_intake_pricing_config.py`, the scope-awareness guards written for the public intake config rework). **A negative control defeated by the fixture rather than by the assertion.** Two new tests existed to prove that one engagement type's pricing override is never asked on another engagement type: one for a scoped override crossing to a sibling service, one for an override attached to a *dormant* service reaching the active ones. Both were written, both passed, and both were then run against a deliberate reintroduction of the exact defect they described. **Both stayed green.**

    The assertions were correct and were aimed at the right value. The fixtures could not produce the failure. Each seeded the leaked question on a complexity flag that the system catalog mapped to only ONE of the two engagement types involved, so when the break dutifully pushed that question into the other service's list, an entirely separate and entirely legitimate filter, the flag-applicability check, dropped it one line later. The observable result was identical to correct behavior. A test that says "X must not appear on service B" proves nothing when X could never have appeared on service B under any implementation, and nothing about reading the test reveals that: the assertion, the fixture, and the break all look right individually, and the thing that defeats them is a rule living in a different table.

    This is instance seventeen's shape moved one layer out. There the control was defeated by an override in another file loaded before the code under test; here it is defeated by catalog data that makes the leak unexpressible. Seventeen's rule was to confirm that what you did to make the test fail is what actually made it fail. Eighteen adds the case where nothing you do to the CODE can make it fail, because the SETUP forbids the outcome. Both fixtures were fixed by mapping a shared flag to both engagement types, so the two entities genuinely share the linking record the leak would have to travel along, and both controls then went red naming the right question. The repaired fixtures carry a comment saying that mapping is load-bearing, because it reads like incidental seed data and deleting it would silently restore the vacuum.

    The generalisable rule: **a test that asserts a cross-entity leak cannot exist must seed a world where that leak is possible.** The two entities have to share whatever record links them, or the test is asserting the absence of something that was never on offer. When a control comes back green, the fixture is a suspect before the test is, and before the code is: check that the failure you are trying to observe is reachable at all from the data you set up, and check specifically for a second, unrelated filter that would discard the leaked row for its own good reasons. Section 2's rule is that a guard is not finished until you have watched it fail. Seventeen added that you must confirm what made it fail. Eighteen adds that if it will not fail, the first question is whether it *could*.

Instances seven, nine, ten, eleven, and fourteen are the purest forms of the pattern. The others are things that failed. Those five never failed. They made a category of failure unobservable, which is worse, because there was nothing to notice. Twelve belongs with them in substance even though it did eventually go red: the divergence it created was unobservable by construction and surfaced only by luck, and it would have kept hiding schema faults for as long as nobody happened to add a column to an existing table. Thirteen sits at the other end: it failed loudly, on every push, for two months, into a report nobody opened. Eighteen belongs with the purest five as well, and is the most uncomfortable of them, because the guard was written correctly, aimed correctly, and put through the negative control this file mandates. Every step was followed and the result was still a test that could not fail. It was caught only because the control was run and its green was disbelieved.

When you find a nineteenth, add it here with its origin. The list is the point. Recognizing the shape early is worth more than any individual rule below.

---

## 2. A guard test is not finished until you have watched it fail

Write the test. Then deliberately break the thing it guards. Confirm it goes red. Then restore.

A test that has only ever been observed passing is not evidence of anything. It might be catching the failure. It might be structurally incapable of catching it. Those two states look identical from the outside, and the only way to tell them apart is the negative control.

This is how instance six was caught. The guard test passed against a deliberately broken registry, which revealed it was measuring the wrong process entirely. Without the negative control it would have shipped green and useless.

Run one control per load-bearing assertion, not one for the file. A suite can have ten passing tests where nine of them survive the defect that matters. When a batch of tests covers one rule, find the defect that only one of them catches, and confirm that one specifically.

**The restore step is not complete until two checks pass:**

1. Re-run the test and confirm it is green again. Red-then-restore without a final green run leaves open the possibility that the restore changed the wrong thing, or that the break and the fix crossed somewhere unexpected.
2. Run `git status` or `git diff` on every file touched during the control and confirm the working tree matches git. A restore command exiting cleanly proves nothing on its own. See instance 8, where the command printed "restored" over a file that still contained the mutation.

Inspect outcomes, not messages. The restore command's own report is exactly the kind of green signal this file exists to distrust.

Applies to guard tests, assertions, alerts, monitors, and any check whose job is to notice a problem.

---

## 3. Reproduce the failure in the same conditions the failure happens in

Instance six failed because the test ran inside pytest, where `conftest.py` had already loaded the whole application. The real failure happens inside Alembic, which loads almost nothing.

Before trusting a check, ask what environment the real failure occurs in, and whether the check runs in that environment. If it does not, the check is measuring a different world.

The fix in that case was to run `import app.models` in a clean subprocess and compare against the fully loaded process. Isolation was the entire point of the test.

A related trap: a test asserting that nothing was created should read the database directly rather than call an endpoint. An endpoint's own filtering can hide the row the test was supposed to catch.

---

## 4. Claude Code's "verified" claims require an empirical check

Claude Code will report work as verified and complete. Sometimes it is. The claim is a hypothesis, not a result.

Ask for the actual command output rather than the summary. Run the check yourself when it is cheap. Where a claim is load-bearing for the next phase, confirm it before starting the next phase, not after.

This is not distrust of the tool. It is that a model reporting on its own work has no independent view of whether the work happened, in the same way the scheduler in instance two had no view into the job it was running.

---

## 5. Alembic verification

`alembic heads` is not `alembic current`. Heads shows every tip revision the local machine knows about. Current shows what is actually applied to the connected database. They disagree in exactly the situations that matter most.

Before considering any migration complete:

- Read the generated migration file in full. If it contains anything beyond what you just added, delete it and write a clean manual migration.
- Run `alembic current` before and after, not just after.
- Confirm the migration file is committed to git. `alembic upgrade head` reads files on disk, not git. A migration applied locally but never committed means the local database is at a revision no other machine has, and nothing will tell you.
- A `use_alter=True` foreign key can never be created inline in `op.create_table`. The CREATE TABLE compiler silently drops it and no deferred ALTER follows in a migration context, so the constraint will not exist even though the migration runs green (instance eleven). Create it with an explicit, named `op.create_foreign_key` after both tables exist, drop it explicitly first in `downgrade()` to break the circle, and confirm it landed by querying the live database catalog, not by the migration's exit status.

Autogenerate only sees models that are imported. `app/models/__init__.py` discovers its own modules automatically, and `migrations/env.py` imports that package, so adding a model file is sufficient to register it. If that ever changes, the tests in `tests/test_model_registry.py` are the tripwire.

CI runs `alembic upgrade head` against an empty Postgres database on every push. That job proves the migration chain executes, but only if somebody reads it: it had been failing on every push since June 10, 2026 and nobody noticed until August 14 (instance thirteen). It does not prove the chain produces the schema the models describe, which is a separate comparison worth adding.

The chain-from-empty check is cheap enough to run locally and does not need CI's cooperation. Create a scratch database, point `DATABASE_URL` at it, run `alembic upgrade head`, and read the resulting catalog. The whole chain takes about five seconds. `tests/test_enrollment_active_index_guard.py` does exactly this and is the working example to copy.

---

## 6. Stop-and-report gates between phases

Multi-part work runs one part at a time with a full stop between them. Report state, confirm it, then continue.

The reason is compounding. If part one produced something subtly wrong and part two builds on it, the error is now inside two layers of work instead of one, and the report at the end covers both. Gates keep the blast radius equal to one part.

Never chain parts to save a round trip.

---

## 7. When a signal and reality disagree, distrust the signal first

The instinct is to explain why the surprising observation must be wrong. Resist it. In every instance above, the surprising observation was correct and the reassuring signal was the broken thing.

If something reports healthy while behaving unhealthily, the reporting is the first suspect.

---

## 8. Read the code before recommending a change to it

Roadmap documents, design references, and prior session notes go stale. The repository is the only current description of the repository.

This applies to comments too. A comment asserting something the code no longer does is worse than no comment, because the next person will trust it. When behavior changes, the comments describing that behavior change in the same commit.

---

## 9. When a rule changes on purpose, update the tests that encoded the old one

Instance five is a test that encoded a bug as the expectation. The mirror image is a test that correctly encoded a rule which has since been deliberately replaced.

Both look the same from the terminal: a red test after a change. The difference is whether the behavior changed on purpose. When it did, update the test to the new expectation, rename it if the name asserts the old rule, and say in the docstring what changed and why. A test named `..._is_refused` that now asserts success is its own small piece of misinformation.

---

## 10. Before refactoring guarded behavior, find the test that pins it

A refactor's correctness proof is that existing tests pass unmodified. That proof is only as good as the tests existing. Before restructuring anything whose behavior must not change, locate the specific test that pins each externally visible behavior: status codes, messages, side effects. Do not assume coverage; find the test by name.

If no pinning test exists, write it against the old code first and watch it pass before touching anything. The order is the whole point. A pinning test written before the refactor records what the code did. The same test written after the refactor records what the new code does, and proves only that the new code agrees with itself.

This is instance nine's rule. The refactor that surfaced it would otherwise have carried an unwatched guard across a restructuring with no way to notice if it dropped.
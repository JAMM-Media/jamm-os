# How We Work: Verification and Debugging

This file exists because of a specific, repeated failure. Eleven separate times, a signal reported success while the thing it was supposed to be watching was broken. Every instance cost real time, and every instance looked fine right up until someone checked by hand.

These are not style preferences. Each rule below is here because ignoring it already cost us something.

---

## 1. The recurring pattern: a green signal measuring something adjacent

The failure mode is always the same shape. Something reports success. The report is accurate about what it measured. What it measured was not the thing that mattered.

Eleven instances so far:

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

Instances seven, nine, ten, and eleven are the purest forms of the pattern. The others are things that failed. Those four never failed. They made a category of failure unobservable, which is worse, because there was nothing to notice.

When you find a twelfth, add it here with its origin. The list is the point. Recognizing the shape early is worth more than any individual rule below.

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

CI runs `alembic upgrade head` against an empty Postgres database on every push. That job proves the migration chain executes. It does not yet prove the chain produces the schema the models describe, which is a separate comparison worth adding.

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
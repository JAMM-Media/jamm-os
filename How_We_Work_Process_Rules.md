# How We Work: Verification and Debugging

This file exists because of a specific, repeated failure. Seven separate times, a signal reported success while the thing it was supposed to be watching was broken. Every instance cost real time, and every instance looked fine right up until someone checked by hand.

These are not style preferences. Each rule below is here because ignoring it already cost us something.

---

## 1. The recurring pattern: a green signal measuring something adjacent

The failure mode is always the same shape. Something reports success. The report is accurate about what it measured. What it measured was not the thing that mattered.

Seven instances so far:

1. **Unregistered expiry sweep.** The sweep was written, tested, and correct. It was never registered with the scheduler, so it never ran. Nothing errored, because nothing happened.
2. **Anniversary job logging ERROR under a successful scheduler.** The scheduler reported healthy. The job inside it was failing every run. Scheduler health and job health are different measurements.
3. **Masked TypeScript compiler.** The build passed. The compiler was not actually checking the files anyone cared about.
4. **Alembic reporting `(head)` with newer migrations on git.** `alembic current` reported head. It was head of what the local machine knew about, not head of the branch. Files on disk are not files in git.
5. **A test asserting a bug as correct expected behavior.** The test passed for years. It encoded the bug as the expectation, so fixing the bug would have turned it red.
6. **The model registry guard test passing against a broken `__init__.py`.** The guard was written to catch unimported models. It passed even with the registry deliberately broken, because `conftest.py` imports `app.main`, which pulls the missing modules in transitively through routers and services. Alembic does not load the app. It imports `app.models` and nothing else. The test and the failure were looking at two different processes.
7. **The test database schema diverging from production.** Seventeen timestamp columns were declared as naive `DateTime()` in the models while the migrations created them as `timestamptz`. Because `conftest.py` builds the test database with `create_all()` from the models, the test suite ran against `TIMESTAMP WITHOUT TIME ZONE` while dev and production ran `WITH TIME ZONE`. Every test passed. Any timezone bug in the affected code would have been invisible to the suite by construction.

Instance seven is the purest form of the pattern. The others are things that failed. That one never failed. It made an entire category of failure unobservable, which is worse, because there was nothing to notice.

When you find an eighth, add it here with its origin. The list is the point. Recognizing the shape early is worth more than any individual rule below.

---

## 2. A guard test is not finished until you have watched it fail

Write the test. Then deliberately break the thing it guards. Confirm it goes red. Then restore.

A test that has only ever been observed passing is not evidence of anything. It might be catching the failure. It might be structurally incapable of catching it. Those two states look identical from the outside, and the only way to tell them apart is the negative control.

This is how instance six was caught. The guard test passed against a deliberately broken registry, which revealed it was measuring the wrong process entirely. Without the negative control it would have shipped green and useless.

Applies to guard tests, assertions, alerts, monitors, and any check whose job is to notice a problem.

---

## 3. Reproduce the failure in the same conditions the failure happens in

Instance six failed because the test ran inside pytest, where `conftest.py` had already loaded the whole application. The real failure happens inside Alembic, which loads almost nothing.

Before trusting a check, ask what environment the real failure occurs in, and whether the check runs in that environment. If it does not, the check is measuring a different world.

The fix in that case was to run `import app.models` in a clean subprocess and compare against the fully loaded process. Isolation was the entire point of the test.

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
# tests/test_database_url_prefix.py

"""
Tripwire: the configured DATABASE_URL must carry the postgresql+psycopg:// prefix.

WHY THIS TEST EXISTS
--------------------
SQLAlchemy picks its driver from the URL prefix, not from which packages are
importable. "postgresql+psycopg://" selects psycopg 3. Plain "postgresql://"
silently selects psycopg2, whenever psycopg2 happens to be installed.

The failure that follows is silent, which is the whole problem. psycopg2
exceptions carry .pgcode; psycopg 3 exceptions carry .sqlstate. Neither driver
has the other's attribute. So a guard written as

    getattr(exc.orig, "sqlstate", None) == "23505"

never fires under psycopg2, and the psycopg2-shaped equivalent never fires
under psycopg 3. The guard does not error. It does not warn. It evaluates to
False forever and the branch it protects becomes unreachable, so a duplicate-key
refusal that should be a 409 arrives as a 500 instead. Nothing in the running
system announces which driver it is on.

Origin: the Aug 15-17 driver dispute, in which two developers on the same repo
observed opposite driver behavior. Neither environment was exotic. They differed
by one string. psycopg2 was installed in BOTH environments, so "is psycopg2
installed" was never the discriminating question and checking it led nowhere for
two days. The prefix was the entire mechanism, and no test was watching it.

CI cannot catch this. psycopg2 is absent from the CI image, so a wrong prefix
there dies loudly at create_engine with ModuleNotFoundError. On a developer
machine with psycopg2 present it degrades silently instead. CI being green has
never been evidence about this failure and never will be.

WHY THESE ASSERTIONS COMPARE THE SCHEME INSTEAD OF CALLING startswith()
----------------------------------------------------------------------
A failing assertion prints its operands. DATABASE_URL contains live database
credentials, and pytest output ends up in terminals, logs, and CI transcripts.
Splitting the scheme off first means a failure can only ever print the part
before "://", never the credentials after it. The assertion is equivalent to
startswith("postgresql+psycopg://"): scheme equality plus a present separator.
"""

from pathlib import Path

from dotenv import dotenv_values

from app.core.config import get_settings

REQUIRED_SCHEME = "postgresql+psycopg"

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def _split_scheme(url: str) -> tuple[str, str]:
    """Return (scheme, separator). Never returns the credential-bearing tail."""
    scheme, separator, _ = url.partition("://")
    return scheme, separator


def test_configured_database_url_uses_psycopg3_prefix():
    """
    The URL the application actually builds its engine from must select psycopg 3.

    This reads app.core.config.get_settings(), which is the same object
    app/db/session.py hands to create_engine(), rather than re-reading a .env
    file. Reading the settings object is the point: it resolves shell
    environment, .env.local, and .env in the same precedence order the running
    application does, so this asserts against the URL the app will really use.
    """
    url = get_settings().DATABASE_URL or ""
    scheme, separator = _split_scheme(url)

    assert separator == "://", (
        "Configured DATABASE_URL has no scheme separator. It is malformed, not "
        "merely wrong-prefixed. Value withheld: it carries credentials."
    )
    assert scheme == REQUIRED_SCHEME, (
        f"Configured DATABASE_URL selects the wrong driver. Expected scheme "
        f"{REQUIRED_SCHEME!r} (psycopg 3), found {scheme!r}. A plain "
        f"'postgresql' scheme silently selects psycopg2, whose exceptions carry "
        f".pgcode instead of .sqlstate, which makes every sqlstate error-code "
        f"guard in this codebase dead on arrival. Fix the DATABASE_URL prefix "
        f"in your .env rather than changing this test."
    )


def test_env_example_template_uses_psycopg3_prefix():
    """
    The onboarding template must not hand a new developer a psycopg2 URL.

    .env.example is the only env file tracked in git (.env, .env.docker, and
    .env.test are all gitignored), and README.md tells a new developer to copy
    it. So it is the single tracked artifact capable of seeding a wrong prefix
    across every future environment, and the test above cannot catch it: that
    one reads resolved settings, and nobody's resolved settings come from
    .env.example. This assertion is the one that watches the template itself.
    """
    assert ENV_EXAMPLE.is_file(), (
        f"{ENV_EXAMPLE.name} is missing from the repository root. It is the "
        f"onboarding template referenced by README.md and is tracked in git."
    )

    template_url = (dotenv_values(ENV_EXAMPLE) or {}).get("DATABASE_URL") or ""
    assert template_url, (
        f"{ENV_EXAMPLE.name} defines no DATABASE_URL. A developer copying it "
        f"gets a config that cannot start, or worse, silently inherits an "
        f"ambient one."
    )

    scheme, separator = _split_scheme(template_url)

    assert separator == "://", (
        f"DATABASE_URL in {ENV_EXAMPLE.name} has no scheme separator."
    )
    assert scheme == REQUIRED_SCHEME, (
        f"DATABASE_URL in {ENV_EXAMPLE.name} would seed a psycopg2 environment. "
        f"Expected scheme {REQUIRED_SCHEME!r}, found {scheme!r}. Every developer "
        f"who copies this template inherits the wrong driver, and the resulting "
        f"breakage is silent."
    )

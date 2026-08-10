# app/models/__init__.py

"""SQLAlchemy model registry.

Discovery is automatic. Every module in this package is imported when the
package is imported, and every model class those modules define is bound into
this namespace. Adding a model file is the only step required to register its
tables with Base.metadata, which is what Alembic autogenerate compares the
database against. There is no hand-maintained import list left to forget.

Import order is irrelevant. Every relationship in this codebase is declared
with a string name, so no model ever needs to see another model's class object
at the moment it is defined.

Both directions of this are covered by tests/test_model_registry.py.
"""

import importlib
import pkgutil

from app.db.base_class import Base

__all__: list[str] = []


def _discover_models() -> None:
    """Import every sibling module and re-export the model classes it owns.

    Binding the classes into the package namespace is what keeps
    `from app.models import Firm` and `app.models.Firm` working exactly as
    they did under the old hand-written import list.
    """
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name == "__init__":
            continue

        module = importlib.import_module(f"{__name__}.{module_info.name}")

        for attr_name, attr in vars(module).items():
            # __module__ filters out classes the module merely imported, so a
            # model is exported once, by the module that actually defines it.
            if (
                isinstance(attr, type)
                and issubclass(attr, Base)
                and attr is not Base
                and attr.__module__ == module.__name__
            ):
                globals()[attr_name] = attr
                __all__.append(attr_name)


_discover_models()

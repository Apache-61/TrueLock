"""Make the repository root importable for the test suite.

`orchestrator/` is a package imported as `orchestrator.workers.*`, but
the repository is not installed (there is no packaging step, by design --
a worker has to run from a fresh clone with nothing but Python 3). With
pytest's default import mode, the presence of this file at the root is
what puts the root on `sys.path`, so `import orchestrator` works whether
pytest is invoked from the root or from a subdirectory.

`scripts/` deliberately stays outside that: those are standalone tools,
not a package, and `tests/unit/test_task_cli.py` loads its subject via
importlib for exactly that reason.
"""

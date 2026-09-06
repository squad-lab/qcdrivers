# Hardware scripts

Interactive bring-up scripts, run cell by cell against real instruments. They
are **not** collected by pytest: they open hardware at hardcoded addresses and
have no assertions. `testpaths = ["tests"]` picks up this directory, but none of
these filenames match pytest's `test_*.py` / `*_test.py` patterns, so nothing
here is imported during a test run.

`notebooks/` holds the Jupyter equivalents, moved out of the package tree so
they are not shipped to users.

Keep automated tests in `tests/` itself.

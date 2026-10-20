# Code conventions

Rules every file in this project follows, so anyone can read the code and
know what each line does.

## Comments and documentation

- **Every module** starts with a docstring: what the file is for, and a short example.
- **Every function and class** has a docstring: what it does, its parameters,
  what it returns, and an example where useful (NumPy docstring style).
- **Inside functions**, a plain-English comment explains each step, and in
  particular *why* it is done. Scientific steps name their method and give the
  reference (paper or standard) in the docstring.
- Comments are written for a scientist who knows Python basics, not for a
  software engineer. Python tricks get a one-line explanation where they appear.
- **Tests** have a docstring saying what behaviour they protect, and a comment
  on each check.

## Code

- Processing never changes data in place; it returns a new object and records
  the step in `history`.
- Errors say what was wrong and how to fix it.
- Every scientific algorithm is tested against a trusted reference (SciPy,
  pybaselines) or a published example, with the tolerance stated.
- Type hints on every function, so editors (VS Code) can show what goes in and out.

## Changes

- One feature per git branch; merge after tests pass and the feature is approved.
- Every merged change gets a line in `CHANGELOG.md`.
- New dependencies are agreed first and documented in `dependencies.md`.

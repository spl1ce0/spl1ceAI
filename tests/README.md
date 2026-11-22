# Tests (`tests/`)

Automated unit tests using Python's built-in `unittest` module.

## Files

* **`test_idea.py`**: Covers title/body formatting, GitHub REST API issue & label handling (`cogs/utils/github.py`), owner-only gating and replies for `/idea` (`cogs/dev.py`), and `ErrorHandler` integration (`cogs/errors.py`) with mocked HTTP calls.

## Running

```bash
python3 -m unittest discover -s tests -v
```

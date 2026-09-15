import glob
import importlib.util
import os


spec = importlib.util.spec_from_file_location(
    "check_code_health", os.path.join(os.path.dirname(__file__), "..", "scripts", "check_code_health.py")
)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
check_file = module.check_file


def test_tldrgraph_code_health():
    """Ensures all source files in tldrgraph adhere to the <= 400 lines limit."""
    files = sorted(glob.glob("tldrgraph/**/*.py", recursive=True))
    all_file_errors = []
    for filepath in files:
        f_errs, _ = check_file(filepath, max_file_lines=400)
        all_file_errors.extend(f_errs)
    assert not all_file_errors, "\n".join(all_file_errors)

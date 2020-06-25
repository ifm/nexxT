from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

def test_BasicWorkflow():
    with tempfile.TemporaryDirectory() as d:
        shutil.copy(Path(__file__).parent / "basicworkflow_script.py", d)
        shutil.copytree(Path(__file__).parent.parent / "binary", Path(d) / "binary")
        shutil.copy(Path(__file__).parent.parent / "interface" / "SimpleStaticFilter.py", d)

        try:
            p = subprocess.run(
                [sys.executable, "-m", "nexxT.core.AppConsole", "--gui", "false", "-s", "basicworkflow_script.py"],
                cwd=d, capture_output=True, timeout=150., encoding="utf-8")
            #p = subprocess.run([sys.executable, Path(sys.executable).parent / "nexxT-gui", "-h"], capture_output=True, encoding="utf-8")
            timeout = False
        except subprocess.TimeoutExpired as e:
            p = e
            timeout = True
        print("STDOUT", p.stdout)
        print("STDERR", p.stderr)
        assert not timeout
        p.check_returncode()



if __name__ == "__main__":
    test_BasicWorkflow()

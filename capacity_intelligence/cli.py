import subprocess
import sys
from importlib.resources import files


def main():
    app_path = str(files("capacity_intelligence").joinpath("app.py"))
    sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", app_path]))

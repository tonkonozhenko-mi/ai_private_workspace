from pathlib import Path
import sys


backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

import sys
from pathlib import Path

# permite importar os pacotes de src/ (farmtech_core, fase1_..., fase7_...)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

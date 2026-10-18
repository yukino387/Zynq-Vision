import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("output", type=Path)
args = parser.parse_args()
commands = json.loads((Path(__file__).resolve().parents[1] / "training/graph.json").read_text())["commands"]
assert len(commands) == 33 and all(len(row) == 10 for row in commands)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text("#pragma once\nstatic const int model_commands[33][10] = {\n" + ",\n".join("{" + ",".join(map(str, row)) + "}" for row in commands) + "\n};\n")

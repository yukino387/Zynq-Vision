"""Package and validate gray/RGB weights for the fixed PL graph and SD/UDP loader."""
import argparse
import hashlib
import json
from pathlib import Path

from training.pl_model import package_model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', type=Path, default=Path(__file__).parent / 'int8/weights.bin')
    parser.add_argument('--metadata', type=Path, default=Path(__file__).parent / 'int8/metadata.bin')
    parser.add_argument('--channels', type=int, choices=(1, 3), default=1)
    parser.add_argument('--version')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    weights, metadata = args.weights.read_bytes(), args.metadata.read_bytes()
    version = args.version or ('INT8-' + hashlib.sha256(weights + metadata).hexdigest()[:16])
    try:
        package, manifest = package_model(weights, metadata, version, args.channels)
    except (ValueError, UnicodeError) as error:
        parser.error(str(error))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'model.bin').write_bytes(package)
    (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'version': version, 'bytes': len(package), 'sha256': manifest['weights']['sha256'], 'payloadSha256': package[88:120].hex()}))


if __name__ == '__main__':
    main()

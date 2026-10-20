"""Processo confiável para operações de preparo; aguarda associação ao Job."""
import json
import sys


def main():
    if sys.stdin.buffer.readline(16) != b'NEXO-GO\n':
        raise SystemExit(3)
    request = json.loads(sys.stdin.buffer.readline(4 * 1024**2))
    sys.path[:0] = request['imports']
    from pathlib import Path
    from nexo.workspace import Workspace
    workspace = Workspace(Path(request['source']), Path(request['home']), request['id'])
    if request['operation'] == 'prepare':
        result = workspace.prepare()
    else:
        raise ValueError('Operação não registrada')
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

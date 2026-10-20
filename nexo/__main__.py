import argparse
from pathlib import Path

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="NEXO local — http://127.0.0.1:8765")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--project", type=Path, help="Diretório explicitamente autorizado para esta sessão")
    parser.add_argument("--data-dir", type=Path, help="Banco e artefatos deste projeto")
    args = parser.parse_args()
    from .api import create_app
    uvicorn.run(create_app(project_dir=args.project, data_dir=args.data_dir), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()

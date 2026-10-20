"""Entrada confiável do executor: só carrega o projeto depois do sinal do pai."""
import compileall
import os
import subprocess
import sys
import unittest

CHECKS = {"python-tests", "python-check", "node-tests", "npm-build"}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in CHECKS:
        raise SystemExit(2)
    if sys.stdin.buffer.readline(16) != b"NEXO-GO\n":
        raise SystemExit(3)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    check = sys.argv[1]
    sys.path.insert(0, os.getcwd())
    if check == "python-tests":
        suite = unittest.defaultTestLoader.discover("tests")
        if suite.countTestCases() == 0:
            print("Nenhum teste encontrado; verificação recusada.", flush=True)
            return 2
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if check == "python-check":
        return 0 if compileall.compile_dir(os.getcwd(), quiet=1, maxlevels=8) else 1
    command = ["node", "--test", "--test-reporter=tap"] if check == "node-tests" else ["npm.cmd", "run", "build"]
    return subprocess.call(command, shell=False, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
                           creationflags=subprocess.CREATE_NO_WINDOW)


if __name__ == "__main__":
    raise SystemExit(main())

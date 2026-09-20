"""Retired generator: manually edited YAML is the translation source of truth.

The previous implementation remains available in Git history. It must not
regenerate localization from the obsolete draft/editorial JSON files.
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")
print("Build.py отключён: перевод редактируется непосредственно в localization/*.yml.")
print("Для проверки используйте tools/Test.py; сравнение и откат выполняются через Git.")
raise SystemExit(1)

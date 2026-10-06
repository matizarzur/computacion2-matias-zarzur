#!/usr/bin/env python3
"""Procesar texto usando pipeline de subprocess."""
import subprocess

texto = """
primera linea
segunda linea con error
tercera linea
otra linea con error
ultima linea
"""

echo = subprocess.Popen(["echo", texto], stdout=subprocess.PIPE)
grep = subprocess.Popen(["grep", "error"], stdin=echo.stdout, stdout=subprocess.PIPE)
wc = subprocess.Popen(["wc", "-l"], stdin=grep.stdout, stdout=subprocess.PIPE, text=True)

echo.stdout.close()
grep.stdout.close()

resultado, _ = wc.communicate()
print(f"Líneas con 'error': {resultado.strip()}")
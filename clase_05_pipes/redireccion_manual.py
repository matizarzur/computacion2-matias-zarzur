#!/usr/bin/env python3
"""Redirección manual de stdout."""
import os
import sys

print("Este mensaje va a la terminal")

stdout_original = os.dup(1)

archivo = os.open("/tmp/salida.txt", os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
os.dup2(archivo, 1)
os.close(archivo)

print("Este mensaje va al archivo")
print("Y este también")
sys.stdout.flush()

os.dup2(stdout_original, 1)
os.close(stdout_original)

print("Volvimos a la terminal")
print("Revisá el contenido de /tmp/salida.txt")
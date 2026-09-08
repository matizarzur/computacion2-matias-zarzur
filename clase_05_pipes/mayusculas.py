#!/usr/bin/env python3
"""Filtro que convierte a mayúsculas."""
import sys

for linea in sys.stdin:
    sys.stdout.write(linea.upper())
#!/usr/bin/env python3
"""Demostración de stdout vs stderr."""
import sys
import os

print("Mensaje normal a stdout")
sys.stdout.write("Otro mensaje a stdout\n")
os.write(1, b"Y otro mas directo al fd 1\n")

print("Mensaje de error a stderr", file=sys.stderr)
sys.stderr.write("Otro error a stderr\n")
os.write(2, b"Error directo al fd 2\n")
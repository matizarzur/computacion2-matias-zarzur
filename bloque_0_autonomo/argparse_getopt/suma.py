#!/usr/bin/env python3
"""
Suma todos los números pasados como argumentos.
Uso: suma.py <num1> <num2> ...
"""
import sys
suma=0
cnt_num=len(sys.argv)
for i in range(1,cnt_num):
    suma += float(sys.argv[i])

print (suma)
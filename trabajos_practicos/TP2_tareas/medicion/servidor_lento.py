#!/usr/bin/env python3
"""Servidor HTTP de prueba con demora controlable.

Sirve de destino para la tarea "descargar" en las mediciones: con URLs de
internet los tiempos dependen de la red y no se pueden reproducir.

    GET /demora/{segundos}   responde después de `segundos`, con TAMANO bytes
    GET /estado/{codigo}     responde de inmediato con ese código HTTP

Si el cliente corta la conexión antes de tiempo (por ejemplo, porque se
canceló la tarea), lo registra por consola: así se comprueba que la
cancelación cierra las conexiones de verdad.

Uso:
    python3 medicion/servidor_lento.py            # escucha en 127.0.0.1:8001
    HOST=0.0.0.0 PORT=8001 python3 medicion/servidor_lento.py
"""
import asyncio
import os
import time

import uvicorn
from fastapi import FastAPI, Request, Response

TAMANO = int(os.getenv('TAMANO', '1000'))

app = FastAPI(title='Servidor lento de prueba')


@app.get('/demora/{segundos}')
async def demora(segundos: float, request: Request) -> Response:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < segundos:
        if await request.is_disconnected():
            transcurrido = time.perf_counter() - t0
            print(f'cliente desconectado a los {transcurrido:.2f} s '
                  f'(pedía {segundos} s)', flush=True)
            return Response(status_code=499)
        await asyncio.sleep(0.02)
    return Response(content=b'x' * TAMANO,
                    media_type='application/octet-stream')


@app.get('/estado/{codigo}')
async def estado(codigo: int) -> Response:
    return Response(status_code=codigo)


if __name__ == '__main__':
    uvicorn.run(app, host=os.getenv('HOST', '127.0.0.1'),
                port=int(os.getenv('PORT', '8001')), log_level='warning')

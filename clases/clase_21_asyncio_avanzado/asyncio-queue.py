import asyncio

async def productor(cola, n):
    for i in range(n):
        await cola.put(f'tarea-{i}')          # await: puede esperar si está llena

async def procesar(tarea):
    await asyncio.sleep(0.05)
    print(f"{tarea} termino ok.")

async def worker(cola, wid):
    while True:
        tarea = await cola.get()              # await: espera si está vacía
        try:
            await procesar(tarea)
        finally:
            cola.task_done()                  # avisar que terminó

async def main():
    cola = asyncio.Queue(maxsize=5)
    workers = [asyncio.create_task(worker(cola, i)) for i in range(3)]

    await productor(cola, 12)
    await cola.join()                         # esperar a que no quede nada

    for w in workers:
        w.cancel()                            # los workers son bucles infinitos

if __name__ == '__main__':
    asyncio.run(main())
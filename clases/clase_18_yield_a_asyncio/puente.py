#!/usr/bin/env python3
"""La prueba de que async/await es azúcar sobre generadores.

No hay que creerlo: se puede verificar en el intérprete. Una corrutina
tiene .send() igual que un generador, y devuelve su resultado por
StopIteration.value — el mismo mecanismo que usó nuestro scheduler.

Uso:
    python3 puente.py
"""
import asyncio
import types


def separador(titulo):
    print(f"\n{'=' * 64}\n{titulo}\n{'=' * 64}")


def generador_suspendible():
    """Un generador que se suspende y recibe, como en el bloque 0."""
    recibido = yield 'me suspendo'
    print(f'  el generador recibió: {recibido!r}')
    return 'listo'


async def corrutina_simple():
    return 42


@types.coroutine
def esperar_algo():
    """El puente histórico: un generador usable con await.

    Así se escribía asyncio antes de Python 3.5, y es como la stdlib
    conecta las corrutinas con el event loop todavía hoy.
    """
    valor = yield 'suspendido desde el generador'
    return valor


async def usa_el_puente():
    resultado = await esperar_algo()       # await sobre un generador
    return f'la corrutina recibió: {resultado!r}'


def main():
    separador('1. Un generador se suspende, recibe y devuelve')
    g = generador_suspendible()
    print('  primer next():', next(g))
    try:
        g.send('hola')
    except StopIteration as e:
        print(f'  al terminar -> StopIteration con value={e.value!r}')

    separador('2. Una corrutina hace exactamente lo mismo')
    c = corrutina_simple()
    print('  tipo del objeto:', type(c).__name__)
    print('  ¿tiene .send()?', hasattr(c, 'send'))
    try:
        c.send(None)                        # arrancarla, como next()
    except StopIteration as e:
        print(f'  c.send(None) -> StopIteration con value={e.value}')
    print('  Es el MISMO mecanismo: suspender, reanudar, devolver por'
          ' StopIteration.')

    separador('3. await sobre un generador: el puente en vivo')
    co = usa_el_puente()
    subido = co.send(None)                  # arranca; el yield sube hasta acá
    print(f'  el yield de adentro llegó hasta afuera: {subido!r}')
    try:
        co.send('respuesta del loop')       # reanudar con un resultado
    except StopIteration as e:
        print(f'  {e.value}')
    print('\n  Eso es lo que hace el event loop: send() para arrancar,')
    print('  recibe el yield, y send(resultado) cuando lo tiene.')

    separador('4. Y con asyncio de verdad')
    print('  resultado:', asyncio.run(corrutina_simple()))
    print('  asyncio.run() hace todo lo anterior por vos.')


if __name__ == '__main__':
    main()

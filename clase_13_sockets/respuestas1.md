# Clase 13: Sockets TCP - Respuestas

## Ejercicio 1: Primer contacto

### 1.1 Cliente contra netcat

```
$ nc -l 8080          (servidor)
$ python3 cliente.py  (cliente: connect + sendall + recv)
```

1. Sí, `hola desde Python` apareció en la terminal de `nc`.

2. Escribiendo `respuesta manual del server` en el `nc` y presionando Enter, el cliente
   imprimió: `Recibido: b'respuesta manual del server\n'`. El `\n` viaja como un byte más:
   `nc` no lo saca, así que aparece tal cual en lo recibido.

3. Sacando el `recv()`, `nc` **no nota la diferencia**: el mensaje llega igual
   (`hola sin esperar respuesta`). Tiene sentido — el `recv()` es del lado del cliente, pasa
   *después* de que el `sendall()` ya entregó los datos al kernel. Sacarlo solo hace que el
   cliente no espere ni muestre la respuesta del otro lado.

### 1.2 Servidor contra netcat

```python
conn, dir = srv.accept()
```

4. Con `nc localhost 8080` de cliente, `dir` imprimió `('127.0.0.1', 34036)` — un `(IP,
   puerto)` de la cuádrupla de la clase 12: es el par (IP origen, puerto origen) del cliente,
   que junto con el (IP, puerto) donde escucha el servidor arman los cuatro valores que
   identifican la conversación.

5. Para que el servidor siga en vez de atender una sola conexión y terminar, hay que envolver
   el `accept()` en un `while True:`. Es exactamente lo que hace `echo_server.py`, y es el
   límite que retoma el ejercicio 6.

### 1.3 SO_REUSEADDR

6. Saqué la línea del `setsockopt`. Conecté con `nc`, corté el servidor con Ctrl+C y lo
   relancé enseguida:

   ```
   Traceback (most recent call last):
     File "servidor.py", line 4, in <module>
   OSError: [Errno 98] Address already in use
   ```

7. Con el error todavía activo, `ss -tan | grep 8080` mostró el puerto en `TIME-WAIT`:

   ```
   TIME-WAIT  127.0.0.1:8080   127.0.0.1:34036
   TIME-WAIT  127.0.0.1:59544  127.0.0.1:8080
   ```

   Ahí está la causa exacta: la conexión vieja sigue "ocupando" la dirección aunque ningún
   proceso la tenga abierta, porque el kernel la retiene para absorber paquetes rezagados.

8. Con la línea de vuelta, el `bind()` funciona sin problema aunque el `TIME-WAIT` siga ahí:
   `SO_REUSEADDR` le dice al kernel que igual permita el bind.

---

## Ejercicio 2: Entender recv()

### 2.1 Lecturas parciales

Con `echo_client.py --parcial` (pide de a 4 bytes un mensaje de 47):

```
recv(4) -> b'un m'
recv(4) -> b'ensa'
...
recv(4) -> b'es\n'
Total: 47 bytes de 47 enviados
```

1. Se ejecutó **12 veces** (`ceil(47/4)`), y no se perdió nada — los 47 bytes llegaron
   completos, solo que repartidos en pedazos de a lo sumo 4.

2. Con `recv(1)`: **48 llamadas** para 47 bytes (la última devuelve `b''`, la señal de
   cierre). Con `recv(65536)`: **2 llamadas** — la primera trae los 47 bytes de una, la
   segunda devuelve `b''`.

3. `recv(65536)` no devuelve necesariamente todo de una porque el argumento es un **tope
   máximo**, no una cantidad garantizada. Si en el momento en que se llama a `recv()` el
   kernel solo tiene, por ejemplo, los primeros 20 bytes disponibles en el buffer de
   recepción, eso es lo que devuelve — no espera a que lleguen los 65536.

### 2.2 La señal de cierre

4. Corriendo el snippet sin el chequeo de `b''` contra un servidor que cierra la conexión:
   el bucle **no lanza ninguna excepción, y gira para siempre**. Lo medí con un servidor que
   cierra apenas después de mandar `test\n`:

   ```
   1369787 llamadas a recv() en 2.5s sin el chequeo (todas devolviendo b'')
   ```

   Casi 1.4 millones de llamadas en 2.5 segundos, y el proceso quedó marcado `R` (running,
   no bloqueado) al **101% de CPU**:

   ```
   PID %CPU STAT CMD
   15962  101 R    python3 -
   ```

5. El chequeo que falta:

   ```python
   if not datos:
       break
   ```

6. Por qué consume 100% de CPU: una vez que el otro lado cerró, `recv()` **no bloquea más**
   —no hay nada que esperar, la conexión ya está cerrada— así que devuelve `b''`
   inmediatamente cada vez que se la llama. Sin el `break`, el `while True` pasa a ser un
   bucle que llama a una función que retorna al instante, sin ceder el CPU en ningún punto:
   exactamente la definición de un *busy loop*. Con el chequeo, en cambio, se corta apenas
   llega la señal de cierre:

   ```
   recv devolvio: b'test\n'
   recv() devolvio b'': el otro cerro. Se corta el bucle tras 1 lecturas utiles.
   ```

### 2.3 send() contra sendall()

7. Según la documentación: `send()` devuelve la cantidad de bytes que **realmente** mandó,
   que puede ser menor a la pedida. `sendall()` no devuelve nada (`None`) porque garantiza
   mandar todo, o lanza una excepción si falla.

8. Mandé 10 MB con `send()` en una sola llamada, sobre un socket **bloqueante**:

   ```
   send() de 10485760 bytes devolvio: 10485760 bytes mandados realmente
   mando TODO? True
   ```

   Mandó todo. Esto merece una aclaración porque contradice la intuición de "puede mandar de
   menos": en Linux, un `send()` sobre un socket **bloqueante** hace que el kernel
   internamente reintente hasta copiar todos los bytes al buffer de envío, bloqueando el
   tiempo que haga falta (solo puede devolver menos si lo interrumpe una señal). El caso
   realista donde `send()` sí trunca es con un socket **no bloqueante**, que probé aparte:

   ```
   send() NO BLOQUEANTE de 52428800 bytes devolvio: 2633835 bytes
   mando TODO? False
   ```

   Con `setblocking(False)`, mandando 50 MB sin que el otro lado lea nada, `send()` devolvió
   apenas ~2.6 MB — lo que entraba en el buffer del kernel en ese instante— y no bloqueó para
   nada. Ahí se ve de verdad el envío parcial.

9. `send()` puede ser preferible a `sendall()` en un socket no bloqueante dentro de un loop de
   eventos (`select`/`epoll`, clase 17): ahí uno *quiere* saber cuántos bytes entraron para
   reintentar el resto más tarde sin bloquear el hilo entero. Para código bloqueante
   convencional, `sendall()` es casi siempre la elección correcta.

---

## Ejercicio 3: Framing (obligatorio)

Implementación propia en [`framing_propio.py`](framing_propio.py), sin mirar `framing.py` de
la clase hasta terminar.

### Parte A: el problema

```
$ python3 echo_client.py --tres
Eco recibido: b'HOLACOMOESTAS'
```

1. El cliente hizo tres `sendall()` (`HOLA`, `COMO`, `ESTAS`) y el servidor los recibió con
   **un solo `recv()`**: el eco que volvió fue `HOLACOMOESTAS` de una pieza, sin separación
   visible entre los tres envíos.

2. **No viola el contrato de TCP.** El contrato es "flujo de bytes confiable y ordenado": los
   13 bytes llegaron todos (confiable) y en el orden `HOLA`→`COMO`→`ESTAS` (ordenado). Nunca
   prometió respetar los límites entre `sendall()`; ese concepto de "mensaje" no existe en la
   capa de transporte, lo agrega la aplicación.

### Parte B: framing por delimitador

`recibir_lineas()` en `framing_propio.py` — generador con buffer que acumula hasta encontrar
`\n`, y un `while` (no `if`) interno para entregar todas las líneas completas que haya.

3. Probado con `nc localhost 8080` escribiendo varias líneas: cada una vuelve en mayúsculas,
   una por una.

4. Con un cliente que manda `HOLA\nCOMO\nESTAS\n` en un solo `sendall()` (demo integrada en
   `framing_propio.py demo`):

   ```
   --- lineas: todo en un sendall -> OK ---
       enviados:  [b'HOLA', b'COMO', b'ESTAS', b'un mensaje mas largo que el resto']
       recibidos: [b'HOLA', b'COMO', b'ESTAS', b'un mensaje mas largo que el resto']
   ```

   Sí, recibe los mensajes completos y separados: el `while b'\n' in buffer` interno los va
   sacando de a uno aunque hayan llegado todos pegados en un mismo `recv()`.

5. Con `hola` mandado **byte por byte** con `time.sleep(0.2)` entre cada uno:

   ```
   respuesta: b'HOLA\n'
   ```

   Funciona exactamente igual. El buffer va acumulando byte a byte hasta que aparece el
   `\n`, sin importar en cuántos `recv()` se repartió la llegada. Los puntos 4 y 5 son los
   dos extremos que pedía la consigna — todo junto, todo separado — y el mismo código
   aguanta los dos porque nunca asume nada sobre cómo llegan los bytes.

### Parte C: framing por longitud

`recibir_exacto()`, `enviar_mensaje()`, `recibir_mensaje()` en `framing_propio.py`.

6. `recibir_exacto()` no puede ser `return sock.recv(n)` porque `recv(n)` es un **tope**, no
   una garantía (ejercicio 2.1). Lo comprobé con un servidor que manda 10 bytes de a 2, con
   pausa entre cada envío:

   ```
   recv(10) ingenuo (una sola llamada) devolvio: b'01'  (2 de 10 bytes pedidos)
   ```

   Un `recv(10)` sin bucle se conformó con los primeros 2 bytes que había disponibles en ese
   instante. Sin el bucle de `recibir_exacto()`, la cabecera de longitud (o el contenido) se
   leería incompleta y el protocolo quedaría desincronizado para siempre: el próximo
   `recv()` interpretaría bytes del mensaje como si fueran la cabecera del siguiente.

7. Mandé un mensaje con `\n` **en el medio**, con las dos versiones:

   ```
   ---- longitud ----
   enviado : b'linea1\nlinea2\nlinea3 con datos binarios \x00\x01\x02'
   recibido: b'LINEA1\nLINEA2\nLINEA3 CON DATOS BINARIOS \x00\x01\x02'
   identico? True

   ---- delimitador (misma entrada) ----
   enviado (con \n adentro): b'linea1\nlinea2\nlinea3'
   primera respuesta: b'LINEA1\n'   <- solo hasta el primer \n

   servidor de lineas vio esto:
     recibido: b'linea1'
     recibido: b'linea2'
     recibido: b'linea3'
   ```

   Con longitud, el mensaje viaja intacto —el `\n` es un byte más del contenido, invisible
   para el framing—. Con delimitador, el servidor lo trató como **tres mensajes distintos**
   sin darse cuenta: exactamente el problema que anticipaba la Parte D del ejercicio 6 de la
   clase 12 sobre "qué pasa si el mensaje contiene el delimitador".

8. Mensaje de **0 bytes**: funciona sin problema, la cabecera dice longitud `0` y
   `recibir_exacto(sock, 0)` devuelve `b''` de inmediato sin tocar la red.

   Mensaje de **5 GB**: no se puede ni construir la cabecera.

   ```
   struct.error: 'I' format requires 0 <= number <= 4294967295
   2**32 - 1 bytes = 4.00 GiB  <- maximo representable en 4 bytes
   ```

   El campo de longitud es un entero sin signo de 4 bytes (`!I`), así que el máximo
   representable son ~4.29 GB. 5 GB directamente no entra en el formato: `struct.pack`
   lanza la excepción antes de mandar nada. Un protocolo real que necesite mensajes más
   grandes usaría un campo de 8 bytes (`!Q`), o partiría el archivo en *chunks* (que es lo
   que hace HTTP con `chunked` — la clase 13 conecta directo con eso).

### Parte D: comparación

| | Delimitador | Longitud |
|---|---|---|
| Contenido binario arbitrario | No — hay que escapar el delimitador | Sí, directo |
| Depurable con `nc` | Sí | No (binario) |
| Hay que saber el tamaño antes | No | Sí, obligatorio |

10. HTTP combina las dos porque cada parte tiene una necesidad distinta. Los **headers** son
    de largo variable y desconocido de antemano —depende de cuántos mande el servidor— pero
    son texto, así que un delimitador (`\r\n`) es simple y no hay contenido binario que
    pueda confundirse con él. El **cuerpo**, en cambio, puede ser binario (una imagen, un
    PDF) donde buscar un delimitador sería inviable — ahí conviene declarar el tamaño por
    adelantado con `Content-Length` (o partirlo en `chunked`, que es la variante "longitud
    por partes" para cuando ni el tamaño total se conoce de antemano, como un stream).
    Cada estrategia se usa donde sus ventajas encajan con la forma de los datos.

---

## Ejercicio 4: Bytes y encoding

1. `s.sendall('hola')` da:

   ```
   TypeError: a bytes-like object is required, not 'str'
   ```

   Python 3 no permite mandar un `str` por un socket: hay que decodificar/codificar
   explícitamente, no hay conversión implícita.

2. ```python
   >>> 'ñ'.encode('utf-8')
   b'\xc3\xb1'
   >>> 'año'.encode('utf-8')
   b'a\xc3\xb1o'
   >>> len('año'), len('año'.encode('utf-8'))
   (3, 4)
   ```

   Difieren porque `len()` sobre un `str` cuenta **caracteres** (puntos de código Unicode),
   mientras que sobre `bytes` cuenta bytes. La `ñ` es un solo carácter pero en UTF-8 ocupa
   **2 bytes** (`\xc3\xb1`), así que "año" (3 caracteres) pesa 4 bytes.

3. Provocando el corte a mitad de carácter:

   ```python
   >>> datos = 'año'.encode('utf-8')          # b'a\xc3\xb1o'
   >>> primera_mitad = datos[:2]              # b'a\xc3'  (corta la ñ por la mitad)
   >>> primera_mitad.decode('utf-8')
   UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc3 in position 1: unexpected end of data
   ```

4. Se evita **acumulando en un buffer y decodificando recién cuando el mensaje está
   completo** — nunca decodificando cada `recv()` suelto. Es la misma disciplina del
   ejercicio 3: el framing (delimitador o longitud) es justamente lo que te dice cuándo el
   mensaje terminó y es seguro decodificarlo entero.

5. `errors='replace'` es aceptable para **logging o debugging** —mostrar algo legible en vez
   de explotar—, nunca para datos que la aplicación va a usar de verdad: reemplaza el
   carácter roto por `�` en silencio, lo cual esconde el bug de framing en vez de arreglarlo.

---

## Ejercicio 5: Errores y timeouts

### 5.1 Conexión rechazada

1. Sin servidor escuchando:

   ```
   ConnectionRefusedError: [Errno 111] Connection refused
   ```

2. Implementado en [`cliente_reintentos.py`](cliente_reintentos.py): captura
   `ConnectionRefusedError`/`TimeoutError` y reintenta con backoff lineal (`0.5 * intento`).

3. Lo probé lanzando el cliente primero y el servidor 2.2 segundos después:

   ```
   Intento 1 falló ([Errno 111] Connection refused). Reintento en 0.5s
   Intento 2 falló ([Errno 111] Connection refused). Reintento en 1.0s
   Intento 3 falló ([Errno 111] Connection refused). Reintento en 1.5s
   Conectado a localhost:8080

   real  0m3.043s
   ```

   Tres intentos fallidos (0 + 0.5 + 1.0 = 1.5s de espera acumulada) hasta que el servidor
   apareció y el cuarto conectó. El tiempo total (~3s) incluye además los timeouts de 2s de
   cada intento fallido de `create_connection` — en este caso `ConnectionRefusedError` es
   casi instantáneo (el SO responde enseguida que no hay nadie escuchando), así que el
   tiempo lo explica sobre todo el backoff.

### 5.2 Timeouts

4. Cliente que se conecta y hace `recv()` sin `settimeout()`, contra un servidor que nunca
   contesta: **se cuelga indefinidamente**. Lo confirmé cortándolo con un `timeout` externo
   del shell — sin eso, el proceso jamás hubiera vuelto solo:

   ```
   (exit code 124, 124 = lo mato el timeout externo => estaba colgado de verdad)
   ```

5. Con `s.settimeout(3)`:

   ```
   TimeoutError tras 3.0s: timed out
   ```

6. Un cliente sin timeout es peligroso en producción porque **un solo peer lento o caído
   cuelga el hilo/proceso que lo atiende para siempre** — no hay excepción, no hay log, el
   programa simplemente deja de avanzar. En un servidor con threads, ese thread queda
   inutilizado (y si además nunca libera un lock o una conexión de base de datos, arrastra
   a otros). Es el mismo espíritu del ejercicio 2.2: sin una condición de salida explícita,
   el programa confía ciegamente en que el otro lado se va a comportar bien.

### 5.3 Servidor robusto

7. Con `echo_server.py` corriendo, conectado con un cliente y cortando la conexión de forma
   **abrupta** (con `SO_LINGER` en 0, que fuerza un RST en vez de un cierre prolijo con FIN):
   el servidor **sobrevive**.

   ```
   servidor SIGUE VIVO tras la desconexion abrupta (RST)
   --- salida del servidor ---
   Conexión desde ('127.0.0.1', 40548)
     [127.0.0.1:40548] recv 23 bytes: b'antes de cortar abrupto'
     [('127.0.0.1', 40548)] desconexión abrupta: [Errno 104] Connection reset by peer
   ```

8. El `try/except` de `echo_server.py` captura `ConnectionResetError` y `BrokenPipeError`.
   Son justamente las dos formas en que un cliente mal desconectado se manifiesta del lado
   del servidor: `ConnectionResetError` cuando el cliente cerró abruptamente (RST) y el
   servidor intenta seguir leyendo o escribiendo esa conexión; `BrokenPipeError` cuando el
   servidor intenta *escribir* en una conexión que el otro lado ya cerró. Capturar
   específicamente esas dos —y no un `except Exception` genérico que taparía cualquier
   bug— deja que el bucle principal siga vivo para el próximo cliente sin esconder errores
   de programación reales.

---

## Ejercicio 6: El límite del servidor secuencial

Con una copia de `echo_server.py` cuya `atender()` hace `time.sleep(10)` antes de responder.

1. Con dos clientes `nc localhost 8080` casi simultáneos: el segundo **no recibe nada** hasta
   que el primero termina sus 10 segundos, aunque el `connect()` del segundo haya funcionado
   sin ningún error.

2. El segundo cliente tarda en ser atendido lo que tarda el primero en terminar (10s) **más**
   sus propios 10s de procesamiento — el log del servidor confirma el orden estrictamente
   secuencial: recién aparece `Conexión desde` del segundo cliente después de que el primero
   ya cerró.

3. `ss` mientras el primero está siendo atendido:

   ```
   LISTEN  Recv-Q=1  Send-Q=5    0.0.0.0:8080
   ESTAB             127.0.0.1:8080  127.0.0.1:54606   <- cliente 1, siendo atendido
   ESTAB             127.0.0.1:8080  127.0.0.1:54614   <- cliente 2, en la cola
   ```

   El segundo cliente aparece como **`ESTAB`, no rechazado**. El handshake lo completó el
   **kernel**, con total independencia de que la aplicación nunca haya llamado a
   `accept()` para esa conexión — `accept()` no participa del handshake, solo saca una
   conexión ya completada de la cola.

4. La columna `Recv-Q` de la línea `LISTEN` es el contador de conexiones completadas y
   pendientes de `accept()`. Con 2 clientes valía `1` (el segundo, en cola); conectando un
   tercero pasó a `2`:

   ```
   con 3 clientes: LISTEN  Recv-Q=2  Send-Q=5
   ```

   Sube de a uno por cada cliente que espera su turno.

5. Bajando a `listen(1)` y probando con cuatro clientes casi simultáneos, uno de ellos quedó
   con la conexión **sin completar**:

   ```
   ESTAB      127.0.0.1:44768  ...          <- vista del servidor: no aparece
   SYN-SENT   127.0.0.1:44768  127.0.0.1:8080   <- vista del cliente: atascado
   ```

   Ese cliente se quedó en `SYN-SENT`: mandó el SYN pero nunca llegó el SYN-ACK, porque el
   kernel del lado servidor descartó el intento al encontrar la cola de pendientes llena.
   (Con `listen(1)` en mis pruebas Linux igual dejó pasar dos o tres conexiones completas
   antes de empezar a rechazar — el backlog real que aplica el kernel no es un límite tan
   estricto como sugiere el número que se le pasa a `listen()`, tiene cierto margen interno.
   El punto pedagógico se sostiene igual: en algún punto, con la cola llena, una conexión
   nueva deja de completarse.)

6. El malentendido: "el cliente conectó, así que el servidor lo está atendiendo" es falso
   porque el `connect()` que ve el cliente **solo confirma que el kernel completó el
   handshake de tres vías**, no que la aplicación del otro lado ya llamó a `accept()` y está
   procesando algo. Puede haber pasado un instante o pueden pasar minutos —como en este
   ejercicio, hasta 10 o 20 segundos— entre que la conexión queda `ESTAB` y que el servidor
   efectivamente la atiende.

7. Tres formas de resolverlo, todas del bloque de concurrencia:
   - Un **thread por cliente** (clase 10): cada `accept()` lanza un thread que atiende y el
     bucle principal vuelve enseguida a `accept()`.
   - Un **proceso por cliente** con `fork()` (clase 4): mismo esquema, aislando cada cliente
     en su propio espacio de memoria.
   - **Multiplexar con `select()`/`epoll()`** (clase 17): un solo hilo atiende a muchos
     clientes intercalando el trabajo, sin bloquearse en ninguno.

---

## Ejercicios adicionales

### Servidor de comandos

[`servidor_comandos.py`](servidor_comandos.py), sobre `recibir_lineas()` de
`framing_propio.py`:

```
TIME                           -> b'2026-08-25T17:43:10.208406\n'
ECHO hola mundo                -> b'hola mundo\n'
ALGO_INVALIDO                  -> b'ERROR: comando desconocido\n'
QUIT                           -> b'BYE\n'
```

Reutilizar el framing por líneas ya resuelto en el ejercicio 3 hizo que el servidor de
comandos fuera casi solo un `if/elif` sobre el texto recibido — el trabajo de reconstruir
mensajes ya estaba hecho.

### Transferencia de archivos

[`transferir_archivo.py`](transferir_archivo.py), con el framing por longitud (soporta
binario sin escapes, a diferencia del de líneas). Probado con un archivo de 5 MB:

```
md5 origen : c34413a2fa0cc360731afcd4c99dd94d
md5 destino: c34413a2fa0cc360731afcd4c99dd94d   -> IDENTICOS
```

### Cliente HTTP mínimo

[`http_minimo.py`](http_minimo.py): arma la petición a mano (`GET`, `Host`,
`Connection: close`), lee hasta que el socket cierra, separa cabeceras de cuerpo buscando
`\r\n\r\n` (el propio HTTP usa un delimitador ahí) y parsea los headers línea por línea:

```
Estado: HTTP/1.1 200 OK
  Content-Type: text/html
  Transfer-Encoding: chunked
  ...
Cuerpo: 571 bytes
```

Es deliberadamente ingenuo con `Transfer-Encoding: chunked` — no interpreta los tamaños de
chunk, solo junta todos los bytes hasta que el socket cierra (que funciona porque pedí
`Connection: close`). Un cliente HTTP real necesitaría además decodificar el chunking para
separar el cuerpo real de los tamaños intercalados.

### getaddrinfo y fallback de direcciones

[`getaddrinfo_fallback.py`](getaddrinfo_fallback.py): recorre `getaddrinfo()` y prueba cada
`(familia, dirección)` hasta que una conecte, capturando `OSError` en cada intento fallido:

```
Conectado por IPv4 a ('172.66.147.243', 80)
```

En esta máquina no llegó a probar IPv6 porque la primera entrada (IPv4) conectó directo —
para verlo fallar y recuperarse de verdad haría falta un host con una entrada AAAA que no
responda, o forzar el orden de la lista. Es exactamente lo que hace `create_connection()`
por dentro: por eso alcanza casi siempre con usar esa función en vez de escribir este bucle
a mano.

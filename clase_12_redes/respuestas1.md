## Ejercicio 1: Reconocimiento de tu propia máquina

### 1.1 Interfaces y direcciones

1. Tengo 6 interfaces de red: `lo`, `enp2s0`, `wlp1s0`, `br-98d5f5454ad8`, `docker0`, `br-7cea78aef911`.
   La interfaz de loopback es `lo`.

2. Mi IP en la red local es `10.70.137.92` (interfaz `wlp1s0`). Es una dirección privada, dentro del rango `10.x.x.x`.

3. Sí tengo dirección IPv6: `fe80::f5c3:71b4:2764:58dc/64` en la interfaz `wlp1s0`. Empieza con `fe80:`, por lo tanto es link-local: solo vale dentro de mi red física, no rutea a Internet.

### 1.2 Rutas

4. Mi gateway por defecto es `10.70.0.1` (línea `default via 10.70.0.1 dev wlp1s0`).

5. El gateway (`10.70.0.1`) está en la misma subred que mi propia IP (`10.70.137.92`): ambos comparten los primeros dos octetos (`10.70.x.x`, red `/16`). Esto es necesario porque mi máquina solo puede alcanzar directamente (sin pasar por otro router) a dispositivos dentro de su misma red local.

### 1.3 Puertos en escucha

6. Tres servicios escuchando:
   - Puerto 53 (DNS / systemd-resolved) en `127.0.0.54` y `127.0.0.53`
   - Puerto 45473 (VS Code) en `127.0.0.1`
   - Puerto 631 (CUPS, sistema de impresión) en `127.0.0.1` y `[::1]`

7. Todos los servicios de mi máquina escuchan en `127.0.0.1` (o `[::1]` en IPv6) — ninguno escucha en `0.0.0.0`. Esto implica que ningún servicio es alcanzable desde otra máquina en mi misma red wifi: solo procesos locales pueden conectarse a ellos. Si escucharan en `0.0.0.0`, cualquiera en la red local podría intentar conectarse.

> **Nota:** las respuestas de arriba se tomaron en otra red (IP `10.70.137.92`). Al hacer
> el resto de los ejercicios mi IP era `192.168.1.50/24` (gateway `192.168.1.1`). El
> razonamiento no cambia: sigue siendo una privada (`192.168.x.x`) y el gateway sigue
> estando en la misma subred que mi IP.

---

## Ejercicio 2: Resolución de nombres

```
;; ANSWER SECTION:
www.um.edu.ar.		600	IN	A	200.51.41.139
;; Query time: 42 msec
;; SERVER: 127.0.0.53#53(127.0.0.53) (UDP)
```

1. Devuelve `200.51.41.139` (un único registro `A`).

2. El TTL es `600`: los segundos que cualquier cache intermedio puede guardar esta
   respuesta antes de volver a preguntarle al servidor autoritativo. Por eso un cambio de
   DNS "tarda en propagarse": los caches siguen sirviendo el valor viejo hasta que expira.

3. Sí, bajó a `597` en la segunda corrida (3 segundos después). La respuesta ya no vino del
   servidor autoritativo sino del cache de `systemd-resolved` (`127.0.0.53`, visible en la
   línea `SERVER:`), que descuenta del TTL el tiempo que la entrada lleva guardada. El
   número que se ve es el TTL *restante*; cuando llega a 0 se descarta y la próxima consulta
   vuelve a salir a la red.

4. `dig google.com +short` me devolvió una sola dirección. Probé con `yahoo.com` para ver el
   caso de múltiples:

   ```
   $ dig yahoo.com +short
   98.137.11.164   74.6.231.20   74.6.231.21
   74.6.143.25     74.6.143.26   98.137.11.163
   ```

   Sirve para **balanceo de carga** (el servidor rota el orden en cada respuesta:
   round-robin DNS) y para **tolerancia a fallos** (si una IP no responde, el cliente
   reintenta con la siguiente). Que Google devuelva una sola no es contradictorio: resuelve
   la redundancia con anycast/GeoDNS en vez de con múltiples registros — de hecho, si le
   pregunto a otro resolver la IP cambia:

   ```
   $ dig google.com +short          -> 142.251.129.46
   $ dig @8.8.8.8 google.com +short -> 142.251.129.174
   ```

5. Sí, y mucho: `23 msec` la primera vez, `0 msec` la segunda. Cachea `systemd-resolved`
   (el `127.0.0.53` de la línea `SERVER:`). La primera consulta salió a la red; la segunda
   se contestó desde memoria local sin mandar un paquete.

---

## Ejercicio 3: Cliente y servidor con netcat

### 3.1 Conversación básica

1. **Si cierro el cliente con Ctrl+C, el servidor también termina** (y al revés). `nc -l`
   atiende **una sola** conexión: cuando esa conexión se cierra, no hay nada más que hacer y
   el proceso sale. Para que sobreviva y siga aceptando hace falta `-k` (*keep listening*).
   Es justo lo que la clase 13 nos va a obligar a programar a mano: un `while True`
   alrededor del `accept()`.

2. Con la conexión abierta:

   ```
   $ ss -tnp | grep 8080
   ESTAB  127.0.0.1:8080   127.0.0.1:50124  users:(("nc",pid=12652,fd=4))
   ESTAB  127.0.0.1:50124  127.0.0.1:8080   users:(("nc",pid=12664,fd=3))
   ```

   Dos líneas porque ambos extremos están en la misma máquina: se ve la conexión desde los
   dos lados. Es la misma cuádrupla leída al derecho y al revés — el `8080` es el puerto que
   elegí con `bind`, el `50124` lo asignó el kernel del rango efímero (ejercicio 7).

3. **Dos clientes a la vez: no funciona, y falla de forma más sutil de lo esperado.**

   ```
   ESTAB  12  0  127.0.0.1:8080  127.0.0.1:50140                    <- sin proceso!
   ESTAB  0   0  127.0.0.1:8080  127.0.0.1:50124  users:(("nc",...))
   LISTEN 1   1    0.0.0.0:8080    0.0.0.0:*      users:(("nc",...))
   ```

   El servidor solo imprimió `CLIENTE-UNO`. Lo interesante: la segunda conexión **igual
   figura `ESTAB`**, porque el handshake de tres vías lo completa el *kernel*, no la
   aplicación. Los 12 bytes de `CLIENTE-DOS\n` están en el `Recv-Q` de esa conexión, pero no
   tiene `users:` — ningún proceso la agarró todavía. La confirmación está en la línea
   `LISTEN`: `Recv-Q=1` son las conexiones completadas y pendientes de `accept()`.

   El cliente 2 conecta sin error, manda datos sin error, y se queda esperando una respuesta
   que nunca llega porque `nc` no vuelve a llamar `accept()`. **Desde el cliente no hay forma
   de distinguir "el servidor me ignora" de "el servidor está lento"** — el problema central
   de la introducción de la clase, en vivo.

### 3.2 El puerto ocupado

4. **En mi sistema no da error.** Dos `nc -l 8080` quedan los dos escuchando:

   ```
   LISTEN 0 1 0.0.0.0:8080 0.0.0.0:* users:(("nc",pid=12712,...))
   ```

   `netcat-openbsd` de Debian/Ubuntu setea `SO_REUSEPORT` además de `SO_REUSEADDR` (lo
   confirmé antes con `strace -e trace=setsockopt,bind nc -l`), que le pide al kernel permitir
   varios sockets en escucha sobre el mismo puerto — pensado para servidores multi-proceso.

   Para ver el error que pide la consigna hay que bindear sin esa opción:

   ```
   $ python3 -c "import socket; s=socket.socket(); s.bind(('0.0.0.0', 8080))"
   OSError errno=98 (Address already in use)
   ```

   Ese `EADDRINUSE` es el que la clase 13 resuelve con `SO_REUSEADDR` — pero por otro motivo:
   no para compartir el puerto, sino para poder re-bindearlo mientras la conexión anterior
   sigue en `TIME_WAIT`.

### 3.3 Loopback contra todas las interfaces

```
$ nc -l 127.0.0.1 8080  ->  LISTEN  127.0.0.1:8080  0.0.0.0:*
$ nc -l 0.0.0.0 8080    ->  LISTEN    0.0.0.0:8080  0.0.0.0:*
```

Con el bind en `127.0.0.1` el socket queda atado a loopback: un paquete que entre por
`wlp1s0` dirigido a `192.168.1.50:8080` no matchea con ese socket y el kernel lo descarta.
Con `0.0.0.0` el socket matchea con cualquier IP local, incluida la de la wifi.

5. Un servidor de desarrollo escucha en `127.0.0.1` porque así **solo es alcanzable desde la
   propia máquina**: nadie en la red del bar, del campus o de casa puede llegar a un
   servidor que probablemente tenga cero autenticación y credenciales de prueba.

---

## Ejercicio 4: HTTP a mano

1. **`HTTP/1.1 200 OK`** en la primera línea.

2. Tres headers de la respuesta:

   - `Content-Type: text/html` — cómo interpretar el cuerpo.
   - `Connection: close` — el servidor cierra el TCP apenas termina de responder (eco de lo
     que pedí en la petición).
   - `Transfer-Encoding: chunked` — el cuerpo viene en trozos con su longitud al principio de
     cada uno, en vez de un `Content-Length` único. Por eso en la salida cruda aparece un
     `22f` (559 en hexa, tamaño del trozo) antes del HTML y un `0` marcando el fin.

   Este header responde directamente al problema de la clase: **HTTP corre sobre TCP, que es
   un flujo sin límites de mensaje, así que HTTP tiene que delimitarse solo.** Lo hace con
   `Content-Length` o con `chunked`.

3. Sin `Host:` → `HTTP/1.1 400 Bad Request`. HTTP/1.1 lo exige porque una misma IP puede
   alojar cientos de sitios (*virtual hosting*): TCP entregó los bytes a la máquina correcta,
   pero la IP no identifica el sitio, solo la máquina. El servidor necesita que el cliente le
   diga a cuál de todos los dominios que atiende le está hablando.

4. `GET /noexiste` → **`404 Not Found`**. El cuerpo es igual al del `200` (example.com sirve
   la misma página), lo que deja claro que **código de estado y cuerpo son independientes**.

5. Con `\n` en vez de `\r\n` **funcionó igual** (`200 OK`): Cloudflare es tolerante. Depender
   de eso es mala idea por tres razones: el RFC exige `\r\n`, así que lo que anda es una
   concesión del servidor, no una garantía; falla al cambiar de servidor, no al escribir el
   código (anda en dev, revienta el día que aparece un proxy estricto en el medio); y cuando
   dos piezas de la cadena no se ponen de acuerdo sobre dónde termina un mensaje aparece
   *request smuggling*. El principio general: ser estricto en lo que se emite, tolerante en
   lo que se acepta — pero nunca emitir apoyándose en la tolerancia ajena.

---

## Ejercicio 5: Observar el handshake

> **Pendiente** — requiere `sudo`, que en esta sesión pide contraseña interactiva y no lo
> pude correr. Comandos a ejecutar en tres terminales:
>
> ```bash
> sudo tcpdump -i lo -n port 8080     # terminal 1
> nc -l 8080                          # terminal 2
> echo "test" | nc localhost 8080     # terminal 3
> ```

Lo que espero ver, según el diagrama del contenido:

```
Cliente                          Servidor
   |------------ SYN ------------->|   [S]    apertura
   |<---------- SYN-ACK -----------|   [S.]
   |------------ ACK ------------->|   [.]    conexión lista
   |------ PSH-ACK "test\n" ------>|   [P.]   5 bytes de datos
   |<----------- ACK --------------|   [.]
   |------------ FIN ------------->|   [F.]   cierre lado cliente
   |<----------- ACK --------------|   [.]
   |<----------- FIN --------------|   [F.]   cierre lado servidor
   |------------ ACK ------------->|   [.]
```

1. Los tres del handshake llevan `[S]`, `[S.]` y `[.]`. El punto en `tcpdump` **es** el flag
   ACK, así que `[S.]` = SYN+ACK.

2. Espero **~10 paquetes para 5 bytes útiles** (`test\n`): 3 de apertura, 2 de datos y su
   confirmación, 4 de cierre. Con 20 bytes de encabezado TCP + 20 de IP por paquete, son
   ~400 bytes de overhead para 5 de payload — el precio del handshake y las garantías, que
   se amortiza en conexiones largas y es carísimo en mensajes cortos. Por eso DNS usa UDP.

3. El cierre lleva `[F.]` (FIN+ACK) y son **cuatro** paquetes, no tres, porque TCP es
   full-duplex y **cada dirección se cierra por separado**: quien manda FIN avisa que no
   tiene más para enviar, pero puede seguir recibiendo.

---

## Ejercicio 6: TCP es un flujo (obligatorio)

### Parte A: observar el problema

1. **Los tres envíos llegaron fusionados**, verificado con un receptor Python que cuenta
   `recv()` (no con `od -c`, que bufferea y podría engañar):

   ```
   sin_pausa: 1 recv() para 3 send()
   ```

2. **Con `sleep(1)` entre envíos cambia:**

   ```
   con_pausa: 3 recv() para 3 send()
   ```

   Pero **no puedo confiar en eso**. No cambió el contrato de TCP, solo las condiciones de
   ejecución: sin pausa, el **algoritmo de Nagle** retiene los envíos chicos y además los
   tres `send()` entran al buffer de salida antes de que el receptor alcance a leer; con
   `sleep`, cada envío sale y llega solo, pero eso depende de latencia, MTU, buffers y carga
   de la máquina. `sleep` vuelve **improbable** la fusión, no imposible: el día que la red se
   congestione vuelve a pasar. Y en el sentido contrario tampoco protege: nada impide que un
   mensaje llegue partido en dos `recv()`, la otra mitad del problema.

### Parte B: la pregunta

3. **No es un bug: es el contrato de TCP.** Un flujo de bytes confiable y ordenado garantiza
   que todos los bytes llegan (✓, llegaron los 13) y en el orden en que se enviaron (✓,
   `HOLACOMOESTAS`). Nunca prometió nada sobre el agrupamiento. `send()` es "copiá estos
   bytes al buffer de salida", no "mandá este mensaje": el concepto de "mensaje" no existe en
   la capa de transporte, lo pone la aplicación arriba.

4. **Dos formas de delimitar mensajes:**

   **a) Delimitador (`\n`)**: se manda `HOLA\nCOMO\nESTAS\n`, el receptor acumula en buffer y
   corta en cada `\n`. Legible, depurable con `nc`, no requiere saber el largo antes. El
   problema es si el mensaje contiene el delimitador: el receptor corta donde no debe y todo
   el stream queda desincronizado desde ahí. Hay que escapar el delimitador (costoso, hay que
   acordarse en los dos lados) o prohibirlo por diseño. Riesgo extra: si nunca llega el
   delimitador el buffer crece sin límite — hay que ponerle un tope y cortar la conexión.

   **b) Prefijo de longitud**: `[4 bytes: N][N bytes: contenido]`. El receptor siempre lee 4
   bytes, los interpreta como tamaño, y lee exactamente esa cantidad. El contenido puede ser
   cualquier cosa —incluido `\n`— porque el largo viaja fuera de banda. Es binario (no se
   tipea a mano), hay que acordar endianness y ancho del campo entre las dos puntas, y un
   largo corrupto desincroniza el stream sin forma de resincronizar (con delimitador al menos
   se puede buscar el próximo `\n`). Hay que validar el largo antes de reservar memoria: un
   prefijo que dice "4 GB" sin chequeo cuelga el proceso.

   En los dos casos, `recv()` puede devolver menos de lo pedido: leer un mensaje siempre es
   un bucle hasta completar, nunca un `recv()` suelto.

### Parte C: UDP para contrastar

5. **3 `recvfrom()` para 3 `sendto()`**, contra el `1 recv()` de TCP con los mismos datos:

   ```
   recvfrom #1: b'HOLA'  de ('127.0.0.1', 38220)
   recvfrom #2: b'COMO'  de ('127.0.0.1', 38220)
   recvfrom #3: b'ESTAS' de ('127.0.0.1', 38220)
   ```

   Los tres compartieron puerto de origen: el kernel se lo asignó al socket UDP en el primer
   `sendto()` aunque nunca hubo `connect()`.

6. TCP fusiona porque **necesita** libertad para reempaquetar: retransmitir lo perdido,
   reordenar, ajustarse a la ventana de congestión. No hay ningún campo en el encabezado TCP
   que diga "acá termina un mensaje", solo un contador de bytes. UDP no fusiona porque no
   tiene nada que optimizar: **cada `sendto()` produce un paquete IP con un campo de longitud
   explícito** en el encabezado UDP. Llega entero o no llega; sin estado, sin retransmisión,
   sin reordenamiento, no hay motivo para tocar los límites. Resumen: TCP paga la pérdida de
   límites a cambio de confiabilidad; UDP conserva los límites a cambio de no garantizar nada.

7. **UDP no necesita `listen()`/`accept()` porque no hay conexión que aceptar.** Esas
   llamadas administran el ciclo de vida de una conexión: `listen()` crea la cola de
   handshakes completados, `accept()` saca uno y devuelve un socket nuevo por cliente. Eso
   presupone estado por cliente. UDP no tiene handshake ni estado por cliente: hay un solo
   socket para todo el mundo, y por eso `recvfrom()` devuelve la dirección de origen junto
   con los datos — es la única forma de saber quién habló, ya que no hay un socket dedicado
   que lo identifique.

---

## Ejercicio 7: Puertos efímeros

1. ```
   $ cat /proc/sys/net/ipv4/ip_local_port_range
   32768	60999
   ```

   Mi sistema: 32768–60999 (28232 puertos). IANA recomienda 49152–65535 (16384 puertos). **No
   coinciden.** La recomendación de IANA es sobre puertos *registrados*, pensada para dejar
   libre el 1024–49151. Linux prioriza tener más puertos efímeros disponibles, porque una
   máquina que abre muchas conexiones salientes se queda sin puertos antes que sin servicios
   registrados. Que sea recomendación y no imposición es posible porque el puerto de origen
   es opaco para el otro extremo: solo tiene que ser único en la cuádrupla, a nadie del otro
   lado del cable le importa de qué rango salió.

2. Cinco conexiones a `example.com:80`:

   ```
   ('192.168.1.50', 46108)
   ('192.168.1.50', 46122)
   ('192.168.1.50', 46134)
   ('192.168.1.50', 46136)
   ('192.168.1.50', 46140)
   ```

   Todas dentro de `32768–60999` ✓. El patrón crece mayormente de a poco (46108→46122→46134,
   +14/+12) con algún salto de a 2, no es un contador estrictamente secuencial: Linux elige
   un punto de partida y avanza salteando puertos ya usados, para que un observador externo
   no pueda predecir el próximo (un contador predecible facilita spoofing).

3. Las cinco salieron por **IPv4**, y `getsockname()` da una tupla de **2 elementos**:
   `(IP, puerto)`. Mi única IPv6 es `fe80::...` (link-local, de la clase 1), que no rutea a
   Internet — si hubiera salido por IPv6 la tupla tendría **4 elementos**:
   `(host, puerto, flowinfo, scope_id)`, donde el `scope_id` es imprescindible justamente con
   direcciones link-local, porque `fe80::/10` es válida en todas las interfaces a la vez y la
   dirección sola es ambigua. Código que asume `host, puerto = sock.getsockname()` se rompe
   con un `ValueError` el día que la conexión sale por IPv6.

4. ```
   $ ss -tn state established '( dport = :80 )'
   192.168.1.50:46108  172.66.147.243:80
   192.168.1.50:46122  172.66.147.243:80
   192.168.1.50:46134  172.66.147.243:80
   192.168.1.50:46136  172.66.147.243:80
   192.168.1.50:46140  172.66.147.243:80
   ```

   Las cinco comparten IP de origen, IP de destino y puerto de destino. Lo único que las
   distingue es el puerto de origen, y alcanza: cada fila es una cuádrupla única. Es el
   mecanismo que permite que un servidor atienda miles de clientes en el puerto 80.

5. **Hacia el mismo servidor y puerto: ~28232 conexiones** (el rango efímero completo), y en
   la práctica bastante menos porque `TIME_WAIT` retiene el par 60 segundos después de
   cerrar: con 28232 puertos y 60s de `TIME_WAIT`, el techo sostenible es de unas 470
   conexiones nuevas por segundo contra ese mismo destino. **Hacia servidores distintos:
   muchísimas más**, porque cambia otra pata de la cuádrupla — el mismo puerto de origen
   puede estar en uso contra cien destinos distintos sin conflicto; el límite pasa a ser
   memoria del kernel y `ulimit -n`. Por eso un balanceador de carga —cliente hacia un
   puñado de backends fijos— se queda sin puertos mucho antes que un cliente cualquiera: su
   techo es `backends × 28232`, y con `TIME_WAIT` de por medio, el de conexiones nuevas por
   segundo es más bajo todavía. La salida habitual es reusar conexiones con keep-alive en vez
   de abrir una por request.

---

## Ejercicios adicionales

### Escaneo de puertos propio

```bash
for p in $(seq 1 1024); do nc -z -w1 127.0.0.1 $p 2>/dev/null && echo "abierto: $p"; done
```

| método | resultado |
|---|---|
| `nc -z` contra `127.0.0.1` | 631 |
| `ss -tlnp` | 53, 631 |

**No coinciden**, y la diferencia es instructiva: el 53 no aparece en el escaneo porque
`systemd-resolved` no escucha en `127.0.0.1` sino en `127.0.0.53`/`127.0.0.54` — toda la red
`127.0.0.0/8` es loopback, no solo el `.1`. La moraleja vale para cualquier escaneo: prueba
pares (IP, puerto), y "no responde" no es lo mismo que "no hay nada". `ss` ve la tabla del
kernel desde adentro y no tiene ese problema.

> Solo contra mi propia máquina.

### Servidor de archivos improvisado

```bash
nc -l 9999 > destino.bin
nc -N localhost 9999 < origen.bin
```

```
md5 origen : f5c61e5ae4315b023a031c1c4b3de16b
md5 destino: f5c61e5ae4315b023a031c1c4b3de16b   -> IDENTICOS (200000 bytes)
```

TCP cumpliendo su contrato: los bytes llegan todos y en orden. El `-N` en el cliente es
necesario para que `nc` cierre el socket al terminar el archivo — sin él el receptor nunca
sabe que terminó. Es el ejercicio 6 otra vez: TCP no tiene marca de "fin de mensaje", y acá el
delimitador que se usa es el cierre mismo de la conexión.

### Medir el costo del handshake

`socket.create_connection()`, 8 repeticiones cada uno:

| destino | media | mínimo |
|---|---|---|
| loopback `127.0.0.1` | 1.778 ms | 0.554 ms |
| gateway LAN `192.168.1.1:80` | 2.261 ms | 1.678 ms |
| remoto `example.com:80` | 35.427 ms | 31.784 ms |

La diferencia es casi toda latencia de propagación, no trabajo de CPU: el handshake cuesta un
ida y vuelta completo (`connect()` retorna al mandar el tercer paquete), así que su costo
debería ser ≈ 1 RTT — y es lo que se ve al pasar de loopback (sin cable de por medio) a la LAN
(un salto físico) a Internet (docenas de saltos). Por eso "abrir la conexión" domina el tiempo
total de una petición corta, y por eso HTTP/1.1 reusa conexiones, TLS 1.3 recortó su handshake
a 1-RTT, y QUIC fusiona el handshake de transporte con el de cifrado.
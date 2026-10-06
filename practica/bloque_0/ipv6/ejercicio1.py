#Comprimí estas direcciones aplicando las dos reglas, **sin usar Python**:

#1. `2001:0db8:0000:0000:0000:ff00:0042:8329` 2001:db8::ff00:42:8329
#2. `0000:0000:0000:0000:0000:0000:0000:0001` ::1
#3. `fe80:0000:0000:0000:0202:b3ff:fe1e:8329` fe80::202:b3ff:fe1e:8329
#4. `2001:0db8:0000:0000:0001:0000:0000:0001` 2001:db8::1:1 ----> mal

import ipaddress
print(ipaddress.ip_address('2001:0db8:0000:0000:0001:0000:0000:0001').compressed)
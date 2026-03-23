import sys
if len(sys.argv)<2: 
    print(f"Porfavor ingrese su nombre")
    
elif len(sys.argv) == 2:
    nombre=sys.argv[1]
    print(f"Hola {nombre}!")
elif len(sys.argv)>2:
    nombre=" ".join(sys.argv[1:])
    print(f"Hola {nombre}!")

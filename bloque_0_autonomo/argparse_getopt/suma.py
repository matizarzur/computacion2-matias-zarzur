import sys
suma=0
cnt_num=len(sys.argv)
for i in range(1,cnt_num):
    suma += float(sys.argv[i])

print (suma)
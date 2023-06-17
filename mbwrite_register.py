#!/usr/bin/env python3

import sys
import asyncio
from phoenix_config import MBDevice

from phoenix_constants import SERIAL_PORTS


print(f"Argumentos: {sys.argv}")
port = SERIAL_PORTS[1]
sl = adr = val = None
mboperation = 6  # Por defecto, Holding Register
try:
    sl, adr, val = map(lambda x: int(x), sys.argv[1:4])
    if len(sys.argv) == 5:  # El cuarto argumento es el tipo 1: coil / 2:discrete i / 3: Holding R / 4: Input Reg
        mboperation = int(sys.argv[4])
        if not mboperation in [5, 6]:
            print(f"Operación {mboperation} no válida. \nValores admitidos para "
                  f"coils son 5 y para holding reg 6")
except SyntaxError as e:
    print(f"Hay que introducir como mínimo 3 argumentos: Esclavo, dirección en la que escribir y valor. "
          f"Si no se indica operación, se toma el valor 6 para holding registers")
    print(f"Valores introducidos:\n\tEsclavo: {sl}\n\tDirección ModBus: {adr}\n\tValor: {val}")

mbdev = MBDevice(port, "Dispositivo Modbus", sl)
writop = asyncio.run(mbdev.write(mboperation, adr, val))
print(f"... Comprobando escritura")
readmboperation = 3 if mboperation == 6 else 1
reading = asyncio.run(mbdev.read(readmboperation, adr, 1))
print(reading)
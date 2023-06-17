#!/usr/bin/env python3

import sys
import asyncio
from phoenix_config import MBDevice

from phoenix_constants import SERIAL_PORTS


print(f"Argumentos: {sys.argv}")
port = SERIAL_PORTS[1]
sl = adr = quan = None
regtype = 3  # Por defecto, Holding Register
try:
    sl, adr, quan = map(lambda x: int(x), sys.argv[1:4])
    if len(sys.argv) == 5:  # El cuarto argumento es el tipo 1: coil / 2:discrete i / 3: Holding R / 4: Input Reg
        regtype = int(sys.argv[4])
except SyntaxError as e:
    print(f"Hay que introducir como mínimo 3 argumentos: Esclavo, dirección a leer y cantidad. Si no se indica "
          f"tipo de registro, se toman holding registers")
    print(f"Valores introducidos:\n\tEsclavo: {sl}\n\tDirección ModBus: {adr}\n\tCantidad: {quan}")

mbdev = MBDevice(port, "Dispositivo Modbus", sl)
reading = asyncio.run(mbdev.read(regtype, adr, quan))

print(reading)
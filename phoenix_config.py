#!/usr/bin/env python3
from typing import Union, List, Tuple, Dict
import serial
from dataclasses import dataclass
from datetime import datetime
from math import ceil
from time import sleep
import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
from modbus_tk.modbus import ModbusError

from phoenix_constants import *

# VARIABLES DEL SISTEMA PHOENIX
boardsn: str = ""  # Número de serie de la placa
prj: Dict = {}  # Diccionario generado a partir del JSON con la configuración del proyecto
datadb: Dict = {}  # Variable para almacenar las lecturas de registros ModBus y asociarlas con las Rooms
all_room_groups: Dict = {}  # Diccionario con todos los grupos de habitaciones. Clave principal es id del grupo
buses: Dict = {}  # Diccionario con las instancias de los dispositivos ModBus asociados a cada bus
mbregmaps: Tuple = ()  # Tupla de objetos tipo mapa de registros modbus ModbusRegisterMap.


# El mapa de registros es un diccionario cuya clave principal de cada diccionario permite identificar
# cada dispositivo por marca y modelo

@dataclass
class MBDevice:
    port: Union[None, str] = None  # Puerto de comunicaciones
    name: Union[None, str] = ""  # Descripción del dispositivo en el proyecto
    slave: Union[None, int] = None  # Dirección en el ModBus
    baudrate: int = 9600
    databits: int = 8
    parity: Union[str, int] = PARITY_EVEN  # Por defecto, paridad PAR
    stopbits: int = 1
    brand: str = ""
    model: str = ""
    qregsmax: int = 25
    conn: modbus_tk.modbus_rtu.RtuMaster = None
    serialport: serial.Serial = None
    write_ops: Tuple = (cst.WRITE_SINGLE_COIL,
                        cst.WRITE_MULTIPLE_COILS,
                        cst.WRITE_SINGLE_REGISTER,
                        cst.WRITE_MULTIPLE_REGISTERS)

    async def connect(self) -> Union[modbus_tk.modbus_rtu.RtuMaster, None]:
        try:
            # Connect to the slave
            serport = serial.Serial(port=self.port,
                                    baudrate=self.baudrate,
                                    bytesize=self.databits,
                                    parity=self.parity,
                                    stopbits=self.stopbits,
                                    xonxoff=0)

            # print(f'{datetime.now()} - Estado puerto serie {self.port}: {["cerrado", "abierto"][serport.is_open]}')
            # serport.flush()
            self.conn = modbus_rtu.RtuMaster(serport)
            self.conn.set_timeout(1)
            self.conn.set_verbose(True)

            # print(f'{str(datetime.now())} - Conexión realizada con el puerto {self.port}')
            return self.conn

        except modbus_tk.modbus.ModbusError as exc:
            print(exc)
            return

    async def read(self, mbop: int, adr: int, quan: int) -> Union[Tuple[int, ...], None]:
        """
        Método para leer el dispositivo ModBus
        Params: mbop: operación de lectura ModBus; 1=coils; 2=discrete inputs; 3:holding registers; 4;input registers
        adr: registro modbus a leer
        quan: cantidad de registros a leer
        Returns: resultado de la lectura modbus.
        """
        # Si quan es mayor que el máximo número de registros a leer de una vez, qregsmax, el proceso de lectura
        # se hace por partes de manera que en cada proceso de lectura no se supere el máximo número de registros
        self.qregsmax = self.qregsmax if self.qregsmax else 25
        if quan > self.qregsmax:
            readings = []
            qreadings = ceil(quan / self.qregsmax)  # Calculo el número de lecturas que es necesario hacer
            for i in range(qreadings):
                init_adr = adr + i * self.qregsmax
                partial_quan = self.qregsmax if (i + 1) * self.qregsmax < quan else quan - i * self.qregsmax
                readings.append((init_adr, partial_quan))
        else:
            readings = [(adr, quan)]
        total_readings = []
        # try:
        self.conn = await self.connect()
        print("\n... abriendo conexión con el dispositivo Modbus")
        for reading in readings:
            if mbop not in [cst.READ_COILS,
                            cst.READ_DISCRETE_INPUTS,
                            cst.READ_HOLDING_REGISTERS,
                            cst.READ_INPUT_REGISTERS]:
                print(f'Operación de lectura, {mbop}, no válida')
                return
            # print(f"lectura Modbus\n\t{self.__dict__}")
            tries = 0
            # self.conn = await self.connect()
            while tries < READING_TRIES:
                try:
                    tries += 1
                    print(f'{datetime.now()} -\tIntentando leer {reading[1]} registros desde el registro {reading[0]} '
                          f'del esclavo {self.slave} con la operación {mbop} en el '
                          f'puerto {self.port} ==> Intento {tries}')
                    reading = self.conn.execute(self.slave, mbop, reading[0], reading[1])
                    if reading:
                        break
                    sleep(0.5)
                except Exception as e:
                    print(f"Error lectura intento {tries}\n{e}")

            else:
                print(f'{str(datetime.now())} -\tNo se ha podido realizar la lectura de {quan} registros desde la '
                      f'dirección {adr} del esclavo {self.slave}/{self.name} con la operación {mbop} en el '
                      f'puerto {self.port}\n')
                print("... cerrando conexión con el dispositivo Modbus\n")
                self.conn.close()
                return

            total_readings += reading
        print("... cerrando conexión con el dispositivo Modbus\n")
        self.conn.close()
        return tuple(total_readings)

    async def write(self, mbop: int, adr: int, *output_value: Union[int, Tuple[int], List[int]]):

        # Compruebo operaciones de escritura válidas definidas para el dispositivo
        if mbop not in self.write_ops:
            print(f'Operación de escritura, {mbop}, no válida. Dispositivo {self.name}')
            return

        # Compruebo si se han introducido valores a escribir:
        if not output_value:
            print(f'Escritura ModBus: No se han introducido valores a escribir en el dispositivo {self.name}')
            return

        # Si se quieren escribir varios valores, pero no está habilitada la escritura múltiple en el dispositivo,
        # la escritura se divide en procesos de escritura simple
        if len(output_value) > 1 and mbop in [cst.WRITE_SINGLE_COIL, cst.WRITE_SINGLE_REGISTER]:
            # Lista de tuplas con (registro, valor a escribir)
            writinglist = [(adr + adroffset, (wvalue,)) for adroffset, wvalue in enumerate(output_value)]
        else:
            writinglist = [(adr, output_value)]

        for wlist in writinglist:
            await self.do_write(self.slave, mbop, wlist[0], *wlist[1])

        print(
            f'{str(datetime.now())} -\tIntentando escribir {len(output_value)} valores a partir del registro {adr} del '
            f'esclavo {self.slave} con la operación {mbop} en el puerto {self.port}')

    async def do_write(self, slv: int, mbop: int, adr: int, *output_value: Union[int, Tuple[int], List[int]]):
        try:
            self.conn = await self.connect()
            value2write = output_value[0] if len(output_value) == 1 and mbop in [5, 6] else output_value
            ret = self.conn.execute(slv, mbop, adr, output_value=value2write)
            return ret
        except Exception as e:
            if isinstance(output_value, int):
                msg = f'{datetime.now()} -\tNo se ha podido escribir el valor {output_value} en el registro {adr}' \
                      f' del esclavo {self.slave} con la operación {mbop} en el puerto {self.port}\n{e}'
            else:
                msg = f'{datetime.now()} -\tNo se han podido escribir {len(output_value)} registros del ' \
                      f'esclavo {self.slave} con la operación {mbop} en el puerto {self.port}\n{e}'
            print(msg)
            return
        finally:
            self.conn.close()

    def __repr__(self):
        dev_info = f"Dispositivo {self.name}: {self.brand} / {self.model}. Esclavo {self.slave}"
        return dev_info


class ModbusRegisterMap:
    """
    Clase para almacenar los mapas de registros de un dispositivo ModBus
    """

    def __init__(self, map_id: str):
        self.map_id = map_id
        # Se carga el diccionario con el mapa de registros del dispositivo
        print(f"(devices.ModbusRegisterMap) - Cargando mapa de registros {self.map_id}")
        self.rmap: [dict, None] = None  # Diccionario con el Mapa de registros

    def co(self):
        """
        Returns: Devuelve un diccionario con las direcciones de registros Coil, si existen
        None si no hay registros tipo Coil
        """
        return self.rmap.get(MODBUS_DATATYPES_KEYS[COIL_ID])

    def di(self):
        """
        Returns: Devuelve un diccionario con las direcciones de registros Discrete Input, si existen
        None si no hay registros tipo Discrete Input
        """
        return self.rmap.get(MODBUS_DATATYPES_KEYS[DISCRETE_INPUT_ID])

    def hr(self):
        """
        Returns: Devuelve un diccionario con las direcciones de registros Holding Register, si existen
        None si no hay registros tipo Holding Register
        """
        return self.rmap.get(MODBUS_DATATYPES_KEYS[HOLDING_REGISTER_ID])

    def ir(self):
        """
        Returns: Devuelve un diccionario con las direcciones de registros Input Register, si existen
        None si no hay registros tipo Input Register
        """
        return self.rmap.get(MODBUS_DATATYPES_KEYS[INPUT_REGISTER_ID])

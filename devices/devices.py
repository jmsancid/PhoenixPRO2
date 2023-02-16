#!/usr/bin/env python3
from typing import Union, List, Tuple, Dict, Any
import serial
import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
from modbus_tk.modbus import ModbusError
from dataclasses import dataclass
from datetime import datetime
import math
import phoenix_constants as cte


@dataclass
class MBDevice:
    port: Union[None, str] = None  # Puerto de comunicaciones
    name: Union[None, str] = ""  # Descripción del dispositivo en el proyecto
    slave: Union[None, int] = None  # Dirección en en el ModBus
    baudrate: int = 9600
    databits: int = 8
    parity: Union[str, int] = cte.PARITY_EVEN  # Por defecto, paridad PAR
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

            print(f'{datetime.now()} - Estado puerto serie {self.port}: {["cerrado", "abierto"][serport.is_open]}')
            # serport.flush()
            self.conn = modbus_rtu.RtuMaster(serport)
            self.conn.set_timeout(1)
            self.conn.set_verbose(True)

            print(f'{str(datetime.now())} - Conexión realizada con el puerto {self.port}')
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
            qreadings = math.ceil(quan / self.qregsmax)  # Calculo el número de lecturas que es necesario hacer
            for i in range(qreadings):
                init_adr = adr + i * self.qregsmax
                partial_quan = self.qregsmax if (i + 1) * self.qregsmax < quan else quan - i * self.qregsmax
                readings.append((init_adr, partial_quan))
        else:
            readings = [(adr, quan)]
        total_readings = []
        try:
            self.conn = await self.connect()
            for reading in readings:
                if mbop not in [cst.READ_COILS,
                                cst.READ_DISCRETE_INPUTS,
                                cst.READ_HOLDING_REGISTERS,
                                cst.READ_INPUT_REGISTERS]:
                    print(f'Operación de lectura, {mbop}, no válida')
                    return
                print(f'{datetime.now()} -\tIntentando leer {reading[1]} registros desde el registro {reading[0]} '
                      f'del esclavo {self.slave} con la operación {mbop} en el puerto {self.port}')
                reading = self.conn.execute(self.slave, mbop, reading[0], reading[1])
                total_readings += reading
            return tuple(total_readings)
        except Exception as e:
            print(f'{str(datetime.now())} -\tNo se ha podido realizar la lectura de {quan} registros desde la '
                  f'dirección {adr} del esclavo {self.slave} con la operación {mbop} en el puerto {self.port}\n{e}')
            return
        finally:
            self.conn.close()

    async def write(self, mbop: int, adr: int, *output_value: Union[int, Tuple[int], List[int]]):

        # Compruebo operaciones de escritura válidas definidas para el dispositivo
        if mbop not in self.write_ops:
            print(f'Operación de escritura, {mbop}, no válida')
            return

        # Compruebo si se han introducido valores a escribir:
        if not output_value:
            print('Escritura ModBus: No se han introducido valores a escribir')
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
        return self.rmap.get(cte.MODBUS_DATATYPES_KEYS[cte.COIL_ID])

    def di(self):
        """
        Returns: Devuelve un diccionario con las direcciones de registros Discrete Input, si existen
        None si no hay registros tipo Discrete Input
        """
        return self.rmap.get(cte.MODBUS_DATATYPES_KEYS[cte.DISCRETE_INPUT_ID])

    def hr(self):
        """
        Returns: Devuelve un diccionario con las direcciones de registros Holding Register, si existen
        None si no hay registros tipo Holding Register
        """
        return self.rmap.get(cte.MODBUS_DATATYPES_KEYS[cte.HOLDING_REGISTER_ID])

    def ir(self):
        """
        Returns: Devuelve un diccionario con las direcciones de registros Input Register, si existen
        None si no hay registros tipo Input Register
        """
        return self.rmap.get(cte.MODBUS_DATATYPES_KEYS[cte.INPUT_REGISTER_ID])


class Generator(MBDevice):
    """
    Generador sistema Phoenix
    Params:
    device: dispositivo ModBus con el mapa de registros a mapear para las operaciones con
    los generadores
    on_info: lista con el tipo de registro, la dirección del registro modbus y el valor
    para poner en ON el generador
    off_info: Ídem anterior para poner el generador en OFF
    demanda_info: Ídem para leer demanda en el generador
    sp_info: registro en el que escribir la consigna de impulsión de agua
    iv_info: Lista con el tipo de registro, la dirección del registro Modbus y los valores
    para poner el generador en modo Calefacción o Refrigeración
    alarm_info: Diccionario con el tipo de registro, la dirección del registro ModBus y los valores
    de alarma del Generador
    """

    def __init__(self, name="", groups=None, brand="", model="",
                 on_info: [List, None] = None,
                 off_info: [List, None] = None,
                 demanda_info: [List, None] = None,
                 sp_info: [List, None] = None,
                 iv_info: [List, None] = None,
                 alarm_info: [Dict, None] = None):
        super().__init__()
        if alarm_info is None:
            alarm_info = {}
        if groups is None:
            groups = []
        self.name = name
        self.groups = groups
        self.brand = brand
        self.model = model
        self.on_info = on_info
        self.off_info = off_info
        self.demanda_info = demanda_info
        self.sp_info = sp_info
        self.iv_info = iv_info
        self.alarm_info = alarm_info

    def read(self, datatype, adr, qregs):
        """
        TODO Eliminar este método cuando el generador exista realmente. Este método se ha creado para pruebas
        """
        msg = f"""Leyendo {qregs} registros de tipo {cte.MODBUS_DATATYPES.get(datatype)} empezando en el registro 
        {adr} en el generador {self.name} (esclavo {self.slave})"""
        print(msg)
        return

    def write(self, datatype, adr, value):
        """
        TODO Eliminar este método cuando el generador exista realmente. Este método se ha creado para pruebas
        """
        msg = f"""Escribiendo el valor {value} en el {cte.MODBUS_DATATYPES.get(datatype)} {adr} 
        del generador {self.name} (esclavo {self.slave})"""
        print(msg)
        return


class RoomSensor(MBDevice):
    def __init__(self, name="", groups=None, brand="", model=""):
        super().__init__()
        if groups is None:
            groups = []
        self.name = name
        self.groups = groups
        self.brand = brand
        self.model = model
        # print(f"Instanciando objeto Sensor {self.name}")


class Fancoil(MBDevice):
    pass


class Split(MBDevice):
    pass


class HeatRecoveryUnit(MBDevice):
    pass


class AirZoneManager(MBDevice):
    pass

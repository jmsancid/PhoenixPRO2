#!/usr/bin/env python3
import json

import phoenix_init as phi
from mb_utils.mb_utils import get_value, set_value
from regops.regops import set_hb, set_lb


class Generator(phi.MBDevice):
    """
    Generador sistema Phoenix
    NOTA: LOS ATRIBUTOS DE ESTA CLASE DEBEN COINCIDIR CON LAS CLAVES DEL JSON GENERATORS.JSON EN LA
    CARPETA DE PROJECT_ELEMENTS
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

    def __init__(self,
                 bus_id: str = "",
                 device_id: str = "",
                 name: str = "",
                 groups: [phi.List, None] = None,
                 brand: str = "",
                 model: str = "",
                 on_info: [phi.List, None] = None,
                 off_info: [phi.List, None] = None,
                 demanda_info: [phi.List, None] = None,
                 sp_info: [phi.List, None] = None,
                 iv_info: [phi.List, None] = None,
                 alarm_info: [phi.Dict, None] = None):
        super().__init__()
        if alarm_info is None:
            alarm_info = {}
        if groups is None:
            groups = []
        self.bus_id = bus_id
        self.device_id = device_id
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
        self.t_ext_info = None
        self.t_inercia = None
        self.water_flow_info = None
        self.energia_electrica_consumida = None
        self.energia_evaporacion_consumida = None
        self.energia_condensacion_consumida = None
        self.cop = None
        self.eer = None


class RoomSensor(phi.MBDevice):
    def __init__(self,
                 bus_id: str = "",
                 device_id: str = "",
                 name: str = "",
                 groups: [phi.List, None] = None,
                 brand: str = "",
                 model: str = ""):
        super().__init__()
        if groups is None:
            groups = []
        self.bus_id = bus_id
        self.device_id = device_id
        self.name = name
        self.groups = groups
        self.brand = brand
        self.model = model
        # print(f"Instanciando objeto Sensor {self.name}")

    async def update(self):
        """
        Todos los dispositivos deben disponer del método update para cuando se actualiza el bus
        :return:
        """
        pass

    def __repr__(self):
        """
        Representación del sensor
        :return:
        """
        dev_info = f"Sensor de habitación {self.name}"
        return dev_info


class Fancoil(phi.MBDevice):
    pass


class Split(phi.MBDevice):
    pass


class HeatRecoveryUnit(phi.MBDevice):
    pass


class AirZoneManager(phi.MBDevice):
    pass


class TempFluidController(phi.MBDevice):
    """
    Controlador de temperatura de impulsión sistema Phoenix.
    Dispositivo especial SIG610
    NOTA: LOS ATRIBUTOS DE ESTA CLASE DEBEN COINCIDIR CON LAS CLAVES DEL JSON TEMPFLUIDCONTROLLERS.JSON EN LA
    CARPETA DE PROJECT_ELEMENTS.
    Puede controlar hasta 3 circuitos de climatización.
    Cada circuito estará asociado a un grupo de habitaciones.
    Al actualizar el controlador se propaga la consigna calculada para cada grupo de habitaciones al circuito
    correspondiente, así como su modo de funcionamiento calefacción/refrigeración.
    Las temperaturas de impulsión de cada circuito se leen con los métodos wt1, wt2 y wt3 para los circuitos
    1, 2 y 3 respectivamente.
    Params:
    device: dispositivo ModBus con el mapa de registros a mapear para las operaciones con el controlador SIG610.
    groups: grupos de habitaciones vinculados al dispositivo. Puede haber hasta 3 grupos. El primer grupo
    se asocia al circuito 1, el segundo al circuito 2 y el tercero al circuito 3.
    """

    def __init__(self,
                 bus_id: str = "",
                 device_id: str = "",
                 name: str = "",
                 groups: [phi.List, None] = None,
                 brand: str = "",
                 model: str = ""):
        super().__init__()
        if groups is None:
            groups = []
        self.bus_id = bus_id
        self.device_id = device_id
        self.name = name
        self.groups = groups
        self.brand = brand
        self.model = model
        self.st1_source = None  # Marcha/Paro bomba circuladora circuito 1
        self.iv1_source = None  # Modo de funcionamiento calefacción/refrigeración circuito 1
        self.sp1_source = None  # Consigna de impulsión circuito 1
        self.ti1_source = None  # Temperatura de impulsión circuito 1
        self.v1_source = None  # % Apertura válvula circuito 1
        self.st2_source = None  # Marcha/Paro bomba circuladora circuito 2
        self.iv2_source = None  # Modo de funcionamiento calefacción/refrigeración circuito 2
        self.sp2_source = None  # Consigna de impulsión circuito 2
        self.ti2_source = None  # Temperatura de impulsión circuito 2
        self.v2_source = None  # % Apertura válvula circuito 2
        self.st3_source = None  # Marcha/Paro bomba circuladora circuito 3
        self.iv3_source = None  # Modo de funcionamiento calefacción/refrigeración circuito 3
        self.sp3_source = None  # Consigna de impulsión circuito 3
        self.ti3_source = None  # Temperatura de impulsión circuito 3
        self.v3_source = None  # % Apertura válvula circuito 3
        self.st4_source = None  # Salida digital 4

    def get_st1(self):
        """
        Devuelve el estado de la bomba circuladora del circuito 1
        Returns: estado de la bomba circuladora del circuito 1
        """
        if self.st1_source is None:
            return
        datatype = self.st1_source[0]
        adr = self.st1_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        st = get_value(value_source=source)
        return st

    async def set_st1(self, new_st_value: int):
        """
        Arranca o para la bomba circuladora del circuito 1
        Returns: Resultado del proceso de escritura ModBus
        """
        if self.st1_source is None:
            return
        datatype = self.st1_source[0]
        adr = self.st1_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        if new_st_value not in [0, 1]:
            print(f"{self.name}: Error accionando la bomba del circuito 1 con el valor {new_st_value}")
            return
        res = await set_value(target, new_st_value)
        return res

    def get_iv1(self):
        """
        Devuelve el modo de funcionamiento del circuito de impulsión 1
        Returns: modo de funcionamiento, Calefacción/Refrigeración del circuito de impulsión 1
        0: Off
        1: Refrigeración
        2: Calefacción
        """
        if self.iv1_source is None:
            return
        datatype = self.iv1_source[0]
        adr = self.iv1_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        iv_sp = get_value(value_source=source)  # El SIG610 almacena consigna en byte bajo y modo en byte alto
        if iv_sp is not None:
            iv, sp = iv_sp
            return iv
        return

    async def set_iv1(self, new_iv_value: int):
        """
        Fija el modo de funcionamiento, Off/Calefacción/Refrigeración del circuito de impulsión 'circuito_id'
        Se escribe en el byte alto del registro correspondiente a 'circuito_id'
        Returns: Resultado del proceso de escritura ModBus
        """
        if self.iv1_source is None:
            return
        datatype = self.iv1_source[0]
        adr = self.iv1_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        if new_iv_value not in [0, 1, 2]:
            print(f"{self.name}: Error escribiendo el modo de funcionamiento {new_iv_value} para "
                  f"el circuito 1")
            return
        # Recojo el valor actual del registro a actualizar
        current_mode, current_value = get_value(target)  # con el SIG610, get_value devuelve una tupla con modo de
        # funcionamiento y la consigna
        # Actualizo el valor del modo de funcionamiento (byte alto)
        new_val = set_hb(current_value, int(new_iv_value))
        res = await set_value(target, new_val)
        return res

    def get_sp1(self):
        """
        Devuelve la consigna del circuito de impulsión 1
        Returns: consigna del circuito de impulsión 1
        """
        if self.sp1_source is None:
            return
        datatype = self.sp1_source[0]
        adr = self.sp1_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        iv_sp = get_value(value_source=source)  # El SIG610 almacena consigna en byte bajo y modo en byte alto
        if iv_sp is not None:
            iv, sp = iv_sp
            return sp
        return

    async def set_sp1(self, new_sp_value: int):
        """
        Fija la consigna de impulsión del circuito de impulsión 1
        Se escribe en el byte bajo del registro correspondiente al circuito 1
        Returns: Resultado del proceso de escritura ModBus
        """
        if self.sp1_source is None:
            return
        datatype = self.sp1_source[0]
        adr = self.sp1_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        if 55 < new_sp_value < 5:
            print(f"{self.name}: Error escribiendo la consigna {new_sp_value} para el circuito 1")
            return
        # Recojo el valor actual del registro a actualizar
        current_mode, current_value = get_value(target)  # con el SIG610, get_value devuelve una tupla con modo de
        # funcionamiento y la consigna
        # Actualizo el valor del setpoint (byte bajo)
        new_val = set_lb(current_value, int(new_sp_value))
        res = await set_value(target, new_val)  # Escritura en el dispositivo ModBus
        return res

    def get_st2(self):
        """
        Devuelve el estado de la bomba circuladora del circuito 2
        Returns: estado de la bomba circuladora del circuito 2
        """
        if self.st2_source is None:
            return
        datatype = self.st2_source[0]
        adr = self.st2_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        st = get_value(value_source=source)
        return st

    async def set_st2(self, new_st_value: int):
        """
        Arranca o para la bomba circuladora del circuito 2
        Returns: Resultado del proceso de escritura ModBus
        """
        if self.st2_source is None:
            return
        datatype = self.st2_source[0]
        adr = self.st2_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        if new_st_value not in [0, 1]:
            print(f"{self.name}: Error accionando la bomba del circuito 2 con el valor {new_st_value}")
            return
        res = await set_value(target, new_st_value)
        return res

    def get_iv2(self):
        """
        Devuelve el modo de funcionamiento del circuito de impulsión 2
        Returns: modo de funcionamiento, Calefacción/Refrigeración del circuito de impulsión 2
        0: Off
        1: Refrigeración
        2: Calefacción
        """
        if self.iv2_source is None:
            return
        datatype = self.iv2_source[0]
        adr = self.iv2_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        iv_sp = get_value(value_source=source)  # El SIG610 almacena consigna en byte bajo y modo en byte alto
        if iv_sp is not None:
            iv, sp = iv_sp
            return iv
        return

    async def set_iv2(self, new_iv_value: int):
        """
        Fija el modo de funcionamiento, Off/Calefacción/Refrigeración del circuito de impulsión 2
        Se escribe en el byte alto del registro correspondiente al circuito 2
        Returns: Resultado del proceso de escritura ModBus
        """
        if self.iv2_source is None:
            return
        datatype = self.iv2_source[0]
        adr = self.iv2_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        if new_iv_value not in [0, 1, 2]:
            print(f"{self.name}: Error escribiendo el modo de funcionamiento {new_iv_value} para "
                  f"el circuito 2")
            return
        # Recojo el valor actual del registro a actualizar
        current_mode, current_value = get_value(target)  # con el SIG610, get_value devuelve una tupla con modo de
        # funcionamiento y la consigna
        # Actualizo el valor del modo de funcionamiento (byte alto)
        new_val = set_hb(current_value, int(new_iv_value))
        res = await set_value(target, new_val)
        return res

    def get_sp2(self):
        """
        Devuelve la consigna del circuito de impulsión 2
        Returns: consigna del circuito de impulsión 2
        """
        if self.sp2_source is None:
            return
        datatype = self.sp2_source[0]
        adr = self.sp2_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        iv_sp = get_value(value_source=source)  # El SIG610 almacena consigna en byte bajo y modo en byte alto
        if iv_sp is not None:
            iv, sp = iv_sp
            return sp
        return

    async def set_sp2(self, new_sp_value: int):
        """
        Fija la consigna de impulsión del circuito de impulsión 2
        Se escribe en el byte bajo del registro correspondiente al circuito 2
        Returns: Resultado del proceso de escritura ModBus
        """
        if self.sp2_source is None:
            return
        datatype = self.sp2_source[0]
        adr = self.sp2_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        if 55 < new_sp_value < 5:
            print(f"{self.name}: Error escribiendo la consigna {new_sp_value} para el circuito 2")
            return
        # Recojo el valor actual del registro a actualizar
        current_mode, current_value = get_value(target)  # con el SIG610, get_value devuelve una tupla con modo de
        # funcionamiento y la consigna
        # Actualizo el valor del setpoint (byte bajo)
        new_val = set_lb(current_value, int(new_sp_value))
        res = await set_value(target, new_val)  # Escritura en el dispositivo ModBus
        return res

    def get_st3(self):
        """
        Devuelve el estado de la bomba circuladora del circuito 3
        Returns: estado de la bomba circuladora del circuito 3
        """
        if self.st3_source is None:
            return
        datatype = self.st3_source[0]
        adr = self.st3_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        st = get_value(value_source=source)
        return st

    async def set_st3(self, new_st_value: int):
        """
        Arranca o para la bomba circuladora del circuito 3
        Returns: Resultado del proceso de escritura ModBus
        """
        if self.st3_source is None:
            return
        datatype = self.st3_source[0]
        adr = self.st3_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        if new_st_value not in [0, 1]:
            print(f"{self.name}: Error accionando la bomba del circuito 3 con el valor {new_st_value}")
            return
        res = await set_value(target, new_st_value)
        return res

    def get_iv3(self):
        """
        Devuelve el modo de funcionamiento del circuito de impulsión 3
        Returns: modo de funcionamiento, Calefacción/Refrigeración del circuito de impulsión 3
        0: Off
        1: Refrigeración
        2: Calefacción
        """
        if self.iv3_source is None:
            return
        datatype = self.iv3_source[0]
        adr = self.iv3_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        iv_sp = get_value(value_source=source)  # El SIG610 almacena consigna en byte bajo y modo en byte alto
        if iv_sp is not None:
            iv, sp = iv_sp
            return iv
        return

    async def set_iv3(self, new_iv_value: int):
        """
        Fija el modo de funcionamiento, Off/Calefacción/Refrigeración del circuito de impulsión 3
        Se escribe en el byte alto del registro correspondiente al circuito 3
        Returns: Resultado del proceso de escritura ModBus
        """
        if self.iv3_source is None:
            return
        datatype = self.iv3_source[0]
        adr = self.iv3_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        if new_iv_value not in [0, 1, 2]:
            print(f"{self.name}: Error escribiendo el modo de funcionamiento {new_iv_value} para "
                  f"el circuito 3")
            return
        # Recojo el valor actual del registro a actualizar
        current_mode, current_value = get_value(target)  # con el SIG610, get_value devuelve una tupla con modo de
        # funcionamiento y la consigna
        # Actualizo el valor del modo de funcionamiento (byte alto)
        new_val = set_hb(current_value, int(new_iv_value))
        res = await set_value(target, new_val)
        return res

    def get_sp3(self):
        """
        Devuelve la consigna del circuito de impulsión 3
        Returns: consigna del circuito de impulsión 3
        """
        if self.sp3_source is None:
            return
        datatype = self.sp3_source[0]
        adr = self.sp3_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        iv_sp = get_value(value_source=source)  # El SIG610 almacena consigna en byte bajo y modo en byte alto
        if iv_sp is not None:
            iv, sp = iv_sp
            return sp
        return

    async def set_sp3(self, new_sp_value: int):
        """
        Fija la consigna de impulsión del circuito de impulsión 3
        Se escribe en el byte bajo del registro correspondiente al circuito 3
        Returns: Resultado del proceso de escritura ModBus
        """
        if self.sp3_source is None:
            return
        datatype = self.sp3_source[0]
        adr = self.sp3_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        if 55 < new_sp_value < 5:
            print(f"{self.name}: Error escribiendo la consigna {new_sp_value} para el circuito 3")
            return
        # Recojo el valor actual del registro a actualizar
        current_mode, current_value = get_value(target)  # con el SIG610, get_value devuelve una tupla con modo de
        # funcionamiento y la consigna
        # Actualizo el valor del setpoint (byte bajo)
        new_val = set_lb(current_value, int(new_sp_value))
        res = await set_value(target, new_val)  # Escritura en el dispositivo ModBus
        return res

    def get_ti1(self):
        """
        Devuelve la temperatura de impulsión del circuito 1
        Returns: temperatura de impulsión del circuito 1
        """
        if self.ti1_source is None:
            return
        datatype = self.ti1_source[0]
        adr = self.ti1_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        ti = get_value(value_source=source)
        return ti

    def get_v1(self):
        """
        Devuelve el estado de apertura de la válvula del circuito 1
        Returns: estado de apertura de la válvula del circuito 1
        """
        if self.v1_source is None:
            return
        datatype = self.v1_source[0]
        adr = self.v1_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        pct_valv = get_value(value_source=source)
        return pct_valv

    def get_ti2(self):
        """
        Devuelve la temperatura de impulsión del circuito 2
        Returns: temperatura de impulsión del circuito 2
        """
        if self.ti2_source is None:
            return
        datatype = self.ti2_source[0]
        adr = self.ti2_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        ti = get_value(value_source=source)
        return ti

    def get_v2(self):
        """
        Devuelve el estado de apertura de la válvula del circuito 2
        Returns: estado de apertura de la válvula del circuito 2
        """
        if self.v2_source is None:
            return
        datatype = self.v2_source[0]
        adr = self.v2_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        pct_valv = get_value(value_source=source)
        return pct_valv

    def get_ti3(self):
        """
        Devuelve la temperatura de impulsión del circuito 3
        Returns: temperatura de impulsión del circuito 3
        """
        if self.ti3_source is None:
            return
        datatype = self.ti3_source[0]
        adr = self.ti3_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        ti = get_value(value_source=source)
        return ti

    def get_v3(self):
        """
        Devuelve el estado de apertura de la válvula del circuito 3
        Returns: estado de apertura de la válvula del circuito 3
        """
        if self.v3_source is None:
            return
        datatype = self.v3_source[0]
        adr = self.v3_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        pct_valv = get_value(value_source=source)
        return pct_valv

    def get_st4(self):
        """
        Devuelve el estado de la salida digital 4 del controlador SIG610
        Returns: estado de la salida digital 4 del controlador SIG610
        """
        if self.st4_source is None:
            return
        datatype = self.st4_source[0]
        adr = self.st4_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        st = get_value(value_source=source)
        return st

    async def update(self):
        """
        Propaga a cada circuito, el modo de funcionamiento, el estado on/off y la consigna de cada uno
        de los grupos de habitaciones.
        Returns: resultado de la escritura modbus de los valores actualizados
        """
        set_st = {0: self.set_st1, 1: self.set_st2, 2: self.set_st3}
        set_iv = {0: self.set_iv1, 1: self.set_iv2, 2: self.set_iv3}
        set_sp = {0: self.set_sp1, 1: self.set_sp2, 2: self.set_sp3}
        with open(phi.ROOMGROUPS_VALUES_FILE, "r") as f:
            roomgroups_values = json.load(f)

        for idx, roomgroup_id in enumerate(self.groups):
            roomgroup = roomgroups_values.get(roomgroup_id)  # Objeto del grupo RoomGroup
            if roomgroup is None:
                continue
            if roomgroup.get("demanda") != 0:
                # Hay demanda de refrigeración (demanda = 1) o de calefacción (demanda = 2). Se propaga el modo iv
                iv = 1 if roomgroup.iv else 2  # roomgroup.iv es booleana. True/1 en refrigeración
                # Se arranca la bomba circuladora
                update_st = set_st.get(idx)(1)
            else:
                iv = 0
                # Se para la bomba circuladora
                update_st = await set_st.get(idx)(0)
            update_iv = await set_iv.get(idx)(iv)  # Se actualiza el modo de funcionamiento al dispositivo
            sp = int(roomgroup.get("water_sp"))  # water sp es float, pero en el dispositivo se escribe un int
            update_sp = await set_sp.get(idx)(sp)

            return update_iv, update_sp, update_st

    def __repr__(self):
        """
        Para imprimir los valores de los 3 circuitos de impulsión
        :return:
        """
        get_st = {0: self.get_st1, 1: self.get_st2, 2: self.get_st3, 3: self.get_st4}
        get_iv = {0: self.get_iv1, 1: self.get_iv2, 2: self.get_iv3}
        get_sp = {0: self.get_sp1, 1: self.get_sp2, 2: self.get_sp3}
        get_ti = {0: self.get_ti1, 1: self.get_ti2, 2: self.get_ti3}
        get_v = {0: self.get_v1, 1: self.get_v2, 2: self.get_v3}
        onoff = {0: "Parada", 1: "En Marcha"}
        activada = {0: "Desactivada", 1: "Activada"}
        modo = {0: "Circuito parado", 1: "Refrigeración", 2: "Calefacción"}
        dev_info = ""

        for cto in range(3):
            st = get_st.get(cto)()
            iv = get_iv.get(cto)()
            sp = get_sp.get(cto)()
            ti = get_ti.get(cto)()
            valv = get_v.get(cto)()
            if any([st is None, iv is None, sp is None, ti is None]):
                # No hay datos registrados del dispositivo
                return f"{self.name} - No hay datos"
            dev_info += f"\nCIRCUITO {cto + 1}"
            dev_info += f"\n=========="
            dev_info += f"\n\tEstado bomba: {onoff.get(st)}"
            dev_info += f"\n\tEstado modo de funcionamiento: {modo.get(iv)}"
            dev_info += f"\n\tConsigna de impulusión: {sp} ºC"
            dev_info += f"\n\tTemperatura de impulusión: {ti} ºC"
            dev_info += f"\n\tApertura válvula: {valv}%"

        dev_info += f"\n\nEstado salida digital 4 {activada.get(get_st.get(3)())}"
        return dev_info


# DICCIONARIO CON LAS CLASES DEL SISTEMA
SYSTEM_CLASSES = {
    "mbdevice": phi.MBDevice,
    "modbusregistermap": phi.ModbusRegisterMap,
    "sensor": RoomSensor,
    "tempfluidcontroller": TempFluidController,
    "generator": Generator,
    "fancoil": Fancoil,
    "split": Split,
    "heatrecoveryunit": HeatRecoveryUnit,
    "airzonemanager": AirZoneManager
}

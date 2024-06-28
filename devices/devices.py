#!/usr/bin/env python3
import json
from bisect import bisect

import phoenix_init as phi
from mb_utils.mb_utils import get_value, save_value, set_value, get_h, get_dp, get_roomgroup_values, \
    update_xch_files_from_devices, get_regmap, check_changes_from_web, get_all_fancoils_st, get_all_ufhc_actuators_st 
from regops.regops import set_hb, set_lb
from project_elements.building import get_temp_exterior, get_hrel_exterior, get_h_exterior, get_modo_iv


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
        self.onoff_source = None
        self.onoff_st = None  # O: Parado / 1: Marcha. Se mapean los valores On/Off del generador
        self.on_value = None
        self.off_value = None
        self.manual_onoff_mode = 1  # Si vale 0, la bomba de calor puede arrancarse desde la Web
        self.manual_onoff = self.on_value  # Valor onoff cuando se activa el onoff manual, leído desde la web
        self.demanda_source = None
        self.sp_source = None
        self.sp = None  # Consigna de impulsión de agua
        self.manual_sp_mode = 0  # Modo manual de selección de la consigna de impulsión del generador
        self.manual_sp = None  # Valor manual de la consigna de impulsión del generador, leída desde la web
        self.dwh_temp_source = None
        self.dhw_sp = None  # Consigna ACS
        self.dhw_t = None  # Temperatura depósito ACS
        self.iv_source = None  # Registro para leer el modo actual de funcionamiento, calefacción o refrigeración
        self.iv_target = None  # Registro para fijar el modo actual de funcionamiento, calefacción o refrigeración
        self.heating_value = None  # Valor para pasar el generador a calefacción en iv_target
        self.cooling_value = None  # Valor para pasar el generador a refrigeración en iv_target
        self.iv = None  # Modo de funcionamiento del sistema Phoenix (calefacción: 0 o refrigeración: 1)
        self.manual_iv_mode = 1  # Si vale 0, el modo calefacción refrigereación de la bomba de calor puede fijarse
        # en la Web
        self.manual_iv = self.heating_value  # Valor manual del modo calefacción/refrigeración. Inicia en calefacción
        self.alarm_source = None
        self.alarm = None
        self.t_ext_source = None
        self.t_ext = None
        self.supply_water_temp_source = None
        self.supply_water_temp = None
        self.return_water_temp_source = None
        self.return_water_temp = None
        self.t_inercia_source = None
        self.t_inercia = None
        self.water_flow_source = None
        self.water_flow = None
        self.eelectrica_consumida_source = None
        self.eelectrica_consumida = None
        self.ecooling_consumida_source = None
        self.ecooling_consumida = None
        self.eheating_consumida_source = None
        self.eheating_consumida = None
        self.edhw_consumida_source = None
        self.edhw_consumida = None
        self.cop_source = None
        self.cop = None
        self.eer_source = None
        self.eer = None

    async def onoff(self, new_st_value: [int, None] = None):
        """
        Arranca o para la bomba de calor si existe new_st_value.
        Si no, devuelve el estado de la bomba de calor
        Param:
            new_st_value: Nuevo estado para la bomba de calor: 0:Parada / 1:En Marcha
        Returns: Estado de la bomba de calor'
        """
        if self.onoff_source is None:
            return
        datatype = self.onoff_source[0]
        adr = self.onoff_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_st = get_value(target)
        if current_st == self.on_value:
            self.onoff_st = phi.ON
        elif current_st == self.off_value:
            self.onoff_st = phi.OFF
        else:
            print(f"ERROR {__file__} - Posible error de definición de los valores de On y Off "
                  f"para {self.name}. Ver JSON {self.brand}-{self.model}.JSON")
            return
        if new_st_value is not None:
            if new_st_value not in [phi.OFF, phi.ON]:
                print(f"{self.name}: Error accionando la bomba de calor {self.name} con el valor {new_st_value}")
            else:
                gen_onoff_value = self.on_value if new_st_value == phi.ON else self.off_value
                res = await set_value(target, gen_onoff_value)
                dbval = save_value(target, gen_onoff_value)
                self.onoff_st = new_st_value

        return self.onoff_st

    async def set_manual_onoff(self):
        """
        Aplica al generador el valor del atributo manual_onoff
        Returns:

        """
        if self.manual_onoff_mode and self.manual_onoff is not None:
            operations = ("Apagando", "Encendiendo")
            print(f"{operations[self.manual_onoff]} MANUALMENTE el generador {self.name}")
            await self.onoff(self.manual_onoff)
            return 1
        return 0

    async def iv_mode(self, new_iv_mode: [int, None] = None):
        """
        Fija el modo iv del generador.
        EN PHOENIX MODO CALEFACCIÓN=0 Y MODO REFRIGERACIÓN=1.
        EN ECODAN, POR EJEMPLO, CALEFACCIÓN=1 (self.heating_value) / REFRIGERACIÓN = 3 (self.cooling_value)
        Hay que mapear los valores de calefacción y refrigeración del generador con dichos valores y tenerlo
        en cuenta a la hora de escribirlos en el generador.
        Si new_iv_mode es None, devuelve el modo actual
        Param:
            new_iv_mode: modo calefacción (0)/ refrigeración (1) a establecer
        Returns:
             Modo calefacción / refrigeración actual
        """
        if self.iv_source is None:
            return

        datatype = self.iv_source[0]
        adr = self.iv_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_iv_mode = get_value(source)  # Valor del modo IV en el generador. No confundir con el modo IV del
        # sistema ya que podrían tener distintos valores.
        print(f"Valor actual IV en la ecodan: {current_iv_mode} - {type(current_iv_mode)}")
        print(f"Valor actual modo refr en la ecodan: {self.cooling_value} - {type(self.cooling_value)}")
        print(f"Valor actual modo calef en la ecodan: {self.heating_value} - {type(self.heating_value)}")
        if current_iv_mode is None:  # No se ha leído el modo de funcionamiento
            return
        if current_iv_mode == self.cooling_value:
            self.iv = phi.COOLING
        elif current_iv_mode == self.heating_value:
            self.iv = phi.HEATING
        else:
            print(f"ERROR {__file__} - Posible error de definición de los valores de calefacción o refrigeración "
                  f"en {self.name}. Ver JSON {self.brand}-{self.model}.JSON")
        iv_set_datatype = self.iv_target[0]
        iv_set_adr = self.iv_target[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": iv_set_datatype,
                  "adr": iv_set_adr}
        if new_iv_mode is None:
            return self.iv
        elif new_iv_mode == phi.HEATING:
            res = await set_value(target, self.heating_value)
            self.iv = phi.HEATING
        elif new_iv_mode == phi.COOLING:
            res = await set_value(target, self.cooling_value)
            self.iv = phi.COOLING
        else:
            print(f"ERROR {__file__}\n\tValor no válido, {new_iv_mode}, para modo Calefacción/Refrigeración "
                  f"en {self.name}. Ver JSON {self.brand}-{self.model}.JSON")
            # self.iv = current_iv_mode
            self.iv = phi.system_iv
        dbval = save_value(target, self.iv)
        return self.iv

    async def set_manual_iv(self):
        """
        Aplica al generador el valor del atributo manual_iv
        Returns:

        """
        if self.manual_iv_mode and self.manual_iv is not None:
            operations = ("Calefaccion", "Refrigeracion")
            print(f"Activando {operations[self.manual_iv]} MANUALMENTE en el generador {self.name}")
            await self.iv_mode(self.manual_iv)
            return 1
        return 0

    async def set_sp(self, new_sp: [int, float, None] = None) -> [int, None]:
        """
        TODO Asociar consigna al grupo de habitaciones + definir consigna ACS + definir consign manual generador
        Fija la consigna de impulsión de agua calculada para el grupo de habitaciones asocado al generador
        Param:
            new_sp: consigna de temperatura de impulsión para el generador
        Returns: Consigna de control de temperatura de impulsión de agua de la bomba de calor
        """
        sp_source = self.sp_source
        if sp_source is None:
            return
        datatype = sp_source[0]
        adr = sp_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_sp = get_value(value_source=source)
        setattr(self, "sp", current_sp)
        print(f"CAMARINES ECODAN UPDATE. Consigna actual: {self.sp} / {current_sp}")

        if not new_sp is None:
            if new_sp > phi.TMAX_IMPUL_CALEF or new_sp < phi.TMIN_IMPUL_REFR:
                print(f"{self.name}: Error escribiendo la consigna {new_sp} para el generador {self.name}.\n"
                      f"Está fuera de los límites [{phi.TMIN_IMPUL_REFR} - {phi.TMAX_IMPUL_CALEF}]")
                # Se limita a la temperatura máxima en calefacción y a la mínima en refrigeración
                self.sp = phi.TMAX_IMPUL_CALEF if self.iv == phi.HEATING else phi.TMIN_IMPUL_REFR
            else:
                # Se propaga la nueva consigna en el byte bajo
                res = await set_value(source, new_sp)  # Escritura Modbus
                self.sp = new_sp
            dbval = save_value(source, self.sp)

        return self.sp

    async def set_manual_sp(self):
        """
        Aplica al generador el valor del atributo manual_sp
        Returns:

        """
        if self.manual_sp_mode and self.manual_sp is not None:
            print(f"Aplicando la consigna {self.manual_sp} MANUALMENTE en el generador {self.name}")
            await self.set_sp(self.manual_sp)
            return 1
        return 0

    async def set_dhwsp(self, new_dhwsp: [int, None] = None) -> [int, None]:
        """
        Fija la consigna de temperatura del ACS en el generador
        Param:
            new_sp: consigna de producción de ACS
        Returns: Consigna de ACS de la bomba de calor
        """
        dhwsp_source = self.dwh_temp_source
        if dhwsp_source is None:
            return
        datatype = dhwsp_source[0]
        adr = dhwsp_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_dhwsp = get_value(value_source=source)

        if new_dhwsp is not None:
            if new_dhwsp > phi.TMAX_ACS:
                print(f"{self.name}: Error escribiendo la consigna de ACS {new_dhwsp} para el generador {self.name}.\n"
                      f"Está fuera del límite {phi.TMAX_ACS}.")
                # Se limita a la temperatura máxima en calefacción y a la mínima en refrigeración
                self.dhw_sp = phi.TMAX_ACS
            else:
                # Se propaga la nueva consigna en el byte bajo
                res = await set_value(source, new_dhwsp)  # Escritura Modbus
                self.dhw_sp = new_dhwsp
        else:
            self.dhw_sp = current_dhwsp

        dbval = save_value(source, self.dhw_sp)  # Se actualiza la base de datos

        return self.dhw_sp

    async def get_generator_info(self):
        """
        Devuelve información del generador asociada a los atributos definidos: temperatura exterior, temperatura
        de impulsión, consumos, COP, EER, etc.
        Param:
        Returns:  1 si la información se recoge satisfactoriamente
        """
        # Atributos con información de la bomba de calor. La clave es el origen ModBus y el valor es el nombre del
        # atributo que almacena la información extraída desde la clave
        info_attributes = {
            "alarm_source": "alarm",
            "t_ext_source": "t_ext",
            "supply_water_temp_source": "supply_water_temp",
            "return_water_temp_source": "return_water_temp",
            "t_inercia_source": "t_inercia",
            "water_flow_source": "water_flow",
            "eelectrica_consumida_source": "eelectrica_consumida",
            "ecooling_consumida_source": "ecooling_consumida",
            "eheating_consumida_source": "eheating_consumida",
            "edhw_consumida_source": "edhw_consumida",
            "cop_source": "cop",
            "eer_source": "eer"}

        for k, v in info_attributes.items():
            # attr_source = self.__getattribute__(k)
            attr_source = getattr(self, k)
            if attr_source is None or not attr_source:
                continue
            datatype = attr_source[0]
            adr = attr_source[1]
            source = {"bus": int(self.bus_id),
                      "device": int(self.device_id),
                      "datatype": datatype,
                      "adr": adr}
            current_attr_val = get_value(source)
            if current_attr_val is not None:
                # self.__setattr__(v, current_attr_val)
                setattr(self, v, current_attr_val)
                print(f"{self.name}. Valor de {v}:\t{current_attr_val}")
        return 1

    async def upload(self):
        """
        Escribe en el dispositivo ModBus los valores actuales de sus atributos tipo RW:
        "manual_onoff_mode", "manual_onoff", "manual_sp_mode", "manual_sp", "dhwsp", "manual_iv_mode", "manual_iv")
        :return:
        """
        await self.set_manual_onoff()
        await self.set_manual_iv()
        await self.set_manual_sp()
        await self.set_sp()
        await self.set_dhwsp(self.dhw_sp)
        return 1

    async def update(self):
        """
        Propaga al generador el modo de funcionamiento, el estado on/off y la consigna del grupo de habitaciones.
        Si la consigna manual está activada, se aplica el valor de la consigna manual.

        Returns: resultado de la escritura modbus de los valores actualizados o los valores manuales.
        """
        system_iv = await get_modo_iv()  # Modo frío=1 / calor=0 del sistema
        print(f"DEBUGGING {__file__} - Modo de funcionamiento del sistema asociado al "
              f"generador {self.name} = {system_iv}")

        if not self.groups:
            print(f"ERROR {__file__} - No se ha definido grupo de habitaciones para {self.name}")

        with open(phi.ROOMGROUPS_VALUES_FILE, "r") as f:
            roomgroups_values = json.load(f)

        roomgroup_id = self.groups[0]  # No puede asociarse más de 1 grupo de habitaciones al generador
        roomgroup = roomgroups_values.get(roomgroup_id)  # Objeto del grupo RoomGroup
        if roomgroup is None:
            print(f"ERROR {__file__} - El grupo de habitaciones {roomgroup_id} asociado {self.name} no "
                  f"tiene información")
            return
        group_supply_water_setpoint = roomgroup.get("water_sp")
        if self.manual_iv_mode:
            await self.iv_mode(self.manual_iv_mode)
        else:
            await self.iv_mode(system_iv)  # Se propaga el modo Frío/Calor del sistema al generador
        if self.manual_sp_mode:
            await self.set_sp(self.manual_sp)
        else:
            # Línea exclusiva para proyecto de Intecser - Camarines. Dejo la consigna que tiene la ECODAN
            if not "camarines" in phi.prj.get("name").lower():
                await self.set_sp(group_supply_water_setpoint)
            else:
                await self.set_sp()
                print(f"CAMARINES ECODAN UPDATE. Consigna actual: {self.sp}")
        if self.manual_onoff_mode:
            await self.onoff(self.manual_onoff)
        else:
            await self.onoff()

        await self.get_generator_info()

        await update_xch_files_from_devices(self)  # Guarda los valores del dispositivo en el archivo de intercambio
        # correspondiente

    def __repr__(self):
        """
        Para imprimir los valores de los 3 circuitos de impulsión
        :return:
        """
        onoff_values = {0: "Parada", 1: "En Marcha"}
        dev_info = ""

        st = onoff_values.get(self.onoff_st)
        iv = "Calefaccion" if self.iv == 0 else "Refrigeracion"
        sp = self.sp
        ti = self.supply_water_temp
        tr = self.return_water_temp
        alarm = self.alarm
        dev_info += f"\nGENERADOR {self.name}"
        dev_info += f"\n================================"
        dev_info += f"\n\tEstado generador: {st}"
        dev_info += f"\n\tModo de funcionamiento: {iv}"
        dev_info += f"\n\tConsigna de impulsión: {sp} ºC"
        dev_info += f"\n\tTemperatura de impulsión: {ti} ºC"
        dev_info += f"\n\tTemperatura de retorno: {tr} ºC"
        dev_info += f"\n\tAlarma: {alarm}"

        return dev_info


class UFHCController(phi.MBDevice):
    """
    Centralita Uponor para suelo radiante X148
    """
    # Lista de atributos por canales + cambio calefacción/refrigeración y estado de bomba
    # sp:consigna, rt:tª ambiente, rh:humedad relativa, ft:tª suelo, st:estado actuador,
    # coff:refrigeración habilitada
    attr_list = ('iv', 'pump',
                 'sp1', 'sp2', 'sp3', 'sp4', 'sp5', 'sp6', 'sp7', 'sp8', 'sp9', 'sp10', 'sp11', 'sp12',
                 'rt1', 'rt2', 'rt3', 'rt4', 'rt5', 'rt6', 'rt7', 'rt8', 'rt9', 'rt10', 'rt11', 'rt12',
                 'rh1', 'rh2', 'rh3', 'rh4', 'rh5', 'rh6', 'rh7', 'rh8', 'rh9', 'rh10', 'rh11', 'rh12',
                 'ft1', 'ft2', 'ft3', 'ft4', 'ft5', 'ft6', 'ft7', 'ft8', 'ft9', 'ft10', 'ft11', 'ft12',
                 'st1', 'st2', 'st3', 'st4', 'st5', 'st6', 'st7', 'st8', 'st9', 'st10', 'st11', 'st12',
                 'coff1', 'coff2', 'coff3', 'coff4', 'coff5', 'coff6', 'coff7', 'coff8', 'coff9',
                 'coff10', 'coff11', 'coff12',
                 'dp1', 'dp2', 'dp3', 'dp4', 'dp5', 'dp6', 'dp7', 'dp8', 'dp9', 'dp10', 'dp11', 'dp12',
                 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9', 'h10', 'h11', 'h12')

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
        for attr in self.attr_list:
            self.__setattr__(attr, None)
        self.active_channels = []  # Lista con los canales activos del controlador
        self.iv_source = None  # Origen del dato para el modo calefacción / refrigeración
        self.iv = None
        self.pump_source = None
        self.pump = None
        self.ch1_source = None
        self.ch1 = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}
        self.ch2_source = None
        self.ch2 = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}
        self.ch3_source = None
        self.ch3 = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}
        self.ch4_source = None
        self.ch4 = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}
        self.ch5_source = None
        self.ch5 = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}
        self.ch6_source = None
        self.ch6 = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}
        self.ch7_source = None
        self.ch7 = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}
        self.ch8_source = None
        self.ch8 = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}
        self.ch9_source = None
        self.ch9 = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}
        self.ch10_source = None
        self.ch10 = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}
        self.ch11_source = None
        self.ch11 = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}
        self.ch12_source = None
        self.ch12 = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}

    async def get_active_channels(self):
        """
        Recoge los canales activos de la centralita a partir de las habitaciones de self.group
        Returns: lista con los canales activos

        """
        if not self.groups:
            print(f"ERROR {__file__} - No se ha definido grupo de habitaciones para {self.name}")

        # with open(phi.ROOMGROUPS_VALUES_FILE, "r") as f:
        #     roomgroups_values = json.load(f)

        roomgroup_id = self.groups[0]  # No puede asociarse más de 1 grupo de habitaciones al controlador
        roomgroup = phi.all_room_groups.get(roomgroup_id)  # Objeto del grupo RoomGroup
        print(f"(devices.py/get_active_channels). Importando roomgroup de {self.name} / tipo {type(roomgroup)}")
        if roomgroup is None:
            print(f"ERROR {__file__} - El grupo de habitaciones {roomgroup_id} asociado {self.name} no "
                  f"tiene información")
            return
        rooms = roomgroup.roomgroup  # Lista con las habitaciones del grupo (objetos Room)
        for room in rooms:
            channel = room.rt_source.get("adr")  # el adr de rt_source coincide con el canal
            if channel is not None:
                self.active_channels.append(channel)
        print(f"(devices.py). Canales activos Controlador {self.name}: {self.active_channels}")

    async def iv_mode(self, new_iv_mode: [int, None] = None):
        """
        Fija el modo iv de la centralita de suelo radiante.
        Si new_iv_mode es None, devuelve el modo actual
        Param:
            new_iv_mode: modo calefacción (0) / refrigeración (1) a establecer
        Returns:
             Modo calefacción / refrigeración actual
        """
        # if self.groups is None:
        #     print(f"ERROR {__file__} - No se ha definido ningún grupo en el dispositivo {self.name}")
        #     return
        # group_values = await get_roomgroup_values(self.groups[0])
        # group_iv = group_values.get("iv")
        # if group_iv is not None:
        #     self.iv = group_iv
        #
        iv_datatype = self.iv_source[0]
        iv_adr = self.iv_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": iv_datatype,
                  "adr": iv_adr}
        current_iv_mode = get_value(target)
        if new_iv_mode is None:
            self.iv = current_iv_mode
        elif new_iv_mode in [phi.COOLING, phi.HEATING]:
            res = await set_value(target, new_iv_mode)
            self.iv = new_iv_mode

        dbval = save_value(target, self.iv)
        return self.iv

    async def pump_st(self):
        """
        Devuelve el estado del relé de bomba.
        Returns:
             Estado del relé de bomba
        """
        if self.pump_source is None:
            return self.pump  # Atributo definido en attr_list

        datatype = self.pump_source[0]
        adr = self.pump_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        self.pump = get_value(source)
        dbval = save_value(source, self.pump)

        return self.pump

    async def set_channel_info(self, channel: int) -> [phi.Dict, None]:
        """
        Actualiza los diccionarios de cada canal con la consigna, temperatura ambiente, humedad relativa,
        temperatura del suelo, estado del actuador y autorización para refrigeración con los valores leídos
        en datadb
        Si el modelo es X147, la consigna es la leída por Modbus, convertida a gradC + 2
        Param:
            channel: Canal a actualizar
        Returns:
            Diccionario con la información del canal
            None cuando el canal no se utiliza en el proyecto
        """
        channel_source_attr = f"ch{channel}_source"
        channel_attr = f"ch{channel}"
        channel_info = {"sp": None, "rt": None, "rh": None, "ft": None, "st": None, "coff": None}
        channel_val_attrs = {magnitud: f"{magnitud}{channel}" for magnitud in tuple(channel_info.keys())}
        # ch_sources = self.__getattribute__(channel_source_attr)
        ch_sources = getattr(self, channel_source_attr)
        print(f"(método set_channel_info) Valor almacenado modo IV X147: {self.iv} ")

        for key, value in ch_sources.items():
            datatype = value[0]
            adr = value[1]
            source = {"bus": int(self.bus_id),
                      "device": int(self.device_id),
                      "datatype": datatype,
                      "adr": adr}
            # current_value = get_value(source)
            current_value = get_value(source)
            if current_value not in (None, ""):
                if "sp" in key and "x147" in self.model.lower() and self.iv:
                    print(f"(método set_channel_info) Valor almacenado consigna X147:sl-{self.slave} - canal: {channel}"
                          f" {current_value} / ({type(current_value)})")
                    current_value += 2.0  # En refrigeración, la consigna de los ttos es 2 gradC superior a la leída
                    print(f"(método set_channel_info) Valor refrigeración consigna X147: {current_value} "
                          f"({type(current_value)})")
            else:
                current_value = phi.READ_ERROR_VALUE  # 08/07/2023 mala lectura

            # if current_value is None:  # El canal no se utiliza
            #     return

            setattr(self, channel_val_attrs.get(key), current_value)  # actualiza los atributos spx, rtx,
            # etc. siendo x el canal
            channel_info[key] = current_value
        # print(f"Método set_channel_info UFHCController.\nCanal {channel}\nOrigen de datos: {ch_sources}")
        setattr(self, channel_attr, channel_info)
        # Si los valores de rt y rh son válidos, se calcula el punto de rocío y la entalpía del canal
        rt = getattr(self, channel_val_attrs.get("rt"))
        rh = getattr(self, channel_val_attrs.get("rh"))
        if rh and rh != phi.READ_ERROR_VALUE:
            rh = rh[1]  # Se toma solo el byte bajo
        channel_h_attr = f"h{channel}"
        channel_dp_attr = f"dp{channel}"
        channel_h = 0
        channel_dp = None

        if rt is not None and rh not in [None, '0', 0]:
            if 100 > float(rt) > -100:
                channel_h = await get_h(float(rt), float(rh))
                channel_dp = await get_dp(float(rt), float(rh))
        setattr(self, channel_h_attr, channel_h)
        setattr(self, channel_dp_attr, channel_dp)

        return getattr(self, channel_attr)

    # async def upload(self):
    #     """
    #     Escribe en el dispositivo ModBus los valores actuales de sus atributos tipo RW:
    #     Los atributos se han actualizado desde la web o desde un termostato
    #     Consignas y modo IV
    #     :return:
    #     """
    #     if not self.active_channels:
    #         await self.get_active_channels()
    #
    #     await self.iv_mode(self.iv)
    #     # spch_sources = (("sp" + str(idx + 1), "ch" + str(idx + 1) + "_source") for idx in range(12))
    #     # Propago únicamente la información de los canales activos
    #     spch_sources = (("sp" + str(idx), "ch" + str(idx) + "_source") for idx in self.active_channels)
    #     for sp, src in spch_sources:
    #         ch_info = getattr(self, src)
    #         sp_value = getattr(self, sp)
    #         print(f"\n\tValor actual de la consigna de {ch_info} antes de terminar upload:"
    #               f" {sp_value}/{type(sp_value)}\n")
    #         sp_value_corr = sp_value
    #         if not sp_value is None and sp_value:
    #             if float(sp_value) > 950:
    #                 continue
    #             else:
    #                 if "x147" in self.model.lower() and self.iv:
    #                     print(
    #                         f"(método x147 upload) Valor real consigna:sl-{self.slave} - canal: {src}"
    #                         f" {sp_value} / ({type(sp_value)})")
    #                     sp_value_corr = float(sp_value) - 2.0  # En refrig, la consigna a escribir es 2 gradC
    #                     # inferior a la de los ttos
    #                     print(f"(método set_channel_info) Valor consigna a escribir X147: {sp_value_corr} "
    #                           f"({type(sp_value_corr)})")
    #
    #         if None not in (ch_info, sp_value):
    #             sp_target = ch_info.get("sp")
    #             datatype = sp_target[0]
    #             adr = sp_target[1]
    #             target = {"bus": int(self.bus_id),
    #                       "device": int(self.device_id),
    #                       "datatype": datatype,
    #                       "adr": adr}
    #             print(f"UFHCController {self.name}. uploading value {sp_value_corr}")
    #             uploaded_value = await set_value(target, sp_value_corr)
    #             dbval = save_value(target, sp_value_corr)
    #             uploaded_value = get_value(target)
    #             print(f"UPLOAD - Comprobando valor de atributo escrito: {uploaded_value}")
    #
    #     return 1


    # 21/06/2024 Cambio el método para que se haga upload sólo del atributo indicado

    async def update_attr_file(self, attr: str):
        """
        Actualiza el archivo de intercambio correspondiente al atributo attr, PERO SÓLO SI HA CAMBIADO SU VALOR.
        Se hace así para poder distinguir entre un cambio en la web, que se haya hecho posteriormente a la
        última lectura
        En el caso de las consignas, la leída en el dispositivo se guarda en spx_bus (x es el canal) y la leída
        en la web se guarda en spx.
        Posteriormente se actualiza el archivo sp con el valor de la web o el valor de spx_bus
        Args:
            attr: atributo a guardar en el archivo de intercambio

        Returns: 1 si la escritura es correcta
        0 si la escritura no es correcta

        """
        # Compruebo si el atributo existe
        attributes = self.__dict__.keys()
        if attr not in attributes:
            print(f"{attr} NO es un atributo de {self.name}")
            return 0
        attr_dev_file = f"{phi.EXCHANGE_FOLDER}/{self.bus_id}/{self.slave}/{attr}"
        if not phi.os.path.isfile(attr_dev_file):
            print(f"ERROR {__file__}\nNo se encuentra el archivo {attr_dev_file}")
            return 0
        current_attr_val = getattr(self, attr)  # Valor leído en el dispositivo
        print(f"\n\tValor actual del atributo {attr} antes de terminar update:"
              f" {current_attr_val}/{type(current_attr_val)}\n"
              f"\tArchivo del que se recoge el atributo: {attr_dev_file}\n")
        with open(attr_dev_file, "r") as attrf:
            xch_value = attrf.read().strip()  # Valor compartido con la Web
            print(f"Valor almacenado en {attr_dev_file} de {self.name}: {xch_value}")
        if not xch_value:
            print("\n\t\tel archivo de intercambio está vacío\n")
            xch_value = current_attr_val
            with open(attr_dev_file, "w") as f:
                f.write(str(current_attr_val))
        # Gestiono las consignas, que tienen un tratamiento distinto al resto
        if "sp" in attr:
            print(f"Valor del atributo leído en el dispositivo: {current_attr_val} / {type(current_attr_val)}")
            attr_dev_bus_file = f"{attr_dev_file}_bus"  # Debe comprobarse si hay cambios desde la web
            if not phi.os.path.isfile(attr_dev_bus_file):
                print(f"ERROR {__file__}\nNo se encuentra el archivo {attr_dev_bus_file}")
                print(f"Se actualiza con el valor leído en {attr_dev_file}: {current_attr_val}")
                try:
                    with open(attr_dev_bus_file, "w") as f:
                        f.write(str(current_attr_val))
                except FileNotFoundError as e:
                    print(f"\n\tError guardando valor en spx_bus file\n{e}\n")
                stored_sp_bus_val = current_attr_val
            else:
                with open(attr_dev_bus_file, "r") as f:
                    stored_sp_bus_val = f.read().strip()  # Valor leído anteriormente en el dispositivo
            print(f"Valor almacenado en {attr_dev_bus_file} de {self.name}: {stored_sp_bus_val} / "
                  f"{type(stored_sp_bus_val)}")
            if not stored_sp_bus_val:
                stored_sp_bus_val = current_attr_val
                with open(attr_dev_bus_file, "w") as f:
                    f.write(str(current_attr_val))

            # if float(stored_sp_bus_val) != float(current_attr_val):  # El usuario ha cambiado la consigna.
            if float(stored_sp_bus_val) != current_attr_val:  # El usuario ha cambiado la consigna.
                # Se actualizan con el nuevo valor los archivos spx, spx_bus y el dispositivo
                print(f"{self.name} - Consigna {stored_sp_bus_val} cambiada en termostato a {current_attr_val}")
                with open(attr_dev_bus_file, "w") as attdbf:
                    attdbf.write(str(current_attr_val))
                with open(attr_dev_file, "w") as attdf:
                    attdf.write(str(current_attr_val))
                setattr(self, attr, current_attr_val)  # Se actualiza el atributo
                return 1
            elif float(xch_value) != current_attr_val:  # Se ha cambiado desde la Web.
                # Se actualiza el archivo spx_bus
                print(f"{self.name} - Consigna {stored_sp_bus_val} cambiada desde la web a {xch_value}")
                setattr(self, attr, float(xch_value))  # Se actualiza el atributo
                print(f"Atributo {attr} actualizado desde la web a {getattr(self, attr)}/{type(getattr(self, attr))}")
                with open(attr_dev_bus_file, "w") as attdbf:
                    attdbf.write(str(xch_value))  # Se actualiza el archivo
                with open(attr_dev_file, "w") as attdbf:
                    attdbf.write(str(xch_value))  # Se actualiza el archivo
                print("\n\tCOMPROBANDO ACTUALIZACIÓN DE ARCHIVO")
                with open(attr_dev_bus_file, "r") as attdbf:
                    file_content = attdbf.read()
                    print(f"\n\tValor guardado en el archivo leído desde el termostato {file_content}")
                return 1
            else:
                print(f"No hay que actualizar {attr} en {self.name}")
                return 0
        # Gestiono el resto de atributos
        if str(current_attr_val) == xch_value:
            print(f"Valor leido en archivo: {xch_value} IGUAL A\nValor actual {current_attr_val}")
            # No cambio el archivo
            return 0
        else:
            print(f"Valor leido en archivo: {xch_value} DISTINTO A\nValor actual {current_attr_val}")
            with open(attr_dev_file, "w") as attrf:
                print(f"Actualizando archivo {attr_dev_file} desde método de clase de {self.name}")
                attrf.write(str(current_attr_val))
                setattr(self, attr, current_attr_val)  # Se actualiza el atributo
                return 1

    async def update(self):
        """
        Actualiza todos los atributos del dispositivo ModBus según las últimas lecturas
        :return:
        """
        if not self.active_channels:
            await self.get_active_channels()

        # system_iv = get_modo_iv()  # Modo frío=1 / calor=0 del sistema
        print(f"DEBUGGING {__file__} - Modo de funcionamiento del sistema asociado al "
              f"Controlador UFHC {self.name} = {phi.system_iv}")
        await self.iv_mode(phi.system_iv)  # Actualizo el modo IV de la centralita
        await self.update_attr_file("iv")  # Actualizo archivo de intercambio iv de la centralita
        await self.pump_st()  # Actualizo el estado de la bomba
        await self.update_attr_file("pump")  # Actualizo archivo de intercambio iv de la centralita
        # Actualizo solo la información de los canales activos
        files_to_update = []
        for ch in self.active_channels:
            await self.set_channel_info(ch)  # Actualiza cada cana (atributos) con los últimos valores leídos
            channel_files = [f"sp{ch}", f"rt{ch}", f"rh{ch}", f"ft{ch}", f"st{ch}", f"coff{ch}"]
            print(f"(devices.py - UFHCController) Actualizando información en archivos de {self.name}. Canal {ch}")
            for f in channel_files:
                # await self.update_attr_file(f) # sustituida por check
                await check_changes_from_web(self.bus_id, self, f)
                # propago al dispositivo los valores de sp y coff
                if "sp" in f or "coff" in f:  # Se trata de una consigna o de una autorización para refrigeración
                    print(f"(ubase update) Propagando el atributo {f} al dispositifo {self.name}")
                    await self.upload(f)
        # await self.upload()  # Se cargan los nuevos valores en el dispositivo
        # await update_xch_files_from_devices(self)  # Guarda los valores del dispositivo en el archivo de intercambio
        # # correspondiente.

        return 1

    async def upload(self, attr):
        """
        Escribe en el dispositivo ModBus el valor actual del atributo del tipo RW
        Los atributos se han actualizado desde la web o desde un termostato
        Consignas y autorización para refrigeración
        :return:
        """
        es_consigna = "sp" in attr
        attr_type = "sp" if es_consigna else "coff"
        channel_id = attr[len(attr_type):]

        attr_source_name = "ch" + channel_id + "_source"
        ch_info = getattr(self, attr_source_name)
        sp_value = getattr(self, attr)
        attr_name = "consigna" if es_consigna else "refrigeración autorizada"
        print(f"\n\tValor actual de {attr_name} antes de terminar upload:{sp_value}/{type(sp_value)}\n")
        sp_value_corr = sp_value  # sp_value es un valor real de consigna en grados centígrados (sin x10)
        if es_consigna and sp_value is not None and sp_value:
            if float(sp_value) > 35.0:
                print(f"la consigna leída en {attr} está fuera de rango")
            else:
                if "x147" in self.model.lower() and self.iv:
                    sp_value_corr = float(sp_value) - 2.0  # En refrig, la consigna a escribir es 2 gradC
                    # inferior a la de los ttos
                    print(f"(método set_channel_info) Valor consigna a escribir X147: {sp_value_corr} "
                          f"({type(sp_value_corr)})")

        if None not in (ch_info, sp_value):
            sp_target = ch_info.get(attr_type)  # extraído la consigna o cooling off
            datatype = sp_target[0]
            adr = sp_target[1]
            target = {"bus": int(self.bus_id),
                      "device": int(self.device_id),
                      "datatype": datatype,
                      "adr": adr}
            print(f"UFHCController {self.name}. uploading value {sp_value_corr}")
            uploaded_value = await set_value(target, sp_value_corr)
            dbval = save_value(target, sp_value_corr)
            uploaded_value = get_value(target)
            print(f"UPLOAD - Comprobando valor de atributo escrito: {uploaded_value}")

        return 1


    def __repr__(self):
        """
        Representación de la centralita para control de sistemas de suelo radiante
        :return:
        """
        iv_mode = ["Calefacción", "Refrigeración"]
        pump_st = ["Parada", "En Marcha"]
        dev_info = f"\nControlador para suelo radiante {self.name}"
        if self.iv is not None:
            dev_info += f"\n\tModo de funcionamiento: {iv_mode[self.iv]}"
        if self.pump is not None:
            dev_info += f"\n\tEstado bomba circuladora: {pump_st[self.pump]}"
        # for ch in range(12):
        # Represento únicamente los canales activos
        for ch in self.active_channels:
            channel_source_attr = f"ch{ch}_source"
            # attr_value = self.__getattribute__(channel_source_attr)
            attr_value = getattr(self, channel_source_attr)
            if attr_value is not None:
                channel_attr = f"ch{ch}"
                # channel_info = self.__getattribute__(channel_attr)
                channel_info = getattr(self, channel_attr)
                dev_info += f"\n\tCanal {ch}:\n\t\t{channel_info}"

        return dev_info


class Split(phi.MBDevice):
    pass


class HeatRecoveryUnit(phi.MBDevice):
    """
    Controlador de recuperadores de calor sistema Phoenix.
    Dispositivo especial SIG310 o cualquier recuperador de calor del mercado
    NOTA: TODAS LAS CLAVES DEL JSON HEATRECOVERYUNITS.JSON EN LA CARPETA DE PROJECT_ELEMENTS DEBE ENCONTRARSE ENTRE
    LOS ATRIBUTOS DE ESTE DISPOSITIVO.
    Puede controlar recuperadores de 3 velocidades con batería de apoyo y compuertas de aire exterior y recirculación.
    Con los recuperadores de calor del mercado, en lugar de velocidades se puede fijar el caudal
    El recuperador estará asociado a un grupo de habitaciones.
    El recuperador tendrá 4 modos de funcionamiento: Deshumidificación, apoyo a la climatización, freecooling y
    ventilación
    Al actualizar el recuperador se determina el modo de funcionamiento, teniendo prioridad el de deshumidificación.
    La deshumidificación se activa cuando la instalación está en modo refrigeración y el punto de rocío del grupo de
    habitaciones se encuentra por encima del valor de la temperatura del grupo + phi.OFFSET_ACTIVACION_DESHUMIDIFICACION
    El apoyo a la climatización se activa cuando, en modo calefacción hay demanda de calefacción en el grupo y
    la consigna del grupo es superior a la temperatura ambiente en modo calefacción o si en modo refrigeración hay
    demanda de refrigeración y la consigna de aire es inferior a la temperatura ambiente.
    La consigna de aire del grupo tiene en cuenta los offsets que hacen funcionar el recuperador como segunda etapa
    de climatización.
    El freecooling se activa en modo refrigeración cuando la entalpía o la temperatura exterior son menores que las
    interiores
    El modo ventilación se activa cuando ninguno de los anteriores está activo.
    En Deshumidificación, Apoyo y Freecooling, el ventilador se pone a la máxima velocidad definida en
    phi.MAX_VELOC_RECUPERADOR o, cuando existe, al caudal máximo definido para el recuperador en el JSON
    heatrecoveryunits.json

    Param: device: dispositivo ModBus con el mapa de registros a mapear para las operaciones con el controlador SIG310.
    Param: groups: grupos de habitaciones vinculados al dispositivo. Cada recuperador sólo puede estar asociado a
    un grupo de habitaciones. Si se introduce más de 1, sólo se utiliza el primero de ellos.
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
        self.onoff = phi.ON
        self.hru_modes = {phi.DESHUMIDIFICACION: False,
                          phi.FANCOIL: False,
                          phi.FREE_COOLING: False,
                          phi.VENTILACION: True}
        self.hru_mode = phi.VENTILACION
        self.man_hru_mode_st = phi.OFF  # Para fijar manualmente el modo de funcionamiento
        self.man_hru_mode = phi.VENTILACION
        self.manual = 0  # Valor manual de velocidad o caudal de aire, compuertas y válvula. 0:desactivado
        self.flow_target = None
        self.supply_flow_source = None
        self.supply_flow = None
        self.exhaust_flow_source = None
        self.exhaust_flow = None
        self.manual_airflow = 240
        self.otemp_source = None  # Tipo de registro y registro para leer la temperatura exterior
        self.itemp_source = None  # Ídem temperatura interior
        self.supply_pres_source = None  #
        self.supply_pres = None
        self.exhaust_pres_source = None
        self.exhaust_pres = None
        self.filter_st_source = None
        self.error_source = None
        self.speed1_source = None
        self.speed2_source = None
        self.speed3_source = None
        self.speed = None
        self.manual_speed = 2
        self.valv_source = None
        self.valv_st = None  # Estado actual de la válvula
        self.man_valv_pos = 1  # Posición manual de la válvula
        self.bypass_target = None  # Registro y tipo de registro para operar con el bypass
        self.bypass_source = None  # Registro y tipo de registro para leer estado bypass
        self.bypass_st = None
        self.dampers_source = None
        self.dampers_st = None
        self.man_dampers_pos = 1
        self.remote_onoff_st_source = None
        self.remote_onoff = None  # Valor del registro 8: on/off remoto del recuperador
        self.aux_ed2_source = None
        self.aux_ed2_st = None
        self.aux_ed3_source = None
        self.aux_ed3_st = None
        self.max_airflow = None

    async def get_airflow(self):
        """
        Si están disponibles, obtiene los caudales de impulsión y extracción del recuperador

        Returns: caudales actuales del impulsión y extracción del recuperador
        """
        sources = (self.supply_flow_source, self.exhaust_flow_source)
        values = [self.supply_flow, self.exhaust_flow]
        for idx, src in enumerate(sources):
            if src is None:
                continue
            af_datatype = src[0]
            af_adr = src[1]
            source = {"bus": int(self.bus_id),
                      "device": int(self.device_id),
                      "datatype": af_datatype,
                      "adr": af_adr}
            values[idx] = get_value(source)
        self.supply_flow, self.exhaust_flow = values
        return self.supply_flow, self.exhaust_flow

    async def set_airflow(self, new_airflow: [int, None] = None):
        """
        Aplica al recuperador el caudal 'new_airflow'.
        Si 'new_airflow' is None, devuelve los caudales actuales del impulsión y extracción del recuperador
        'new_airflow' está limitado al valor de self.max_airflow.

        Returns: caudales actuales del impulsión y extracción del recuperador
        """
        self.supply_flow, self.exhaust_flow = await self.get_airflow()  # Caudales actuales de impulsión y extracción

        if self.flow_target is None:  # En este recuperador no se fija el caudal
            return

        new_af_datatype = self.flow_target[0]
        new_af_adr = self.flow_target[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": new_af_datatype,
                  "adr": new_af_adr}

        if new_airflow is None:
            return self.supply_flow, self.exhaust_flow

        new_airflow = self.max_airflow if new_airflow > self.max_airflow else new_airflow
        res = await set_value(target, new_airflow)
        if res:
            self.supply_flow = new_airflow
            self.exhaust_flow = new_airflow
            dbval = save_value(target, self.exhaust_flow)
        return self.supply_flow, self.exhaust_flow

    async def set_speed(self, new_speed: [int, None] = None):
        """
        Aplica al recuperador la velocidad 'new_speed'.
        Si 'new_speed' is None, devuelve la velocidad actual del recuperador. Si hay más de un relé de velocidad
        activado, se toma el más alto.
        Si 'new_speed es 0, se ponen a 0 todas las velocidades

        Returns: Velocidad actual del recuperador
        """
        print(f"DEBUGGING {__file__}: Fijando velocidad recuperador - {new_speed}")
        sources = {1: self.speed1_source, 2: self.speed2_source, 3: self.speed3_source}
        if all([x is None for x in sources.values()]):
            return  # El recuperador no trabaja con velocidades, sino con caudales
        current_speed = 0
        # self.speed = 0
        for spd, src in sources.items():
            if src is None:
                continue
            speed_datatype = src[0]
            speed_adr = src[1]
            target = {"bus": int(self.bus_id),
                      "device": int(self.device_id),
                      "datatype": speed_datatype,
                      "adr": speed_adr}
            spd_value = get_value(target)
            if new_speed == 0:
                print(f"DEBUGGING {__file__}: Poniendo recuperador a velocidad 0")
                self.speed = 0
                if spd_value == phi.ON:
                    res = await set_value(target, phi.OFF)
            elif new_speed is None:
                if spd_value:
                    print(f"DEBUGGING {__file__}: Velocidad actual recuperador {spd_value}")
                    current_speed = spd
                    self.speed = spd
            elif new_speed == spd:
                print(f"DEBUGGING {__file__}: Poniendo recuperador a velocidad {new_speed}")
                res = await set_value(target, phi.ON)
                current_speed = spd
                self.speed = spd
            else:
                res = await set_value(target, phi.OFF)
                self.speed = 0
            dbval = save_value(target, self.speed)

        if current_speed == 0:  # No se ha seleccionado ninguna velocidad y el recuperador estaba apagado
            self.speed = 0

        print(f"DEBUGGING {__file__}: (antes de return) Poniendo recuperador a velocidad {self.speed}")
        return self.speed

    async def set_manual_speed(self):
        """
        Aplica al recuperador la velocidad self.manual_speed cuando se activa el modo manual

        Returns: Velocidad actual
        """
        targets = {1: self.speed1_source, 2: self.speed2_source, 3: self.speed3_source}
        if not self.manual:
            return self.speed
        for spd, src in targets.items():
            if src is None:
                continue
            speed_datatype = src[0]
            speed_adr = src[1]
            target = {"bus": int(self.bus_id),
                      "device": int(self.device_id),
                      "datatype": speed_datatype,
                      "adr": speed_adr}
            spd_value = get_value(target)
            if self.manual_speed == 0:
                self.speed = 0
                if spd_value == phi.ON:
                    res = await set_value(target, phi.OFF)
                    dbval = save_value(target, phi.OFF)
            elif self.manual_speed == spd:
                res = await set_value(target, phi.ON)
                dbval = save_value(target, phi.ON)
                self.speed = spd
            else:
                res = await set_value(target, phi.OFF)
                dbval = save_value(target, phi.OFF)

        return self.speed

    async def set_manual_airflow(self):
        """
        Aplica al recuperador el caudal self.manual_airflow cuando se activa el modo manual

        Returns: Caudal actual de aire
        """
        if not self.manual:
            airflows = await self.get_airflow()
            return airflows  # Caudales de impulsión y extracción
        if self.flow_target is None:
            return
        af_datatype = self.flow_target[0]
        af_adr = self.flow_target[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": af_datatype,
                  "adr": af_adr}

        await self.set_airflow(self.manual_airflow)
        self.supply_flow = self.manual_airflow
        self.exhaust_flow = self.manual_airflow

        return self.supply_flow, self.exhaust_flow

    async def set_dampers_pos(self, new_pos: [int, None] = None):
        """
        Coloca las compuertas en la posición definida en new_pos:
            0: recirculación cerrada / aire exterior abierta
            1: recirculación abierta / aire exterior cerrada

        Si 'new_pos' is None, devuelve la posición actual de las compuertas.

        Returns: Posición actual de las compuertas
        """
        if self.dampers_source is None:
            return
        datatype = self.dampers_source[0]
        adr = self.dampers_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_pos = get_value(value_source=source)
        print(f"DEBUGGING {__file__}: Posición actual compuertas {current_pos}\n(0=sin recirculación)")
        if current_pos == new_pos or new_pos is None:
            self.dampers_st = current_pos
        else:
            res = await set_value(source, new_pos)
            dbval = save_value(source, new_pos)
            self.dampers_st = new_pos

        print(f"DEBUGGING {__file__}: Posición calculada compuertas {self.dampers_st}\n(0=sin recirculación)")
        return self.dampers_st

    async def set_valv_pos(self, new_pos: [int, None] = None):
        """
        Coloca la válvula en la posición definida en new_pos:
            0: cerrada
            1: abierta

        Si 'new_pos' is None, devuelve la posición actual de la válvula.

        Returns: Posición actual de la válvula
        """
        if self.valv_source is None:
            return
        datatype = self.valv_source[0]
        adr = self.valv_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_pos = get_value(value_source=source)
        # print(f"DEBUGGING {__file__}: Estado actual válvula {current_pos}\t(0 = Cerrada)\n"
        #       f"La funcion get_value devuelve un valor de tipo {type(current_pos)}  ")
        if current_pos == new_pos or new_pos is None:
            self.valv_st = current_pos
        else:
            states = ["Cerrando", "Abriendo"]
            valv_operation = "No se puede actuar sobre " if self.valv_st is None else f"{states[new_pos]}"
            print(f"DEBUGGING {__file__}: {valv_operation} válvula")
            res = await set_value(source, new_pos)
            dbval = save_value(source, new_pos)
            self.valv_st = new_pos

        # print(f"DEBUGGING {__file__}: Estado válvula {self.valv_st}\t(0 = Cerrada)")
        return self.valv_st

    async def set_bypass_pos(self, new_pos: [int, None] = None):
        """
        Coloca el bypass del recuperador en la posición definida en new_pos:
            0: cerrada
            1: abierta

        Si 'new_pos' is None, devuelve la posición actual del bypass del recuperador.

        Returns: Posición actual del bypass del recuperador
        """
        if self.bypass_source is None:
            return
        src_datatype = self.bypass_source[0]
        src_adr = self.bypass_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": src_datatype,
                  "adr": src_adr}
        current_pos = get_value(value_source=source)
        if current_pos == new_pos or new_pos is None:
            self.bypass_st = current_pos
        else:
            if self.bypass_target is None:
                target = source
            else:
                tgt_datatype = self.bypass_target[0]
                tgt_adr = self.bypass_target[1]
                target = {"bus": int(self.bus_id),
                          "device": int(self.device_id),
                          "datatype": tgt_datatype,
                          "adr": tgt_adr}
            res = await set_value(target, new_pos)
            dbval = save_value(target, new_pos)
            self.bypass_st = new_pos if res else current_pos

        return self.bypass_st

    async def get_op_mode(self) -> int:
        """
        Determina el modo de funcionamiento a fijar en el recuperador.
            0: HRU off
            1: DESHUMIDIFICACION
            2: FANCOIL / APOYO A LA CLIMATIZACIÓN
            4: FREE_COOLING
            5: FREE_COOLING + DESHUMIDIFICACIÓN (Modo anulado para no introducir humedad exterior aunque sea menor)
            6: FREE_COOLING + FANCOIL
            8: VENTILACIÓN
        - Modo Deshumidificación: Grupo de habitaciones en modo Cooling AND Temperatura ambiente de alguna
        habitación del grupo a menos de phi.OFFSET_ACTIVACION_DESHUMIDIFICACION (default=1) del punto de rocío del
        grupo de habitaciones. El modo se podrá activar en el método act_op_mode si dampers_source AND valv_source
        NO SON None.
        La consigna de impulsión de agua siempre va a estar limitada por el punto de rocío.
        - Modo Fancoil (Apoyo a la climatización): La diferencia entre la temperatura ambiente del grupo y la consigna
        de aire del grupo es mayor que phi.OFFSET_COOLING en refrigeración o que phi.OFFSET_HEATING en calefacción.
        - Modo Freecooling: La entalpía o la temperatura exteriores se pueden leer y son menores que la temperatura
        interior AND bypass_source no es None
        - Modo Ventilación: Cuando no está activa ninguna de las anteriores. Si se conoce el nivel de calidad de aire y
        la consigna, se ventila en función a dicho valor. Si no, se fija una velocidad por defecto.
        Returns:
             Modo de funcionamiento del recuperador.

        """
        if self.onoff == phi.OFF:
            return phi.OFF

        if not self.groups:
            return self.hru_mode

        dehumid_mode = False  # Modo deshumidificación
        fancoil_mode = False  # Modo fancoil / apoyo a la climatización
        freecooling_mode = False  # Modo free-cooling
        ventilation_mode = True
        self.hru_mode = phi.VENTILACION
        group_id = self.groups[0]  # El recuperador sólo puede estar asociado a un grupo de habitaciones
        group = phi.all_room_groups.get(group_id)
        group_cooling_mode = group.iv  # Modo calefacción (False) o refrigeración (True) del grupo
        group_rt = [float(room.get_rt()) for room in group.roomgroup if room.get_rt() is not None]  # Tª de las habitaciones
        group_sp = group.air_sp  # Consigna de ambiente calculada para el grupo
        group_wsp = group.water_sp  # Consigna de impulsión de agua para el grupo
        group_demand = group.demand  # 0-No demanda / 1-Demanda Refrig / 2-Demanda Calef.
        print(f"DEBUGGING {__file__}: Grupo {self.groups[0]}\n\tConsignas:\t{group_sp} \n\t"
              f"temperaturas:\t{group_rt}\n\tImpulsion agua:\t{group_wsp}\n\tDemanda:\t{group_demand}  ")
        if not group_sp or not group_rt:  # Si no leo temperaturas o consignas,
            # activo Modo Ventilación
            print(f"DEBUGGING {__file__}: Grupo {self.groups[0]}\n\tFaltan consignas ({group_sp} o "
                  f"temperaturas{group_rt}")
            return self.hru_mode
        else:
            print(f"DEBUGGING {__file__}: Grupo {self.groups[0]}\n\tConsignas y temp válidas ({group_sp} "
                  f"temperaturas{group_rt}")

        group_dp = group.air_dp  # Punto de rocío del grupo
        group_h = group.air_h  # Entalpía del grupo
        if group_cooling_mode:
            for rt in group_rt:
                if rt < group_dp + phi.OFFSET_ACTIVACION_DESHUMIDIFICACION or \
                        (group_demand == 1 and group_wsp > phi.TEMP_ACTIVACION_DESHUMIDIFICACION):
                    dehumid_mode = True
                    self.hru_mode = phi.DESHUMIDIFICACION
            building = group.roomgroup[0].building_id  # Edificio al que pertenece el grupo de habitaciones
            t_ext = get_temp_exterior(building)  # Temperatura exterior
            rh_ext = get_hrel_exterior(building)  # Humedad relativa Exterior
            if rh_ext == 0 or rh_ext is None:  # El freecooling debe ser térmico
                if t_ext < min(group_rt):  # Se activa el freecooling térmico
                    freecooling_mode = True
            elif group_h is not None:  # Se comprueba si se puede habilitar el free-cooling entálpico
                h_ext = get_h_exterior()  # Entalpía exterior
                if h_ext < group_h:
                    freecooling_mode = True

        if not dehumid_mode:
            if group_cooling_mode and group_sp < max(group_rt) + phi.OFFSET_COOLING or \
                    not group_cooling_mode and group_sp > min(group_rt) + phi.OFFSET_HEATING:  # OFFSET_HEATING es
                # siempre < 0
                fancoil_mode = True
                self.hru_mode = phi.FANCOIL

        if freecooling_mode and not dehumid_mode:  # En modo deshumidificación no se activa free-cooling
            # para no introducir más humedad exterior, aunque sea más baja que la interior.
            self.hru_mode += phi.FREE_COOLING

        if dehumid_mode or fancoil_mode or freecooling_mode:
            ventilation_mode = False  # El modo ventilación se activa sólo si no está activado alguno de
            # los otros modos
        self.hru_modes[phi.DESHUMIDIFICACION] = dehumid_mode
        self.hru_modes[phi.FANCOIL] = fancoil_mode
        self.hru_modes[phi.FREE_COOLING] = freecooling_mode
        self.hru_modes[phi.VENTILACION] = ventilation_mode
        return self.hru_mode

    async def off_mode(self):
        """
        Apaga el recuperador:
            Ventilador a velocidad 0 (relés velocidad desactivados) o recuperador a caudal 0
            Compuerta de recirculación abierta / compuerta aire exterior cerrada
            Válvula de 3 vías cerrada
        :return:
        """
        print(f"Apagando recuperador {self.name}")
        await self.set_speed(phi.OFF)
        await self.set_airflow(0)
        await self.set_valv_pos(phi.CLOSED)
        await self.set_dampers_pos(phi.CLOSED)

    async def dehumidification_mode(self):
        """
        Configura el recuperador en modo deshumidificación:
            Ventilador a velocidad máxima
            Compuerta de recirculación abierta / compuerta aire exterior cerrada
            Válvula de 3 vías abierta
        :return:
        """
        print(f"Activando modo deshumidificación en el recuperador {self.name}")
        await self.set_speed(phi.MAX_HRU_SPEED)
        await self.set_airflow(self.max_airflow)
        await self.set_valv_pos(phi.OPEN)
        await self.set_dampers_pos(phi.OPEN)

    async def fancoil_mode(self):
        """
        Configura el recuperador en modo fancoil / apoyo a la climatización:
            Ventilador a velocidad máxima
            Compuerta de recirculación cerrada / compuerta aire exterior abierta
            Válvula de 3 vías abierta
        :return:
        """
        print(f"Activando modo fancoil en el recuperador {self.name}")
        await self.set_speed(phi.MAX_HRU_SPEED)
        await self.set_airflow(self.max_airflow)
        await self.set_valv_pos(phi.OPEN)
        await self.set_dampers_pos(phi.CLOSED)

    async def freecooling_mode(self):
        """
        Activa el freecooling con el recuperador:
            Ventilador a velocidad máxima
            Compuerta de recirculación cerrada / compuerta aire exterior abierta
            Válvula de 3 vías cerrada si no están activados los modos Fancoil o Deshumidificación
            Bypass recuperador abierto
        :return:
        """
        print(f"Activando freecooling en el recuperador {self.name}")
        await self.set_speed(phi.MAX_HRU_SPEED)
        await self.set_airflow(self.max_airflow)
        if self.hru_mode in (5, 6):
            await self.set_valv_pos(phi.OPEN)  # En modo fancoil y deshumidificación con FreeC la válvula está abierta
        else:
            await self.set_valv_pos(phi.CLOSED)
        await self.set_dampers_pos(phi.CLOSED)
        await self.set_bypass_pos(phi.OPEN)

    async def ventilation_mode(self):
        """
        Activa el modo ventilación en el recuperador:
            Si hay lectura de calidad de aire, se ventila en función de la calidad de aire.
            Si no, se ventila a velocidad fija: phi.HRU_VENTILATION_SPEED o a phi.HRU_VENTILATION_AFLOWPCT
            Compuerta de recirculación cerrada / compuerta aire exterior abierta
            Válvula de 3 vías cerrada
            Bypass recuperador abierto
        :return:  Velocidad seleccionada o caudal actual
        """
        print(f"Activando modo ventilación en el recuperador {self.name}")
        await self.set_valv_pos(phi.CLOSED)
        await self.set_dampers_pos(phi.CLOSED)  # Compuerta de aire exterior abierta y la de recirculación cerrada

        por_caudal = True if self.max_airflow is not None else False
        if por_caudal:
            default_airflow = self.max_airflow * phi.HRU_VENTILATION_AFLOWPCT / 100  # % por defecto del caudal
            # máximo de aire para modo ventilación
        else:
            default_airflow = None
        if not self.groups:
            res = await self.set_speed(phi.HRU_VENTILATION_SPEED)
            res = await self.set_airflow(default_airflow)
        group_id = self.groups[0]  # El recuperador sólo puede estar asociadoa un grupo de habitaciones
        group = phi.all_room_groups.get(group_id)
        group_aq = group.aq  # Máximo contenido en CO2 de las habitaciones del grupo (valor mínimo = 0)
        group_aq_sp = group.aq_sp  # Mínima consigna de nivel de CO2 de las habitaciones del grupo con
        # necesidad de ventilación
        if por_caudal:  # Hay que asignar caudal de aire en lugar de velocidades de recuperador
            if group_aq == 0:  # No se lee la calidad de calire => Caudal por defecto
                ventilation_airflow = default_airflow
            else:
                airflow_limits = list(map(lambda x: int(group_aq_sp + (group_aq_sp * 1.2 - group_aq_sp) / 9 * x),
                                          range(10)))
                max_af_pct = bisect(airflow_limits, group_aq) / 10
                ventilation_airflow = int(
                    self.max_airflow * max_af_pct)  # Se fija el caudal de aire en función de la calidad.
                # Se impulsa el caudal máximo cuando la calidad de aire supera en un 20% la consigna de calidad de aire
            res = await self.set_airflow(ventilation_airflow)
            return ventilation_airflow

        else:  # Hay que fijar la velocidad del ventilador del recuperador
            if group_aq == 0:  # No se lee la calidad de calire => Velocidad por defecto
                speed = phi.HRU_VENTILATION_SPEED
            else:
                speed_limits = list(map(lambda x: int(group_aq_sp + (group_aq_sp * 1.2 - group_aq_sp) / 2 * x),
                                        range(1, 3)))  # Lista de caudales para seleccionar la velocidad
                speed = bisect(speed_limits, group_aq) + 1  # Velocidad 3 si la calidad de aire supera en un 20%
                # la consigna
                res = await self.set_speed(speed)
            return speed

    async def set_man_op_mode(self):
        """
        Activa manualmente el modo de funcionamiento del recuperador
        self.man_op_mode values:
            0: HRU off
            1: DESHUMIDIFICACION
            2: FANCOIL / APOYO A LA CLIMATIZACIÓN
            4: FREE_COOLING
            5: FREE_COOLING + DESHUMIDIFICACIÓN  - Opción no disponible
            6: FREE_COOLING + FANCOIL
            8: VENTILACIÓN
        Param:

        Returns:

        """
        if self.man_hru_mode_st == phi.ON:  # Modo manual de funcionamiento del recuperador activado
            rest = await self.activate_op_mode(self.man_hru_mode)
            self.hru_mode = self.man_hru_mode

    async def activate_op_mode(self, new_op_mode: [int, None] = None):
        """
        Procesa el modo de funcionamiento del recuperador cuando está activo en modo auto o bien
        Activa el modo de funcionamiento new_op_mode
        new_op_mode values:
            0: HRU off
            1: DESHUMIDIFICACION
            2: FANCOIL / APOYO A LA CLIMATIZACIÓN
            4: FREE_COOLING
            5: FREE_COOLING + DESHUMIDIFICACIÓN
            6: FREE_COOLING + FANCOIL
            8: VENTILACIÓN
        Param:

        Returns:
            Modo iv o None si falta algún dato
        """
        modes = {0: self.off_mode,
                 1: self.dehumidification_mode,
                 2: self.fancoil_mode,
                 4: self.freecooling_mode,
                 5: (self.dehumidification_mode, self.freecooling_mode),
                 6: (self.fancoil_mode, self.freecooling_mode),
                 8: self.ventilation_mode}

        if all(not x for x in self.hru_modes.values()) or new_op_mode == phi.OFF:
            # Ningún modo activado o se quiere parar el HRU
            res = await self.off_mode()
            self.onoff = phi.OFF
            return phi.OFF

        if new_op_mode in modes.keys():
            op_mode = modes.get(new_op_mode)
            if isinstance(op_mode, tuple):
                for op in op_mode:
                    res = op()
            else:
                res = op_mode()
            return new_op_mode

        res = await self.get_op_mode()  # Determino el modo de funcionamiento

        freecooling = True if self.hru_modes.get(phi.FREE_COOLING) else False
        # El modo freecooling es compatible con los modos DESHUMIDIFICACIÓN y FANCOIL

        if self.hru_modes.get(phi.DESHUMIDIFICACION):
            res = await self.dehumidification_mode()
            if freecooling:
                res = await self.freecooling_mode()
                return phi.DH_FREEC
            else:
                return phi.DESHUMIDIFICACION
        elif self.hru_modes.get(phi.FANCOIL):
            res = await self.fancoil_mode()
            if freecooling:
                res = await self.freecooling_mode()
                return phi.FC_FREEC
            else:
                return phi.FANCOIL
        else:
            res = await self.ventilation_mode()
            return phi.VENTILACION

    async def upload(self):
        """
        Escribe en el dispositivo ModBus los valores actuales de sus atributos tipo RW:
        "onoff", "manual", "manual_speed", "manual_airflow", "man_hru_mode_st", "man_hru_mode"
        :return:
        """
        available_modes = (0, 1, 2, 4, 6, 8)
        if self.manual:
            if None not in (self.speed, self.manual_speed):
                await self.set_speed(self.manual_speed)
            elif None not in (self.get_airflow(), self.manual_airflow):
                await self.set_airflow(self.manual_airflow)
            await self.set_valv_pos(self.man_valv_pos)
            await self.set_dampers_pos(self.man_dampers_pos)
        if self.man_hru_mode_st and self.man_hru_mode in available_modes:
            await self.set_man_op_mode()
        if self.onoff == phi.OFF:
            await self.off_mode()
        return 1

    async def update(self):
        """
        Propaga al recuperador el modo de funcionamiento y almacena los valores de los distintos atributos
        definidos en phi.HEATRECOVERYUNIT_R_FILES en los archivos correspondientes de phi.HEATRECOVERYUNIT_R_FILES
        TODO comprobar modificaciones desde la web como la consigna de AQ, el on/off, la velocidad del ventilador,
        TODO o el estado de válvula y compuertas
        El valor de self.manual tiene prioridad sobre set_man_op_mode.
        Returns: resultado de la escritura modbus de los valores actualizados
        """
        if self.manual:
            print(f"update {self.name} - Modo manual activado")
            if None not in (self.exhaust_flow_source, self.manual_airflow):
                await self.set_airflow(self.manual_airflow)
            elif None not in (self.speed1_source, self.manual_speed):
                await self.set_manual_speed()
            await self.set_valv_pos(self.man_valv_pos)
            await self.set_dampers_pos(self.man_dampers_pos)

        elif self.man_hru_mode_st == phi.ON:
            await self.set_man_op_mode()
        else:
            self.hru_mode = await self.activate_op_mode()  # Modo de funcionamiento seleccionado

        await update_xch_files_from_devices(self)  # Guarda los valores del dispositivo en el archivo de intercambio
        # correspondiente

    def __repr__(self):
        """
        Para imprimir la información actual del fancoil
        :return:
        """
        onoff = {0: "Parado", 1: "En Marcha"}
        modo = {0: "Calefacción", 1: "Refrigeración"}
        demanda = {0: "No hay demanda", 1: "Demanda de calor", 2: "Demanda de frío"}
        manual = {0: "Automático", 1: "Manual"}
        por_caudal = True if self.max_airflow is not None else False
        hru_modes_descr = {0: "Parado",
                           1: "Modo Deshumidificación",
                           2: "Modo Fancoil",
                           4: "Modo Free-cooling",
                           5: "Modo Deshumidificación + Freecooling",
                           6: "Modo Fancoil + Freecooling",
                           8: "Modo Ventilación"}
        dev_info = f"\nRecuperador {self.name}\n"
        dev_info += f"\tEstado: {onoff.get(self.onoff)}\n"
        dev_info += f"\tModo de funcionamiento: {hru_modes_descr.get(self.hru_mode)}\n"
        dev_info += f"\tModo manual ventilador {manual.get(self.manual)}\n"
        if por_caudal:
            dev_info += f"\tCaudal del recuperador: {self.supply_flow}\n"
        else:
            dev_info += f"\tVelocidad ventilador: {self.speed}\n"
        dev_info += f"\tEstado compuertas: {self.dampers_st}\n"
        dev_info += f"\tEstado válvula: {self.valv_st}\n"
        return dev_info


class AirZoneManager(phi.MBDevice):
    """
    Controlador para Zonificación por aire sistema Phoenix.
    Dispositivo especial SIG510
    NOTA: LOS ATRIBUTOS DE ESTA CLASE DEBEN COINCIDIR CON LAS CLAVES DEL JSON AIRZONEMANAGERS.JSON EN LA
    CARPETA DE PROJECT_ELEMENTS.
    Este tipo de AirZoneManager se utilizó en Finestrat-Atenas 47 y es distinto del de Serrano
    TODO Unificar criterios para AirZoneManagers
    Controla fancoils a 2 tubos. Aparentemente, la válvula abre o cierra por demanda
    El zonificador estará asociado a un grupo de habitaciones.
    Al actualizar el controlador se recoge la consigna y la temperatura calculadas para el grupo de
    habitaciones asociado y se propaga al zonificador correspondiente, así como su modo de funcionamiento
    calefacción/refrigeración.
    Param: device: dispositivo ModBus con el mapa de registros a mapear para las operaciones con el controlador SIG510.
    Param: groups: grupos de habitaciones vinculados al dispositivo. Cada zonificador (fancoil) sólo puede estar
    asociado a un grupo de habitaciones. Si se introduce más de 1, sólo se utiliza el primero de ellos.
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
        self.onoff_target = None  # Orden Marcha/Paro fancoil
        self.onoff_st = None
        self.iv_source = None  # Tipo registro y dirección modbus Modo de funcionamiento calefacción/refrigeración
        self.iv = None  # Modo de funcionamiento calefacción/refrigeración
        self.sp_source = None  # Tipo registro y dirección modbus Consigna fancoil zonificador
        self.sp = None  # Consigna de funcionamiento fancoil zonificador
        self.rt_source = None  # Tipo registro y direccion modbus Temperatura ambiente fancoil zonificador
        self.rt = None  # Temperatura de funcionamiento del fancoil zonificador
        self.fan_manual_speed_mode = False
        self.fan_manual_speed = 1
        self.fan_auto_cont_source = None  # Tipo registro y direccion modbus funcionamiento auto-continuo del ventilador
        self.fan_auto_cont = None  # Funcionamiento auto-continuo del ventilador
        self.fan_st_source = None  # Tipo registro y direccion modbus estado del ventilador
        self.fan_speed_target = None  # Tipo registro y direccion modbus velocidad actual del ventilador
        self.fan_speed = None  # Velocidad actual del zonificador
        self.sp1_source = None  # Tipo registro y dirección modbus Consigna Zona 1
        self.sp1 = None  # Consigna Zona 1
        self.rt1_source = None  # Tipo registro y dirección modbus Temperatura ambiente Zona 1
        self.rt1 = None  # Consigna Zona 1
        self.sp2_source = None  # Tipo registro y dirección modbus Consigna Zona 2
        self.sp2 = None  # Consigna Zona 2
        self.rt2_source = None  # Tipo registro y dirección modbus Temperatura ambiente Zona 2
        self.rt2 = None  # Consigna Zona 2
        self.demanda_st_source = None
        self.demand = None
        self.damper_st_source = None
        self.damper1_st = None  # Estado rejilla 1
        self.damper2_st = None  # Estado rejilla 2
        self.remote_onoff_st_source = None  # Tipo registro y direccion modbus para on/off remoto del fancoil
        self.remote_onoff = None  # Valor del registro 18: on/off remoto del fancoil. 0:por modbus / 1:por ED
        self.aux_eds_source = None  # Tipo registro y direccion modbus estado de las entradas digitales auxiliares
        self.ed1_aux = None  # Estado entrada digital 1
        self.ed2_aux = None  # Estado entrada digital 2
        self.ed3_aux = None  # Estado entrada digital 3

    async def onoff(self, new_status: [int, None] = None):
        """
        Arranca o para el zonificador según el valor 1 (arrancar) o 0 (parar) del parámetro new_status
        Si new_status es None, devuelve el estado actual, leído en el byte alto del registro 21
        Returns: Estado onoff del zonificador o None si falta algún dato
        """
        if self.onoff_target is None:
            return
        st_datatype = self.fan_st_source[0]
        st_adr = self.fan_st_source[1]
        datatype = self.onoff_target[0]
        adr = self.onoff_target[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": st_datatype,
                  "adr": st_adr}

        # Recojo el estado actual del fancoil
        current_st = get_value(source)  # El registro 18 del SIG510 devuelve el estado del ventilador
        # 0: off, 1: vel. baja, 2: vel. media y 3:vel. alta
        if new_status is None:
            self.onoff_st = 0 if current_st == 0 else 1
        elif new_status not in [0, 1]:
            print(f"ERROR - El valor {new_status} no es válido para arrancar o parar el zonificador {self.name}.\n"
                  f"Valores válidos son 1 para arrancar ó 0 para parar")
            self.onoff_st = 0 if current_st == 0 else 1
        else:
            res = await set_value(target, new_status)
            dbval = save_value(target, new_status)
            self.onoff_st = new_status
        return self.onoff_st

    async def demanda_st(self):
        """
        Devuelve el valor de la demanda del fancoil
        Returns:
            0: No hay demanda
            1: Demanda de refrigeración
            2: Demanda de calefacción
        """
        if self.demanda_st_source is None:
            return
        datatype = self.demanda_st_source[0]
        adr = self.demanda_st_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}

        # Recojo el estado actual del fancoil
        current_demand = get_value(source)  # El registro 19 del SIG510 0: si no hay demanda, 1: demanda
        # de refrigeración, 2: demanda de calefacción
        self.demand = current_demand
        return self.demand

    async def iv_mode(self, new_iv_mode: [int, None] = None):
        """
        Procesa el modo de funcionamiento:
        Ventilación (new_iv_mode = 0),
        Refrigeración (new_iv_mode = 1),
        Calefacción (new_iv_mode = 2)
        del zonificador.
        Param:
            new_iv_mode:
                Si None, se devuelve el modo actual
                Si 0, se activa el modo ventilación en el zonificador
                Si 1, se activa el modo refrigeración en el zonificador
                Si 2, se activa el modo calefacción en el zonificador
        Returns:
            Modo iv o None si falta algún dato
        """
        if self.iv_source is None:
            return
        datatype = self.iv_source[0]
        adr = self.iv_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        # Recojo el modo actual de funcionamiento del fancoil
        current_iv_value = get_value(target)
        if new_iv_mode is None or new_iv_mode not in [0, 1, 2]:
            self.iv = current_iv_value
        # Se activa el modo indicado en iv_mode
        elif new_iv_mode in [0, 1, 2]:
            res = await set_value(target, new_iv_mode)
            dbval = save_value(target, new_iv_mode)
            self.iv = new_iv_mode
        else:
            print(f"ERROR - Modo calefacción/refrigeración {new_iv_mode} no válido para el zonificador {self.name}")
            return
        return self.iv

    async def set_sp(self, new_sp_value: [int, float, None] = None, target: [int, None] = None):
        """
        Propaga la consigna new_sp_value al target.
        Target puede ser:
        None ó 0: la consigna se aplica al zonificador
        1: la consigna se aplica para la zona 1
        2: la consigna se aplica para la zona 2
        Si new_sp_value es None, devuelve la consigna actual de target leída del diccionario
        que almacena las lecturas modbus.
        Si no, fija la consigna de funcionamiento del zonificador
        Param:
            new_sp_value: Consigna a pasar al target. Se introduce el valor deseado. Se le aplica la función de
            conversión necesaria en el momento de escribir. Es decir se escribe el valor real, o sea, 20 °C, no 200
        Returns:
            Consigna activa del target o None si falta algún dato
        """
        sources = {0: self.sp_source, 1: self.sp1_source, 2: self.sp2_source}
        sp_source = sources.get(0) if target is None else sources.get(target)
        targets = {0: "sp", 1: "sp1", 2: "sp2"}
        sp_target = targets.get(0) if target is None else targets.get(target)
        target_names = {0: "Zonificador", 1: "Zona 1", 2: "Zona 2"}
        target_name = target_names.get(0) if target is None else target_names.get(target)

        if sp_source is None:
            return
        datatype = sp_source[0]
        adr = sp_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_sp = get_value(value_source=source)
        if new_sp_value is None:
            self.__setattr__(sp_target, current_sp)
        elif new_sp_value > 35 or new_sp_value < 10:
            print(f"{self.name}: ERROR estableciendo una consigna de {new_sp_value} en {target_name} "
                  f"(rango 10-35)")
            self.__setattr__(sp_target, current_sp)
        else:
            print(f"airzonemanager.set_sp: Actualizando consigna con valor {new_sp_value} en {target_name}")
            res = await set_value(source, new_sp_value)
            dbval = save_value(source, new_sp_value)
            # self.__setattr__(sp_target, new_sp_value)
            setattr(self, sp_target, new_sp_value)
        # return self.__getattribute__(sp_target)
        return getattr(self, sp_target)

    async def set_rt(self, new_rt_value: [int, float, None] = None, target: [int, None] = None):
        """
        Propaga la temperatura new_rt_value al target.
        Target puede ser:
        None ó 0: la temperatura se aplica al zonificador
        1: la consigna se aplica para la zona 1
        2: la consigna se aplica para la zona 2
        Si new_rt_value es None, devuelve la temperatura actual de target leída del diccionario
        que almacena las lecturas modbus.
        Si no, fija la temperatura de funcionamiento del zonificador
        Param:
            new_rt_value: Temperatura a pasar al target. Se introduce el valor deseado. Se le aplica la función de
            conversión necesaria en el momento de escribir. Es decir se escribe el valor real, o sea, 20 °C, no 200
        Returns:
            Temperatura activa del target o None si falta algún dato
        """
        sources = {0: self.rt_source, 1: self.rt1_source, 2: self.rt2_source}
        rt_source = sources.get(0) if target is None else sources.get(target)
        targets = {0: "rt", 1: "rt1", 2: "rt2"}
        rt_target = targets.get(0) if target is None else targets.get(target)
        target_names = {0: "Zonificador", 1: "Zona 1", 2: "Zona 2"}
        target_name = target_names.get(0) if target is None else target_names.get(target)

        if rt_source is None:
            return
        datatype = rt_source[0]
        adr = rt_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_rt = get_value(value_source=source)
        if new_rt_value is None:
            self.__setattr__(rt_target, current_rt)
        elif new_rt_value > 50 or new_rt_value < 0:
            print(f"{self.name}: ERROR estableciendo una temperatura de {new_rt_value} en {target_name} "
                  f"(rango 0-50)")
            self.__setattr__(rt_target, current_rt)
        else:
            print(f"airzonemanager.set_rt: Actualizando temperatura con valor {new_rt_value} en {target_name}")
            res = await set_value(source, new_rt_value)
            dbval = save_value(source, new_rt_value)
            setattr(self, rt_target, new_rt_value)
            # self.__setattr__(rt_target, new_rt_value)
        # return self.__getattribute__(rt_target)
        return getattr(self, rt_target)

    async def fan_auto_cont_mode(self, new_fan_auto_cont_mode: [int, None] = None):
        """
        Si el parámetro fan_auto_cont_mode es None, devuvelve la configuración del ventilador del fancoil.
        Auto si fan_auto_cont_mode = 0
        Continuo si fan_auto_cont_mode = 1
        Returns:
            0 para ventilador auto
            1 para ventilador continuo
            None si falta algún dato

        """
        AUTO = 0
        CONTINUO = 1
        if self.fan_auto_cont_source is None:
            return
        datatype = self.fan_auto_cont_source[0]
        adr = self.fan_auto_cont_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        # Recojo el valor actual del registro a actualizar
        current_auto_cont_mode = get_value(value_source=source)
        if new_fan_auto_cont_mode is not None:
            res = await set_value(source, new_fan_auto_cont_mode)  # Escritura en el dispositivo ModBus
            dbval = save_value(source, new_fan_auto_cont_mode)

        self.fan_auto_cont = CONTINUO if new_fan_auto_cont_mode == CONTINUO else AUTO
        return self.fan_auto_cont

    async def manual_fan_speed(self, manual_mode: int = phi.OFF, man_speed: [int, None] = None) -> \
            [int, None]:
        """
        Ajusta manualmente la velocidad del zonificador según el valor de man_speed:
        0: Velocidad baja
        1: Velocidad media
        2: Velocidad alta
        Si man_speed es None, devuelve la velocidad actual del zonificador
        Param:
            man_speed

        Returns: Velocidad seleccionada del zonificador
        """
        if self.fan_speed_target or self.fan_st_source is None:
            return
        if self.fan_manual_speed_mode != manual_mode:
            self.fan_manual_speed_mode = manual_mode
        current_speed_datatype = self.fan_st_source[0]
        current_speed_adr = self.fan_st_source[1]
        current_speed_source = {"bus": int(self.bus_id),
                                "device": int(self.device_id),
                                "datatype": current_speed_datatype,
                                "adr": current_speed_adr}

        manual_speed_datatype = self.fan_speed_target[0]
        manual_speed_adr = self.fan_speed_target[1]
        manual_speed_target = {"bus": int(self.bus_id),
                               "device": int(self.device_id),
                               "datatype": manual_speed_datatype,
                               "adr": manual_speed_adr}
        # Recojo el valor actual de la velocidad manual
        current_speed = get_value(value_source=current_speed_source)
        if manual_mode == phi.OFF:
            # Selecciono velocidad automática del ventilador
            auto_speed = 3  # 3 es velocidad automática del ventilador
            res = await set_value(manual_speed_target, auto_speed)
            dbval = save_value(manual_speed_target, auto_speed)
            self.fan_speed = auto_speed
        elif man_speed is None:
            self.fan_speed = current_speed
        elif man_speed not in [0, 1, 2, 3]:
            self.fan_speed = current_speed
            print(f"ERROR - No se puede fijar una velocidad de {man_speed} en el fancoil {self.name}.\n"
                  f"Rango: (0, 1, 2, 3)")
        else:
            res = await set_value(manual_speed_target, man_speed)
            dbval = save_value(manual_speed_target, man_speed)
            self.fan_speed = man_speed
        return self.fan_speed

    async def remote_onoff_mode(self, onoff_mode: [int, None] = None):
        """
        Configura el on/off remoto del zonificador.
        Param:
            onoff_mode:
                Si onoff_mode vale 0, el marcha/paro del fancoil se hace por ModBus.
                Si vale 1, se hace en función de la entrada digital (registro 21)
                    Arranca o para el fancoil según el valor 1 (arrancar) o 0 (parar) del registro 21
                Si onoff_mode es None, devuelve la configuración actual del remote_onoff
        Returns:
            Configuración del onoff remoto del fancoil o None si falta algún dato

        """
        if self.remote_onoff_st_source is None:
            return
        datatype = self.remote_onoff_st_source[0]
        adr = self.remote_onoff_st_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        # Recojo el estado actual del fancoil
        current_status = get_value(source)
        if onoff_mode is None:
            self.remote_onoff = current_status
        else:
            res = await set_value(source, onoff_mode)
            dbval = save_value(source, onoff_mode)
            self.remote_onoff = onoff_mode
        return self.remote_onoff

    async def get_dampers_st(self):
        """
        Devuelve el estado de las rejillas de las zonas 1 y 2, almacenados en los bytes alto y bajo del registro 21
        Param:
        Returns:
            Estado 0/1 de las 2 rejillas

        """
        if self.damper_st_source is None:
            return
        datatype = self.damper_st_source[0]
        adr = self.damper_st_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        # Recojo el estado actual del registro que almacena la posición de las rejillas
        current_status = get_value(source)  # Tupla con los estados de las rejillas
        if current_status is None:
            print(f"ERROR recuperando el estado de las rejillas del zonificador {self.name}")
            return
        self.damper1_st = current_status[0]
        self.damper2_st = current_status[1]
        return self.damper1_st, self.damper2_st

    async def ed_aux_st(self):
        """
        Devuelve el estado de las 3 entradas digitales auxiliares del SIG510 almacenado en los bits 0, 1 y 2
        del registro 22
        Param:
        Returns:
            Estado 0/1 de las 3 entradas digitales

        """
        if self.aux_eds_source is None:
            return
        datatype = self.aux_eds_source[0]
        adr = self.aux_eds_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        # Recojo el estado actual de las entradas digitales
        current_status = get_value(source)  # Tupla con los valores de los 16 bits del registro 22
        if current_status is None:
            print(f"ERROR recuperando el estado de las entradas digitales auxiliares del zonificador {self.name}")
            return
        self.ed1_aux = current_status[0]
        self.ed2_aux = current_status[1]
        self.ed3_aux = current_status[2]
        return self.ed1_aux, self.ed2_aux, self.ed3_aux

    async def upload(self):
        """
        Escribe en el dispositivo ModBus los valores actuales de sus atributos tipo RW:
        Consignas y modo IV
        :return:
        """
        pass
        return 1

    async def update(self):
        """
        Propaga al zonificador el modo de funcionamiento, el estado on/off, la consigna y la temperatura del grupo
        de habitaciones asociado y actualiza el estado de sus atributos.
        También propaga la consigna y la temperatura ambiente de las zonas 1 y 2 para el funcionamiento de las rejillas.
        Returns: resultado de la escritura modbus de los valores actualizados
        """
        roomgroup = phi.all_room_groups.get(self.groups[0])  # Accedo al grupo de habitaciones del zonificador
        room1 = roomgroup.roomgroup[0]
        room2 = roomgroup.roomgroup[1]
        sp1 = room1.get_sp()
        rt1 = room1.get_rt()
        sp2 = room2.get_sp()
        rt2 = room2.get_rt()
        await self.set_sp(sp1, 1)  # Actualizo la consigna de la zona 1
        await self.set_rt(rt1, 1)  # Actualizo la temperatura ambiente de la zona 1
        await self.set_sp(sp2, 2)  # Actualizo la consigna de la zona 2
        await self.set_rt(rt2, 2)  # Actualizo la temperatura ambiente  de la zona 2

        with open(phi.ROOMGROUPS_VALUES_FILE, "r") as f:
            roomgroups_values = json.load(f)

        roomgroup_vals = roomgroups_values.get(self.groups[0])  # Datos del grupo de habitaciones asociado al fancoil
        if roomgroup_vals is None:
            print(f"No se ha encontrado información del grupo de habitaciones {self.groups[0]}")

        group_iv = await self.iv_mode(roomgroup_vals.get("iv"))  # 0:Calefaccion / 1:Refrigeracion en el grupo
        # de habitaciones; Calefacción es 2 en el zonificador
        self.iv = 1 if group_iv == 1 else 2
        zonificador_sp = roomgroup_vals.get("air_sp") + phi.OFFSET_COOLING if self.iv == 1 \
            else roomgroup_vals.get("air_sp") + phi.OFFSET_HEATING  # Offset heating tiene un valor negativo
        self.sp = await self.set_sp(new_sp_value=zonificador_sp)
        zonificador_rt = roomgroup_vals.get("air_rt")
        self.rt = await self.set_rt(new_rt_value=zonificador_rt)
        self.onoff_st = await self.onoff()
        self.demand = await self.demanda_st()
        self.iv = await self.iv_mode()
        self.fan_auto_cont = await self.fan_auto_cont_mode()
        if self.fan_manual_speed_mode:
            self.fan_speed = await self.manual_fan_speed(manual_mode=phi.ON, man_speed=self.fan_manual_speed)
        else:
            self.fan_speed = await self.manual_fan_speed(manual_mode=phi.OFF)
        self.remote_onoff = await self.remote_onoff_mode()
        eds_st = await self.ed_aux_st()
        if eds_st is not None:
            self.ed1_aux, self.ed2_aux, self.ed3_aux = eds_st
        dampers_st = await self.get_dampers_st()
        if dampers_st is not None:
            self.damper1_st, self.damper2_st = dampers_st
        await update_xch_files_from_devices(self)  # Guarda los valores del dispositivo en el archivo de intercambio
        # correspondiente

    def __repr__(self):
        """
        Para imprimir la información actual del fancoil
        :return:
        """
        onoff = {0: "Parado", 1: "En Marcha"}
        modo = {0: "Calefacción", 1: "Refrigeración"}
        demanda = {0: "No hay demanda", 1: "Demanda de calor", 2: "Demanda de frío"}
        manual = {0: "Automático", 1: "Manual"}
        estado_manual_ventilador = self.fan_manual_speed_mode
        dev_info = f"\nFancoil {self.name}\n"
        dev_info += f"\tEstado: {onoff.get(self.onoff_st)}\n"
        dev_info += f"\t:Modo de funcionamiento: {modo.get(self.iv)}\n"
        dev_info += f"\t:Consigna {self.sp}\n"
        dev_info += f"\t:Temperatura ambiente {self.rt}\n"
        dev_info += f"\t:Demanda {demanda.get(self.demand)}\n"
        dev_info += f"\t:Velocidad {self.fan_speed}\n"
        dev_info += f"\t:Modo ventilador {manual.get(estado_manual_ventilador)}\n"
        return dev_info


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
    Las temperaturas de impulsión de cada circuito se leen con los métodos get_ti1, get_ti2 y get_tit3 para
    los circuitos 1, 2 y 3 respectivamente.
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
        self.iv1_source = None  # Tipo de registro y registro modbus modo de funcionamiento cal/ref circuito 1
        self.iv1 = None  # Modo de funcionamiento Off/Refrigeración/Calefacción circuito 1
        self.st1_target = None  # Tipo de registro y registro modbus marcha/Paro bomba circuladora circuito 1
        self.act_man_st1 = 0  # Activación modo manual control bomba circuladora circuito 1
        self.man_st1 = 1  # Valor manual funcionamiento bomba circuladora circuito 1
        self.st1 = None  # Estado actual bomba circuladora circuito 1
        self.sp1_source = None  # Tipo de registro y registro modbus consigna de impulsión circuito 1
        self.act_man_sp1 = 0  # Activación selección manual consigna impulsión circuito 1
        self.man_sp1 = 25  # Valor manual consigna impulsión circuito 1
        self.sp1 = None  # Valor actual consigna impulsión circuito 1
        self.ti1_source = None  # Tipo de registro y registro modbus temperatura de impulsión circuito 1
        self.ti1 = None  # Temperatura impulsión circuito 1
        self.v1_source = None  # Tipo de registro y registro modbus Apertura válvula circuito 1
        self.v1 = None  # % Apertura válvula circuito 1
        self.iv2_source = None  # Tipo de registro y registro modbus modo de funcionamiento cal/ref circuito 2
        self.iv2 = None  # Modo de funcionamiento Off/Refrigeración/Calefacción circuito 2
        self.st2_target = None  # Tipo de registro y registro modbus marcha/Paro bomba circuladora circuito 2
        self.act_man_st2 = 0  # Activación modo manual control bomba circuladora circuito 2
        self.man_st2 = 1  # Valor manual funcionamiento bomba circuladora circuito 2
        self.st2 = None  # Estado actual bomba circuladora circuito 2
        self.sp2_source = None  # Tipo de registro y registro modbus consigna de impulsión circuito 2
        self.act_man_sp2 = 0  # Activación selección manual consigna impulsión circuito 2
        self.man_sp2 = 25  # Valor manual consigna impulsión circuito 2
        self.sp2 = None  # Valor actual consigna impulsión circuito 2
        self.ti2_source = None  # Tipo de registro y registro modbus temperatura de impulsión circuito 2
        self.ti2 = None  # Temperatura impulsión circuito 2
        self.v2_source = None  # Tipo de registro y registro modbus Apertura válvula circuito 2
        self.v2 = None  # % Apertura válvula circuito 2
        self.iv3_source = None  # Tipo de registro y registro modbus modo de funcionamiento cal/ref circuito 3
        self.iv3 = None  # Modo de funcionamiento Off/Refrigeración/Calefacción circuito 3
        self.st3_target = None  # Tipo de registro y registro modbus marcha/Paro bomba circuladora circuito 3
        self.act_man_st3 = 0  # Activación modo manual control bomba circuladora circuito 3
        self.man_st3 = 1  # Valor manual funcionamiento bomba circuladora circuito 3
        self.st3 = None  # Estado actual bomba circuladora circuito 3
        self.sp3_source = None  # Tipo de registro y registro modbus consigna de impulsión circuito 3
        self.act_man_sp3 = 0  # Activación selección manual consigna impulsión circuito 3
        self.man_sp3 = 25  # Valor manual consigna impulsión circuito 3
        self.sp3 = None  # Valor actual consigna impulsión circuito 3
        self.ti3_source = None  # Tipo de registro y registro modbus temperatura de impulsión circuito 3
        self.ti3 = None  # Temperatura impulsión circuito 3
        self.v3_source = None  # Tipo de registro y registro modbus Apertura válvula circuito 3
        self.v3 = None  # % Apertura válvula circuito 3
        self.st4_source = None  # Salida digital 4
        self.st4 = None  # Estado actual salida digital 4

    async def onoff(self, circuit: int = 1, new_st_value: [int, None] = None):
        """
        Arranca o para la bomba circuladora del circuito 'circuit' si existe new_st_value.
        Este método se utiliza en el funcionamiento automático del control de temperatura de impulsión
        Si no, devuelve el estado de la bomba del circuito 'circuit'
        Param:
            new_st_value: Nuevo estado para la bomba
            circuit: Circuito al que aplicar el estado: 1, 2 ó 3.
        Returns: Estado de la bomba circuladora circuito 'circuit'
        """
        target_id = "st"+str(circuit)+"_target"
        state_id = "st"+str(circuit)
        st_target = getattr(self, target_id)
        st_value = getattr(self, state_id)
        if st_target is None or circuit not in (1, 2, 3):
            return
        datatype = st_target[0]
        adr = st_target[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_st = get_value(target)
        if not new_st_value is None:
            if new_st_value not in [phi.OFF, phi.ON]:
                print(f"{self.name}: Error accionando la bomba del circuito {circuit} con el valor {new_st_value}")
                val_to_write = current_st
            else:
                val_to_write = new_st_value
        else:
            val_to_write = current_st

        setattr(self, state_id, val_to_write)
        if val_to_write == current_st:
            print(f"No cambia el estado de la bomba del circuito {circuit} de {self.name}")
            return current_st  
        res = await set_value(target, val_to_write)  # Escritura Modbus
        dbval = save_value(target, val_to_write)  # se guarda el valor a escribir en el json con las lecturas
        state = getattr(self, state_id)
        return state  # devuelve el estado actual del modo on-off


    async def man_onoff(self, circuit: int = 1, new_man_mode: [int, None] = None) -> [phi.Tuple[int, int], None]:
        """
        Activa y desactiva el modo manual de funcionamiento de la bomba circuladora del circuito 'circuit' y, cuando
        está activado, la arranca o para dependiendo del valor de new_st_value
        parameters:
        circuit: identificación del circuito a procesar
        new_man_mode: nuevo valor del funcionamiento manual del circuito
        Si new_man_mode es None, devuelve el valor de activación del modo manual: 1:activado / 0:desactivado
        Returns: Tupla con el estado del modo manual y valor manual configurado para la bomba
        """
        if circuit not in (1, 2, 3):
            print(f"ERROR intentando activar MANUALMENTE el circuito {circuit} de {self.name}")
            return

        manual_activation_attribute = "act_man_st" + str(circuit)
        manual_state_attribute = "man_st" + str(circuit)
        current_manual_state = getattr(self, manual_activation_attribute)
        current_manual_value = getattr(self, manual_state_attribute)

        if not new_man_mode is None and new_man_mode in (phi.ON, phi.OFF):  # se ha activado el modo manual
            # el valor de manual_state_attribute se escribe desde la web
            # se propaga el valor manual de la bomba al circuito correspondiente
            setattr(self, manual_activation_attribute, new_man_mode)
            await self.onoff(circuit, manual_state_attribute)

        if not new_man_mode is None:
            if new_man_mode not in [phi.OFF, phi.ON]:  # Activación manual incorrecta
                print(f"{self.name}: Error activando el modo manual de la bomba del circuito {circuit} "
                      f"con el valor {new_man_mode}")
                val_to_write = current_manual_state
            else:
                val_to_write = new_man_mode
        else:
            val_to_write = current_manual_state

        if val_to_write == current_manual_state:
            print(f"No cambia el estado de activación manual de la bomba del circuito {circuit} de {self.name}")
            return current_manual_state, current_manual_value

        setattr(self, current_manual_state, val_to_write)  # se actualiza el atributo del estado del modo manual
        # el valor del modo manual, man_stx sólo se activa desde la web
        manual_state = getattr(self, manual_activation_attribute)
        manual_value = getattr(self, manual_state_attribute)

        return manual_state, manual_value


    async def iv_mode(self, circuit: int = 1, new_iv_mode: [int, None] = None) -> [int, None]:
        """
        Si new_iv_mode es None, devuelve el modo de funcionamiento del circuito 'circuit'
        Param:
            circuit: circuito en el que se gestiona el modo off/refrigeración/calefacción
            new_iv_mode: modo a propagar al controlador de temperatura de impulsión
            0: Off
            1: Frío
            2: Calor
        Returns: Modo actual de funcionamiento del circuito 
        """
        source = "iv" + str(circuit) + "_source"
        mode_attr = "iv" + str(circuit)

        iv_mode_source = getattr(self, source)
        if iv_mode_source is None or circuit not in (1, 2, 3):
            return
        datatype = iv_mode_source[0]
        adr = iv_mode_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}

        current_iv_sp = get_value(value_source=target)  # El SIG610 almacena CONSIGNA en byte bajo y MODO en byte alto
        if current_iv_sp is not None:
            current_iv, current_sp = current_iv_sp
            print(f"Modo off/frio/calor actual del circuito {circuit} de {self.name}: {current_iv}")
            print(f"Consigna actual del circuito {circuit} de {self.name}: {current_sp}")
        else:
            print(f"No se ha podido leer el modo del circuito {circuit} de {self.name}")
            return
        if not new_iv_mode is None:
            if new_iv_mode not in [0, 1, 2]:
                print(f"{self.name}: Error activando el modo del circuito {circuit} con el valor {new_iv_mode}")
                mode_to_write = current_iv
                # Se mantiene el modo actual
            else:
                # Se propaga el nuevo modo de funcionamiento
                mode_to_write = new_iv_mode

            if mode_to_write == current_iv:
                return current_iv  # No ha cambiado el modo. No hay nada que actualizar

            # Actualizo el valor del modo de funcionamiento (byte alto)
            new_val = set_hb(current_iv_sp, int(mode_to_write))
            dbval = save_value(target, new_val)
            res = await set_value(target, new_val)  # Escritura Modbus
            setattr(self, mode_attr, mode_to_write)
        mode = getattr(self, mode_attr)
        return mode

    async def sp(self, circuit: int = 1, new_sp: [int, None] = None) -> [int, None]:
        """
        Si new_sp es None, devuelve el valor actual de la consigna del circuito 'circuit'
        Param:
            circuit: circuito en el que se gestiona la consigna de temperatura de impulsión de agua
            new_sp: Nueva consigna a aplicar
        Returns: Consigna de control de temperatura de impulsión de agua del circuito 'circuit' 
        """
        source = "sp" + str(circuit) + "_source"
        sp_attr = "sp" + str(circuit)

        sp_source = getattr(self, source)
        if sp_source is None or circuit not in (1, 2, 3):
            return
        datatype = sp_source[0]
        adr = sp_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}

        current_iv_sp = get_value(value_source=source)  # El SIG610 almacena CONSIGNA en byte bajo y MODO en byte alto
        if not current_iv_sp is None:
            current_iv_sp_value = current_iv_sp[0] * 256 + current_iv_sp[1]
            current_iv, current_sp = current_iv_sp
            print(f"Modo off/frio/calor actual del circuito {circuit} de {self.name}: {current_iv}")
            print(f"Consigna actual del circuito {circuit} de {self.name}: {current_sp}")
        else:
            print(f"No se ha podido leer la consigna del circuito {circuit} de {self.name}")
            return

        sp_to_write = current_sp
        print(f"tempfluidcontroller, \n"
              f"current_iv_sp = {current_iv_sp}, \n"
              f"current_iv = {current_iv}, \n"
              f"current_sp = {current_sp}")
        if not new_sp is None:
            if new_sp > 55 or new_sp < 5:
                print(f"{self.name}: Error escribiendo la consigna {new_sp} para el circuito {circuit}")
                # Se mantiene la consigna actual
            else:
                sp_to_write = new_sp

            if sp_to_write == current_sp:
                return current_sp  # No se ha cambiado la consigna. No hay nada que actualizar.

        # Se propaga la nueva consigna en el byte bajo.
        print(f"\ntempfluidcontroller, \n"
              f"sp_to_write = {sp_to_write}, \n")

        new_val = set_lb(current_iv_sp_value, sp_to_write)
        dbval = save_value(source, new_val)  # Se actualiza la base de datos de lecturas con el nuevo valor
        res = await set_value(source, new_val)  # Escritura Modbus
        setattr(self, sp_attr, sp_to_write)
        setpoint = getattr(self, sp_attr)
        return setpoint

    async def man_sp(self, circuit: int = 1, man_set_sp_mode: [int, None] = None) -> [phi.Tuple[int, int], None]:
        """
        Fija la consigna de impulsión del circuito 'circuit' en lugar de utilizar el valor calculado
        desde el grupo de habitaciones.

        Activa y desactiva el ajuste manual de la consigna y, cuando está activado, propaga la consigna almacenada
        en 'man_sp'
        Param:
            circuit: circuito en el que se va a fijar la consigna de forma manual en lugar de la calculada
            para el grupo de habitaciones
            man_set_sp_mode: estado activado o desactivado del ajuste manual de la consigna
            man_sp: valor manual de consigna a aplicar, leída desde el archivo de intercambio
        Si man_set_sp_mode es None, devuelve el valor de activación del ajuste manual de consigna:
        1:activado / 0:desactivado y el valor de consigna configurada como manual.
        Returns: Tupla con el estado del ajuste manual de la consigna y valor manual configurado
        """
        sp_man_activation_attr = "act_man_sp" + str(circuit)
        man_sp_value = "man_sp" + str(circuit)

        current_man_sp_val = getattr(self, man_sp_value)

        if not man_set_sp_mode is None:
            if man_set_sp_mode in (phi.ON, phi.OFF):
                setattr(self, sp_man_activation_attr, man_set_sp_mode)

            if man_set_sp_mode == phi.ON:
                print(f"Actualizando MANUALMENTE la consigna del circuito {circuit} de {self.name} a "
                      f"{current_man_sp_val}")
                # Consigna manual activada
                await self.sp(circuit, current_man_sp_val)  # La consigna manual se escribe en la base de datos
                # de lecturas y en el atributo de spx

        current_man_sp_activation = getattr(self, sp_man_activation_attr)
        current_man_sp_val = getattr(self, man_sp_value)

        return current_man_sp_activation, current_man_sp_val

    async def ti(self, circuit: int = 1):
        """
        Devuelve el valor de la temperatura de impulsión del circuito 'circuit'
        Param:
            circuit: Circuito cuya temperatura de impulsión se desea leer: 1, 2 ó 3.
        Returns: Temperatura de impulsión del circuito 'circuit'
        """
        ti_source_attr = "ti" + str(circuit) + "_source"
        ti_attr = "ti" + str(circuit)

        ti_source = getattr(self, ti_source_attr)
        if ti_source is None or circuit not in (1, 2, 3):
            return
        datatype = ti_source[0]
        adr = ti_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_ti = get_value(source)
        if current_ti is None or current_ti < 0 or current_ti > 60:
            print(f"{self.name}: Error leyendo la temperatura de impulsión del circuito {circuit}\n"
                  f"Se para la bomba circuladora por seguridad")
            await self.onoff(circuit, phi.OFF)
            return
        else:
            setattr(self, ti_attr, current_ti)
        ti = getattr(self, ti_attr)
        return ti

    async def valv(self, circuit: int = 1):
        """
        Devuelve la posición de la válvula del circuito 'circuit'
        Param:
            circuit: Circuito cuya temperatura de impulsión se desea leer: 1, 2 ó 3.
        Returns: % apertura válvula del circuito 'circuit'
        """
        v_source_attr = "v" + str(circuit) + "_source"
        v_attr = "v" + str(circuit)

        valv_source = getattr(self, v_source_attr)
        if valv_source is None or circuit not in (1, 2, 3):
            return
        datatype = valv_source[0]
        adr = valv_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_pos = get_value(source)
        if current_pos is None:
            print(f"{self.name}: Error leyendo la posición de la válvula del circuito {circuit}")
            return
        else:
            setattr(self, v_attr, current_pos)
        valv_position = getattr(self, v_attr)
        return valv_position

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
        self.st4 = get_value(value_source=source)
        return self.st4

    async def set_st4(self, new_st4_val=1):
        """
        Establece el valor de la salida digital 4 del controlador SIG610
        Returns: Estado de la salida digital 4 del controlador SIG610
        """
        if self.st4_source is None or new_st4_val not in (phi.ON, phi.OFF):
            return
        datatype = self.st4_source[0]
        adr = self.st4_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        await set_value(source, new_st4_val)
        dbval = save_value(source, new_st4_val)
        self.st4 = new_st4_val
        return self.st4

    async def upload(self):
        """
        Escribe en el dispositivo ModBus los valores actuales de sus atributos tipo RW:
        'st4'
        :return:
        """
        circuits = (1, 2, 3)

        for circuit in circuits:
            await self.iv_mode(circuit)
            await self.sp(circuit)
            await self.man_onoff(circuit)  # Recoge el valor del atributo de activación manual de la bomba
            await self.man_sp(circuit)  # Recoge el valor del atributo de activación manual de la consigna
            await self.valv(circuit)

        await self.set_st4(self.st4)

        return 1

    async def update(self):
        """
        Propaga a cada circuito, el modo de funcionamiento, el estado on/off y la consigna de cada uno
        de los grupos de habitaciones. Puede haber hasta 3 grupos de habitaciones.
        El circuito 1 corresponde al primer grupo, el circuito 2 al segundo y así sucesivamente
        Returns: resultado de la escritura modbus de los valores actualizados o los valores manuales.
        """
        await self.upload()  # Compruebo el estado de los modos manuales

        # Se actualizan los valores que son de SÓLO LECTURA, calculados desde los grupos de habitaciones

        with open(phi.ROOMGROUPS_VALUES_FILE, "r") as f:
            roomgroups_values = json.load(f)

        q_grupos = 0
        if self.groups:
            print(f"(tempfluidcontroller update). Se han definido los siguientes grupos en {self.name}: {self.groups}")
            q_grupos = len(self.groups)  # Cantidad de grupos de habitaciones definidos en el controlador
            # El primer grupo se asocia al circuito 1, el segundo, si existe, al 2 y el tercero al circuito 3
        else:
            print(f"(tempfluidcontroller update). No se han definido grupos de habitaciones en {self.name}")
            return

        st4_attr = "st4"  # Atributo asociado a la salida digital 4 del controlador
        # El modo IV se toma del sistema: 1 = refrigeración / 0 = calefacción, pero al circuito hay que propagar
        # un 1 para refrigeración y un 2 para calefacción
        # system_modo_iv = await phi.get_modo_iv()
        tempfluidcontroller_iv = phi.system_iv if phi.system_iv == 1 else 2

        for circ in range(q_grupos):  # circ toma valores desde 0 hasta q_grupos - 1
            circuito = circ + 1
            roomgroup = roomgroups_values.get(self.groups[circ])  # Diccionario con datos del grupo de habitaciones
            # asociado al controlador de temperatura de impulsión
            if roomgroup is None:
                print(f"No se ha encontrado información del grupo de habitaciones {self.groups[circ]}")
                return
            group_sp = int(round(roomgroup.get("water_sp"), 0))  # Se extrae la consigna de agua del grupo
            group_demand = roomgroup.get("demanda")  # Se extrae la demanda del grupo
            group_name = self.groups[circ]
            print(f"(tempfluidcontroller update) Valores del grupo {group_name}\n"
                  f"\tConsigna a escribir en controlador: {group_sp}\n"
                  f"\tDemanda del grupo: {group_demand}")

            # Los valores de lectura y escritura proceden de la web por lo que hay que ver si se han modificado.
            # Sólo se actualiza EL ESTADO DE LAS BOMBAS, LA CONSIGNA MANUAL y LA CONSIGNA REAL
            modo_iv_attr = "iv" + str(circuito)
            pump_man_activation_attr = "act_man_st" + str(circuito)
            pump_man_value_attr = "man_st" + str(circuito)
            sp_man_activation_attr = "act_man_sp" + str(circuito)
            sp_man_value_attr = "man_sp" + str(circuito)
            spx = "sp" + str(circuito)
            vx = "v" + str(circuito)

            iv = await self.iv_mode(circuito)
            if iv != tempfluidcontroller_iv:
                # Se actualiza el modo IV del circuito
                new_iv = await self.iv_mode(circuito, tempfluidcontroller_iv)
                print(f"Se actualiza a {new_iv} el modo IV del circuito {circuito} de {self.name}")

            pump_man_activation, pump_man_value = await self.man_onoff(circuito)
            sp_man_activation, sp_man_value = await self.man_sp(circuito)
            print(f"UPDATE TempFluidController {self.name}, circuito {circuito}: "
                  f"Valores de los atributos ANTES de comprobar actualización desde la web")
            print(f"\tModo IV: {iv}\n"
                  f"\tMando manual bomba habilitado: {pump_man_activation}\n"
                  f"\tValor manual bomba: {pump_man_value}\n"
                  f"\tConsigna manual habilitada: {sp_man_activation}\n"
                  f"\tValor manual consigna: {sp_man_value}\n"
            )

            # Primero se actualizan los atributos con los valores manuales de estado bomba y consigna
            man_values_attrs = (pump_man_value_attr, sp_man_value_attr)
            for attrname in man_values_attrs:
                print(f"{self.name}.{attrname}: {getattr(self, attrname)}")
                changed = await check_changes_from_web(self.bus_id, self, attrname)
                if changed:
                    print(f"{self.name}.{attrname} ha cambiado en la web: {getattr(self, attrname)}")

            # Luego se actualizan los atributos que habilitan los valores manuales y se procesan
            man_values_attrs = (pump_man_activation_attr, sp_man_activation_attr)
            for attrname in man_values_attrs:
                print(f"{self.name}.{attrname}: {getattr(self, attrname)}")
                changed = await check_changes_from_web(self.bus_id, self, attrname)
                if changed:
                    print(f"{self.name}.{attrname} ha cambiado en la web: {getattr(self, attrname)}")
                new_val = getattr(self, attrname)
                if "st" in attrname:  # Ha cambiado la habilitación manual de la bomba
                    if new_val == phi.ON:  # Modo manual activado. Se propaga la acción manual de la bomba
                        await self.man_onoff(circuito, new_val)
                    elif new_val == phi.OFF: # Modo manual desactivado. Se arranca si hay demanda y se para si no
                        if group_demand != 0:  # El grupo tiene demanda
                            algun_actuador_abierto = await get_all_ufhc_actuators_st()
                            if circuito in (1, "1") and algun_actuador_abierto: # El circuito 1 es el de suelo radiante
                            # hay algún actuador abierto
                                print(f"\nEl grupo {group_name} tiene demanda: {group_demand} y "
                                        f"algun_actuador_abierto={algun_actuador_abierto}. Se arranca bomba\n")
                                await self.onoff(circuito, phi.ON)
                            elif circuito in (1, "1"): # Todos los actuadores están cerrados
                                print(f"\nEl grupo {group_name} tiene demanda: {group_demand} y "
                                        f"algun_actuador_abierto={algun_actuador_abierto}. Se para bomba\n")
                                await self.onoff(circuito, phi.OFF)
                            algun_fancoil_activo = await get_all_fancoils_st()
                            if circuito in (2, "2") and algun_fancoil_activo: # El circuito 2 es el de los fancoils
                            # hay algún fancoil en marcha
                                print(f"\nEl grupo {group_name} tiene demanda: {group_demand} y "
                                        f"algun_fancoil_activo={algun_fancoil_activo}. Se arranca bomba\n")
                                await self.onoff(circuito, phi.ON)
                            elif circuito in (2, "2"): # Todos los fancoils están parados
                                print(f"\nEl grupo {group_name} tiene demanda: {group_demand} y "
                                        f"algun_fancoil_activo={algun_fancoil_activo}. Se para bomba\n")
                                await self.onoff(circuito, phi.OFF)
                        else:
                            print(f"\nEl grupo {group_name} no tiene demanda: {group_demand}. Se para la bomba\n")
                            await self.onoff(circuito, phi.OFF)
                    else:
                        print(f"\nUPDATE TempFluidController - Algo ha ido mal procesando la bomba del "
                              f"circuito {circuito}\n")
                elif "sp" in attrname: # Ha cambiado la habilitación manual de la consigna
                    if new_val == phi.ON:  # Consigna manual activada. Se propaga la consigna manual
                        await self.man_sp(circuito, new_val)
                    elif new_val == phi.OFF: # Consigna manual desactivada. Se propaga la consigna de agua del grupo
                        print(f"El grupo {group_name} tiene una consigna calculada de : {group_sp}.")
                        await self.sp(circuito, group_sp)
                    else:
                        print(f"UPDATE TempFluidController - Algo ha ido mal procesando la consigna del "
                              f"circuito {circuito}")
                print(f"{self.name}.{attrname}: {getattr(self, attrname)}")
                changed = await check_changes_from_web(self.bus_id, self, attrname)
                if changed:
                    print(f"{self.name}.{attrname} ha cambiado en la web: {getattr(self, attrname)}")


            # Finalmente se actualiza la consigna real y el estado de la válvula
            print(f"{self.name}.{spx}: {getattr(self, spx)}")
            changed = await check_changes_from_web(self.bus_id, self, spx)
            if changed:
                print(f"{self.name}.{spx} ha cambiado en la web: {getattr(self, spx)}")

            print(f"{self.name}.{vx}: {getattr(self, vx)}")
            changed = await check_changes_from_web(self.bus_id, self, vx)
            if changed:
                print(f"{self.name}.{vx} ha cambiado en la web: {getattr(self, vx)}")

            iv = await self.iv_mode(circuito)
            pump_man_activation, pump_man_value = await self.man_onoff(circuito)
            sp_man_activation, sp_man_value = await self.man_sp(circuito)
            spx = await self.sp(circuito)
            print(f"UPDATE TempFluidController {self.name}, circuito {circuito}: "
                  f"Valores de los atributos DESPUÉS de comprobar actualización desde la web")
            print(f"\tModo IV: {iv}\n"
                  f"\tMando manual bomba habilitado: {pump_man_activation}\n"
                  f"\tValor manual bomba: {pump_man_value}\n"
                  f"\tConsigna manual habilitada: {sp_man_activation}\n"
                  f"\tValor manual consigna: {sp_man_value}\n"
                  f"\tValor aplicado consigna: {spx}\n"
                  )
        return 1

    def __repr__(self):
        """
        Para imprimir los valores de los 3 circuitos de impulsión
        :return:
        """
        onoff_st = ("st1", "st2", "st3")
        iv_modes = ("iv1", "iv2", "iv3")
        setpoints = ("sp1", "sp2", "sp3")
        t_imps = ("ti1", "ti2", "ti3")
        valv_st = ("v1", "v2", "v3")
        onoff_values = {0: "Parada", 1: "En Marcha"}
        active_values = {0: "Desactivada", 1: "Activada"}
        mode_values = {0: "Circuito parado", 1: "Refrigeración", 2: "Calefacción"}
        dev_info = ""

        for idx in range(3):
            circuito = idx + 1
            st = self.__getattribute__(onoff_st[idx])
            iv = self.__getattribute__(iv_modes[idx])
            sp = self.__getattribute__(setpoints[idx])
            ti = self.__getattribute__(t_imps[idx])
            valv = self.__getattribute__(valv_st[idx])
            dev_info += f"\nCIRCUITO {circuito}"
            dev_info += f"\n=========="
            dev_info += f"\n\tEstado bomba: {onoff_values.get(st)}"
            dev_info += f"\n\tEstado modo de funcionamiento: {mode_values.get(iv)}"
            dev_info += f"\n\tConsigna de impulsión: {sp} ºC"
            dev_info += f"\n\tTemperatura de impulsión: {ti} ºC"
            dev_info += f"\n\tApertura válvula: {valv}%"

        dev_info += f"\n\nEstado salida digital 4 {active_values.get(self.get_st4())}"
        return dev_info


class Fancoil(phi.MBDevice):
    """
    Controlador de fancoils sistema Phoenix.
    Dispositivo especial SIG311
    NOTA: LOS ATRIBUTOS DE ESTA CLASE DEBEN COINCIDIR CON LAS CLAVES DEL JSON FANCOILS.JSON EN LA
    CARPETA DE PROJECT_ELEMENTS.
    Puede controlar fancoils a 2 tubos con ventilador de 3 velocidades o electrónico.
    El fancoil estará asociado a un grupo de habitaciones.
    Al actualizar el controlador se recoge la consigna y la temperatura calculadas para el grupo de
    habitaciones asociado y se propaga al fancoil correspondiente, así como su modo de funcionamiento
    calefacción/refrigeración.
    Param: device: dispositivo ModBus con el mapa de registros a mapear para las operaciones con el controlador SIG311.
    Param: groups: grupos de habitaciones vinculados al dispositivo. Cada fancoil sólo puede estar asociado a un grupo
    de habitaciones. Si se introduce más de 1, sólo se utiliza el primero de ellos.
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
        self.onoff_target = None  # Orden Marcha/Paro fancoil
        self.st_modo_demanda_source = None  # Tipo registro y dirección modbus para estado, modo y demanda
        self.onoff_st = None
        self.demand = None
        self.iv_source = None  # Tipo registro y dirección modbus Modo de funcionamiento calefacción/refrigeración
        self.iv = None  # Modo de funcionamiento calefacción/refrigeración
        self.sp_source = None  # Tipo registro y dirección modbus Consigna fancoil
        self.sp = None  # Consigna de funcionamiento fancoil
        self.rt_source = None  # Tipo registro y direccion modbus Temperatura ambiente fancoil
        self.rt = None  # Temperatura de funcionamiento del fancoil
        self.fan_type_source = None  # Tipo registro y direccion modbus Tipo de ventilador
        self.fan_type = None  # Tipo de ventilador 0:AC / 1:EC
        self.fan_auto_cont_source = None  # Tipo registro y direccion modbus funcionamiento auto-continuo del ventilador
        self.fan_auto_cont = None  # Tipo registro y direccion modbus funcionamiento auto-continuo del ventilador
        self.fan_st_source = None  # Tipo registro y direccion modbus estado del ventilador
        self.fan_speed = None  # Velocidad actual del fancoil
        self.manual_fan_target = None  # Tipo registro y direccion modbus Modo manual del ventilador
        self.manual_fan = None  # Tupla con el estado de activación manual del ventilador y la velocidad manual
        self.actmanual_fan = None  # Estado de activación manual del ventilador
        self.manual_speed = None  # Velocidad manual del ventilador
        self.manual_speed_target = None  # Tipo registro y direccion modbus velocidad manual del ventilador
        self.ac_speed_limit_source = None  # Tipo registro y direccion modbus velocidades máxima y mínima del
        # ventilador tipo AC
        self.ec_speed_limit_source = None  # Tipo registro y direccion modbus velocidades máxima y mínima del
        # ventilador tipo EC
        self.speed_limit = None  # Velocidades máxima y mínima del ventilador
        self.manual_valv_source = None  # Tipo registro y direccion modbus activación modo manual de la válvula
        # del fancoil
        self.manual_valv_position_source = None  # Tipo registro y direccion modbus apertura/cierre manual de la
        # válvula del fancoil
        self.manual_valv_st = None  # Estado de operación manual de la válvula
        self.manual_valv_pos = phi.OPEN  # Posición de la válvula en modo manual
        self.valv_st_source = None  # Tupla con el estado de la válvula
        self.valv_st = None  # Estado actual de la válvula
        self.remote_onoff_source = None  # Tipo registro y direccion modbus para on/off remoto del fancoil
        self.remote_onoff = None  # Valor del registro 18: on/off remoto del fancoil. 0:por modbus / 1:por ED
        self.sd_aux_source = None  # Tipo registro y direccion modbus para la salida digital auxiliar
        self.sd_aux = None  # Operación con la salida digital auxiliar
        self.floor_temp_source = None  # Tipo registro y direccion modbus para leer la temperatura del pavimento
        self.floor_temp = None  #

    async def onoff(self, new_status: [int, None] = None):
        """
        Arranca o para el fancoil según el valor 1 (arrancar) o 0 (parar) del parámetro new_status
        Si new_status es None, devuelve el estado actual, leído en el byte alto del registro 21
        Returns: Estado onoff del fancoil o None si falta algún dato
        """
        if self.onoff_target is None:
            return
        st_datatype = self.st_modo_demanda_source[0]
        st_adr = self.st_modo_demanda_source[1]
        datatype = self.onoff_target[0]
        adr = self.onoff_target[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": st_datatype,
                  "adr": st_adr}

        # Recojo el estado actual del fancoil
        current_st_mode, current_demand = get_value(source)  # El registro 21 del SIG311 devuelve en el byte alto el
        # estado 0: off, el modo 1: on en calefacción o el modo 2: on en refrigeración. En el byte bajo devuelve
        # 0: si no hay demanda, 1: demanda de calor, 2: demanda de frío
        if new_status is None:
            self.onoff_st = 0 if current_st_mode == 0 else 1  # Se devuelve 1 tanto en modo calefacción
            # como refrigeración
        elif new_status not in [0, 1]:
            print(f"ERROR - El valor {new_status} no es válido para arrancar o parar el fancoil {self.name}.\n"
                  f"Valores válidos son 1 para arrancar ó 0 para parar")
            self.onoff_st = 0 if current_st_mode == 0 else 1
        else:
            res = await set_value(target, new_status)
            dbval = save_value(target, new_status)
            self.onoff_st = new_status
        return self.onoff_st

    async def demanda_st(self):
        """
        Devuelve el valor de la demanda del fancoil
        Returns:
            0: No hay demanda o el fancoil está en manual-off
            1: Demanda de calor
            2: Demanda de frío
        """
        if self.st_modo_demanda_source is None:
            return
        datatype = self.st_modo_demanda_source[0]
        adr = self.st_modo_demanda_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}

        # Recojo el estado actual del fancoil
        current_st_mode, current_demand = get_value(source)
        # El registro 21 del SIG311 devuelve en el byte alto el
        # estado 0: off, el modo 1: on en calefacción o el modo 2: on en refrigeración. En el byte bajo devuelve
        # 0: si no hay demanda, 1: demanda de calor, 2: demanda de frío
        # Si el fancoil está en modo manual - off, la demanda de pone a 0 para que no se active la bomba circuladora
        if self.manual_fan and self.manual_speed == 0:
            self.demand = 0
            print(f"Fancoil {self.name} PARADO en modo MANUAL. Se considera que no hay demanda.\n"
                  f"Demanda fancoil {self.name} = {self.demand}, "
                  f"aunque la demanda en el controlador es {current_demand}")
        else:
            self.demand = current_demand
        return self.demand

    async def iv_mode(self, new_iv_mode: [int, None] = None):
        """
        Procesa el modo de funcionamiento Calefacción (new_iv_mode = 0) / Refrigeración (iv_mode = 1) del
        fancoil.
        Param:
            new_iv_mode:
                Si None, se devuelve el modo actual
                Si 1, se activa el modo refrigeración en el fancoil
                Si 0, se activa el modo calefacción en el fancoil
        Returns:
            Modo iv o None si falta algún dato
        """
        if self.iv_source is None:
            return
        datatype = self.iv_source[0]
        adr = self.iv_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        mode_datatype = self.st_modo_demanda_source[0]
        mode_adr = self.st_modo_demanda_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": mode_datatype,
                  "adr": mode_adr}
        # Recojo el modo actual de funcionamiento del fancoil
        current_iv_value = get_value(target)
        # print(f"DEBUGGING {__file__}: Valor iv fancoil: {current_iv_value}")
        if current_iv_value is None:
            return
        current_st_mode, current_demand = get_value(source)  # El registro 21 del SIG311 devuelve en el byte alto el
        # estado 0: off, el modo 1: on en calefacción o el modo 2: on en refrigeración. En el byte bajo devuelve
        # 0: si no hay demanda, 1: demanda de calor, 2: demanda de frío
        if new_iv_mode is None or new_iv_mode not in [phi.HEATING, phi.COOLING]:
            if current_st_mode in [1, 2]:
                self.iv = phi.HEATING if current_st_mode == 1 else phi.COOLING
            else:
                self.iv = current_iv_value
        # Se activa el modo indicado en iv_mode
        elif new_iv_mode in [phi.HEATING, phi.COOLING]:
            res = await set_value(target, new_iv_mode)
            dbval = save_value(target, new_iv_mode)
            self.iv = new_iv_mode
        else:
            print(f"ERROR - Modo calefacción/refrigeración {new_iv_mode} no válido para el fancoil {self.name}")
            return
        return self.iv

    async def set_sp(self, new_sp_value: [int, float, None] = None):
        """
        Procesa la consigna de funcionamiento del fancoil.
        Si new_sp_value es None, devuelve la consigna de funcionamiento del fancoil leída del diccionario que almacena
        las lecturas modbus.
        Si no, fija la consigna de funcionamiento del fancoil
        Param:
            new_sp_value: Consigna a pasar al fancoil. Se introduce el valor deseado. Se le aplica la función de
            conversión necesaria en el momento de escribir. Es decir se escribe el valor real, o sea, 20 °C, no 200
        Returns:
            Consigna activa en el fancoil o None si falta algún dato
        """
        if self.sp_source is None:
            return
        datatype = self.sp_source[0]
        adr = self.sp_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_sp = get_value(value_source=source)
        if new_sp_value is None:
            self.sp = current_sp
        elif new_sp_value > 40 or new_sp_value < 10:
            print(f"{self.name}: ERROR estableciendo una consigna de {new_sp_value} en el fancoil {self.name} "
                  f"(rango 10-40)")
            self.sp = current_sp
        else:
            print(f"fancoil.set_sp: Actualizando consigna con valor {new_sp_value} en fancoil {self.name}")
            res = await set_value(source, new_sp_value)
            dbval = save_value(source, new_sp_value)
            self.sp = new_sp_value
        return self.sp

    async def set_rt(self, new_rt_value: [int, float, None] = None):
        """
        Procesa la temperatura ambiente de funcionamiento del fancoil.
        Si new_rt_value es None, devuelve la temperatura ambiente de funcionamiento del fancoil leída del
        diccionario que almacena las lecturas modbus.
        Si no, fija la consigna de funcionamiento del fancoil
        Param:
            new_rt_value: temperatura ambiente a pasar al fancoil. Se introduce el valor deseado.
            Se le aplica la función de conversión necesaria en el momento de escribir.
            Es decir se escribe el valor real, o sea, 20 °C, no 200
        Returns:
            Temperatura ambiente activa en el fancoil o None si falta algún dato
        """
        if self.rt_source is None:
            return
        datatype = self.rt_source[0]
        adr = self.rt_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_rt = get_value(value_source=source)
        # if new_rt_value is None or current_rt > 50 or current_rt < 0:
        if new_rt_value is None:
            # print(f"ERROR {self.name} - No se puede leer la temperatura ambiente.\nSe para el fancoil por seguridad")
            # await self.manual_fan_speed(manual_mode=phi.ON, man_speed=phi.OFF)  # Parada manual
            self.rt = current_rt
        elif new_rt_value > 50 or new_rt_value < 0:
            await self.manual_fan_speed(manual_mode=phi.OFF)  # Se activa la selección automática de velocidad
            print(f"{self.name}: ERROR estableciendo una temperatura ambiente de {new_rt_value} en el "
                  f"fancoil {self.name} (rango 0-50)")
            self.rt = current_rt
        else:
            # await self.manual_fan_speed(manual_mode=phi.OFF)  # Se activa la selección automática de velocidad
            print(f"fancoil.set_sp: Actualizando temperatura ambiente con valor {new_rt_value} en fancoil {self.name}")
            res = await set_value(source, new_rt_value)
            dbval = save_value(source, new_rt_value)
            self.rt = new_rt_value
        return self.rt

    def _get_fan_type(self):
        """
        Devuelve el tipo de ventilador "AC", 3 velocidades, o "EC" electrónico
        Returns: 'AC' si el registro 6 vale 0, 'EC' si vale 1
        """
        datatype = self.fan_type_source[0]
        adr = self.fan_type_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        fan_type = get_value(value_source=source)
        fan_type_name = {0: "AC", 1: "EC"}
        self.fan_type = fan_type_name[fan_type]
        return self.fan_type

    async def fan_auto_cont_mode(self, fan_mode_cooling: [int, None] = None, fan_mode_heating: [int, None] = None):
        """
        Si el parámetro fan_mode es None, devuvelve la configuración del ventilador del fancoil.
        Byte alto para funcionamiento en modo refrigeración
        Byte bajo para funcionamiento en modo calefacción
        Si Auto, vale 0 el byte correspondiente.
        En modo Continuo vale 1
        Si el parámetro fan_mode es 1, se activa el modo de funcionamiento continuo del ventilador
        Si fan_mode es 0, se activa el modo de funcionamiento automático del ventilador
        Returns:
            0 para ventilador auto (según sea el modo calefacción o refrigeración, byte bajo o byte alto)
            1 para ventilador continuo (según sea el modo calefacción o refrigeración, byte bajo o byte alto)
            None si falta algún dato

        """
        AUTO = 0
        CONTINUO = 1
        cooling = True if self.iv else False  # 1-refrigeración / 0-calefacción
        if self.fan_auto_cont_source is None:
            return
        datatype = self.fan_auto_cont_source[0]
        adr = self.fan_auto_cont_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        # Recojo el valor actual del registro a actualizar
        cont_cooling, cont_heating = get_value(value_source=source)  # con el SIG311, get_value devuelve una tupla
        # con el modo del ventilador en el byte alto para refrigeración y en el bajo para calefacción
        current_value = cont_cooling * 256 + cont_heating
        if fan_mode_cooling is not None:
            # Actualizo el modo del ventilador para refrigeración (byte alto)
            new_val_cooling = set_hb(current_value, int(fan_mode_cooling))
            res = await set_value(source, new_val_cooling)  # Escritura en el dispositivo ModBus
            dbval = save_value(source, new_val_cooling)
            cont_cooling = new_val_cooling
        if fan_mode_heating is not None:
            # Actualizo el modo del ventilador para refrigeración (byte alto)
            new_val_heating = set_lb(current_value, int(fan_mode_heating))
            res = await set_value(source, new_val_heating)  # Escritura en el dispositivo ModBus
            dbval = save_value(source, new_val_heating)
            cont_heating = new_val_heating
        if cooling:
            self.fan_auto_cont = CONTINUO if cont_cooling == CONTINUO else AUTO
        else:
            self.fan_auto_cont = CONTINUO if cont_heating == CONTINUO else AUTO
        return self.fan_auto_cont

    async def manual_fan_speed(self, manual_mode: int = None, man_speed: [int, None] = None) -> \
            [phi.Tuple[int, int], None]:
        """
        Permite activar el modo manual de selección de velocidad del fancoil y seleccionar la velocidad.
        1 = Manual, valor del registro 8 = 1
        0 = Auto, valor del registro 8 = 0
        Param:
            manual_mode
                Si manual_mode es None, devuelve el modo de selección de la velocidad del fancoil, autamática ó manual,
                y la velocidad manual configurada actualmente según el tipo de motor del ventilador: AC o EC
                Si manual_mode es True, pone el ventilador en modo manual (valor 1) y con la velocidad 'speed'
                (registro 9)
                Si manual_mode es False, pone el ventilador en modo auto (valor 0)
            speed
                velocidad manual para el fancoil. de 0 a 3 en ventiladores AC y de 0 a 100 en ventiladores EC.
                El tipo de ventilador se lee con el método _get_fan_type

        Returns: Tupla con el estado de activación del modo manual del fancoil y su velocidad manual configurada

        NOTA 19/06/2024
        Anteriormente se tomaba el valor de los atributos directamente de los valores leídos y almacenados en datadb.
        Como esos valores leídos han servido para actualizar los atributos de cada objeto fancoil, ahora, en lugar
        de coger los valores de datadb mediante get_value, leemos directamente los atributos correspondientes del
        objeto fancoil.
        """
        AC_FAN_SPEED = (0, 1, 2, 3)
        EC_FAN_SPEED = tuple([x for x in range(101)])
        if self.manual_fan_target is None or self.manual_speed_target is None:
            return
        fan_type = self._get_fan_type()  # Puede ser 'AC' o 'EC'
        manual_datatype = self.manual_fan_target[0]
        manual_adr = self.manual_fan_target[1]
        manual_speed_datatype = self.manual_speed_target[0]
        manual_speed_adr = self.manual_speed_target[1]
        manual_mode_target = {"bus": int(self.bus_id),
                              "device": int(self.device_id),
                              "datatype": manual_datatype,
                              "adr": manual_adr}
        manual_speed_target = {"bus": int(self.bus_id),
                               "device": int(self.device_id),
                               "datatype": manual_speed_datatype,
                               "adr": manual_speed_adr}
        # Recojo el modo actual de selección de velocidad del fancoil
        current_manual_operation = get_value(value_source=manual_mode_target)
        # Recojo el valor actual de la velocidad manual
        man_speed_ac, man_speed_ec = get_value(value_source=manual_speed_target)  # con el SIG311, get_value devuelve
        # una tupla con la velocidad manual para ventiladores AC en el byte alto y para ventiladores EC en el byte bajo
        current_man_speed = man_speed_ac if fan_type == "AC" else man_speed_ec
        current_manual_speed_value = man_speed_ac * 256 + man_speed_ec
        current_speed = await self.get_fan_speed()
        if man_speed is not None:
            if (fan_type == "AC" and man_speed not in AC_FAN_SPEED) or \
                    (fan_type == "EC" and man_speed not in EC_FAN_SPEED):
                print(f"La velocidad seleccionada, {man_speed}, para el fancoil {self.name} de tipo {fan_type} "
                      f"no es válida. Se mantiene la configuración de velocidad manual actual.")
                man_speed = current_man_speed
            else:
                # Se actualiza el valor de velocidad manual
                # print(f"{self.name} - Valores actuales velocidad manual: \n\tbyte alto:\t{man_speed_ac}"
                #       f"\n\tbyte bajo: {man_speed_ec}")
                new_man_speed = set_hb(current_manual_speed_value, man_speed) if fan_type == "AC" \
                    else set_lb(current_manual_speed_value, man_speed)
                print(f"{self.name} - Actualizando valor velocidad manual al valor {new_man_speed} en el esclavo "
                      f"{self.slave}, dirección  {manual_speed_target}")
                res = await set_value(manual_speed_target, new_man_speed)  # Escritura en el dispositivo ModBus
                dbval = save_value(manual_speed_target, new_man_speed)
        else:
            man_speed = current_man_speed

        if manual_mode is not None:
            print(f"{self.name} - Estableciendo al valor {manual_mode} para el Ajuste Manual de Velocidad "
                  f"en el esclavo {self.slave}, dirección  {manual_mode_target}")
            res = await set_value(manual_mode_target, manual_mode)  # Se activa o desactiva el modo manual indicado
            dbval = save_value(manual_mode_target, manual_mode)
            self.manual_fan = (manual_mode, man_speed)
            if manual_mode:
                self.fan_speed = self.manual_fan[1]
        else:
            self.manual_fan = (current_manual_operation, man_speed)  # Aunque no se active el modo manual, se puede
            # cambiar la velocidad manual configurada
        self.actmanual_fan, self.manual_speed = self.manual_fan
        return self.manual_fan

    async def get_fan_speed(self) -> [int, None]:
        """
        Devuelve la velocidad actual del fancoil, dependiendo de si éste es del tipo AC o EC
        Returns:
            0-3 para ventilador AC
            0-100 para ventilador EC
        """
        if self.fan_st_source is None:
            return
        fan_type = self._get_fan_type()  # Puede ser 'AC' o 'EC'
        datatype = self.fan_st_source[0]
        adr = self.fan_st_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        ac_speed, ec_speed = get_value(source)
        self.fan_speed = ac_speed if fan_type == "AC" else ec_speed

        return self.fan_speed

    async def get_valv_st(self) -> [int, None]:
        """
        Devuelve el estado actual de la válvula
        Returns:
            0: válvula cerrada
            1: válvula abierta
        """
        datatype = self.valv_st_source[0]
        adr = self.valv_st_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        valv_st = get_value(source)
        self.valv_st = valv_st

        return self.valv_st

    async def set_speed_limit(self, max_speed: [int, None] = None, min_speed: [int, None] = None) \
            -> [phi.Tuple[int, int], None]:
        """
        Procesa las velocidades máxima y mínima de funcionamiento del fancoil en función del tipo de fancoil.
        Si max_speed y min_speed son None, devuelve las velocidades máxima y mínima de funcionamiento del fancoil
        leídas del diccionario que almacena las lecturas modbus.
        Si máx_speed o min_speed son 0, no se modifica su valor
        Si no, fija la velocidad máxima y/o mínima que se indiquen
        Param:
            max_speed: velocidad máxima del fancoil. 1, 2 ó 3 para ventilador AC ó valores de 1 a 100 para EC
            min_speed: velocidad mínima del fancoil. 1, 2 ó 3 para ventilador AC ó valores de 1 a 100 para EC
            min_speed <= max_speed
        Returns: Tupla con las velocidades máxima y mínima del fancoil
        """
        fan_type = self._get_fan_type()
        SPEED_VALUES = {"AC": (1, 2, 3), "EC": tuple([x + 1 for x in range(100)])}

        if fan_type == "AC" and self.ac_speed_limit_source is None or \
                fan_type == "EC" and self.ec_speed_limit_source is None:
            return
        datatype = self.ac_speed_limit_source[0] if fan_type == "AC" else self.ec_speed_limit_source[0]
        adr = self.ac_speed_limit_source[1] if fan_type == "AC" else self.ec_speed_limit_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_max, current_min = get_value(value_source=source)
        current_limits = current_max * 256 + current_min

        if (max_speed is not None and max_speed not in SPEED_VALUES.get(fan_type)) or \
                (min_speed is not None and min_speed not in SPEED_VALUES.get(fan_type)):
            print(f"ERROR - Algún valor límite introducido no es válido para el fancoil {self.name}\n\t"
                  f"Rango válido: {SPEED_VALUES.get(fan_type)[0]}-{SPEED_VALUES.get(fan_type)[-1]}")
            print("\tSe mantienen los valores actuales")
            self.speed_limit = (current_max, current_min)

        if max_speed in [None, 0] and min_speed in [None, 0]:  # No se cambian los valores
            self.speed_limit = (current_max, current_min)
        elif max_speed in [None, 0]:
            # Sólo se modifica la velocidad mínima
            if min_speed > current_max:
                print(f"ERROR - No se puede fijar una velocidad mínima, {min_speed}, mayor que la velocidad máxima "
                      f"{current_max} actual en el fancoil {self.name}")
                self.speed_limit = (current_max, current_min)
            else:  # Se modifica la velocidad mínima
                new_limits = set_lb(current_limits, min_speed)
                res = await set_value(source, new_limits)
                dbval = save_value(source, new_limits)
                self.speed_limit = (current_max, min_speed)
        elif min_speed in [None, 0]:
            # Sólo se modifica la velocidad máxima
            if max_speed < current_min:
                print(f"ERROR - No se puede fijar una velocidad máxima, {max_speed}, menor que la velocidad mínima "
                      f"{current_min} actual en el fancoil {self.name}")
                self.speed_limit = (current_max, current_min)
            else:  # Se modifica la velocidad máxima
                new_limits = set_hb(current_limits, max_speed)
                res = await set_value(source, new_limits)
                dbval = save_value(source, new_limits)
                self.speed_limit = (max_speed, current_min)
        else:  # Se modifican las velocidades máxima y mínima de funcionamiento del fancoil.
            new_limits = max_speed * 256 + min_speed
            res = await set_value(source, new_limits)
            dbval = save_value(source, new_limits)
            self.speed_limit = (max_speed, min_speed)
        return self.speed_limit

    async def valv_manual_open(self, manual_mode: [int, None] = None, new_position: [int, None] = None) \
            -> [phi.Tuple[int, int], None]:
        """
        Permite activar el modo manual de apertura/cierre de la válvula del fancoil y seleccionar su posición.
        1 = Manual, valor del registro 15 = 1
        0 = Auto, valor del registro 15 = 0
        Param:
            manual_mode
                Si manual_mode es None, devuelve el modo de selección de operación de la válvula, automática ó manual,
                y la posición manual de la válvula, abierta o cerrada
                Si manual_mode es 1, pone la válvula en modo manual (valor 1) y en la posición definida en el
                registro 16
                Si manual_mode es 0, pone la válvula en modo auto (valor 0)
            new_position
                posición manual de la válvula. 0:cerrada / 1:abierta


        Returns: Tupla con el estado de activación de operación manual de válvula y su posición manual configurada
        """
        if self.manual_valv_source is None or self.manual_valv_position_source is None:
            return
        manual_datatype = self.manual_valv_source[0]
        manual_adr = self.manual_valv_source[1]
        manual_valv_position_datatype = self.manual_valv_position_source[0]
        manual_valv_position_adr = self.manual_valv_position_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": manual_datatype,
                  "adr": manual_adr}
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": manual_valv_position_datatype,
                  "adr": manual_valv_position_adr}
        # Recojo el modo actual de operación de la válvula
        current_manual_operation = get_value(value_source=source)
        # Recojo el valor actual de la posición manual
        current_manual_position = get_value(value_source=target)
        if new_position is not None:
            if new_position not in [phi.CLOSED, phi.OPEN]:
                print(f"La posición seleccionada, {new_position}, para la válvula del fancoil {self.name} "
                      f"no es válida. Debe ser 1 (abierta) o 0 (cerrada). \n"
                      f"Se mantiene la configuración de manual actual.")
                new_position = current_manual_position
            else:
                # Se actualiza el valor de posición manual de la válvula
                res = await set_value(target, new_position)  # Escritura en el dispositivo ModBus
                dbval = save_value(target, new_position)

        if not manual_mode is None:
            res = await set_value(source, manual_mode)  # Se activa o desactiva el modo manual indicado
            dbval = save_value(source, manual_mode)
            self.manual_valv_st = manual_mode
            self.manual_valv_pos = new_position
        else:
            self.manual_valv_st = current_manual_operation
        return self.manual_valv_st

    async def remote_onoff_mode(self, onoff_mode: [int, None] = None):
        """
        Configura el on/off remoto del fancoil.
        Param:
            onoff_mode:
                Si onoff_mode vale 0, el marcha/paro del fancoil se hace por ModBus.
                Si vale 1, se hace en función de la entrada digital (registro 25)
                    Arranca o para el fancoil según el valor 1 (arrancar) o 0 (parar) del registro 25
                Si onoff_mode es None, devuelve la configuración actual del remote_onoff
        Returns:
            Configuración del onoff remoto del fancoil o None si falta algún dato

        """
        if self.remote_onoff_source is None:
            return
        datatype = self.remote_onoff_source[0]
        adr = self.remote_onoff_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        # Recojo el estado actual del fancoil
        current_status = get_value(source)
        if onoff_mode is None:
            self.remote_onoff = current_status
        else:
            res = await set_value(source, onoff_mode)
            dbval = save_value(source, onoff_mode)
            self.remote_onoff = onoff_mode
        return self.remote_onoff

    async def sd_aux_st(self, onoff_mode: [int, None] = None):
        """
        Controla la salida digital auxiliar del controlador SIG311.
        Param:
            onoff_mode:
                Si onoff_mode vale 0, salida digital auxiliar desactivada.
                Si vale 1, salida digital auxliar activada
                Si onoff_mode es None, devuelve el estado actual de la salida auxiliar
        Returns:
            Configuración del onoff remoto del fancoil o None si falta algún dato

        """
        if self.sd_aux_source is None:
            return
        datatype = self.sd_aux_source[0]
        adr = self.sd_aux_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        # Recojo el estado actual del fancoil
        current_status = get_value(source)
        if onoff_mode is None:
            self.sd_aux = current_status
        else:
            res = await set_value(source, onoff_mode)
            dbval = save_value(source, onoff_mode)
            self.sd_aux = onoff_mode
        return self.sd_aux

    async def get_floor_temp(self):
        """
        Devuelve la temperatura leída en el registro 24
        Param:
        Returns:
            Temperatura del pavimento (registro 24)

        """
        if self.floor_temp_source is None:
            return
        datatype = self.floor_temp_source[0]
        adr = self.floor_temp_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        # Recojo el estado actual del fancoil
        self.floor_temp = get_value(source)
        return self.floor_temp

    async def update(self):
        """
        Propaga al fancoil el modo de funcionamiento, el estado on/off, la consigna y la temperatura del grupo
        de habitaciones asociado
        Returns: resultado de la escritura modbus de los valores actualizados
        """
        await self.upload()  # Se actualizan los atributos con los últimos valores leídos en el fancoil

        # Se actualizan los valores que son de SÓLO LECTURA, calculados desde los grupos de habitaciones

        with open(phi.ROOMGROUPS_VALUES_FILE, "r") as f:
            roomgroups_values = json.load(f)

        roomgroup = roomgroups_values.get(self.groups[0])  # Datos del grupo de habitaciones asociado al fancoil
        if roomgroup is None:
            print(f"No se ha encontrado información del grupo de habitaciones {self.groups[0]}")
            return

        self.iv = await self.iv_mode(roomgroup.get("iv"))  # 0:Calefaccion / 1:Refrigeracion
        if None in [self.iv, roomgroup.get("air_sp"), roomgroup.get("air_rt")]:
            print(f"DEBUGGING método update {__file__}  iv, sp o rt del fancoil {self.name} es None")
            return
        self.demand = await self.demanda_st()
        fancoil_sp = roomgroup.get("air_sp")  # Al calcular el setpoint del grupo ya se tiene en cuenta el offset
        # fancoil_sp = roomgroup.get("air_sp") + phi.OFFSET_COOLING if self.iv \
        #     else roomgroup.get("air_sp") + phi.OFFSET_HEATING  # Offset heating tiene un valor negativo
        self.sp = await self.set_sp(new_sp_value=fancoil_sp)
        fancoil_rt = roomgroup.get("air_rt")
        self.rt = await self.set_rt(new_rt_value=fancoil_rt)
        # self.iv = await self.iv_mode()
        self.fan_type = self._get_fan_type()
        self.fan_auto_cont = await self.fan_auto_cont_mode()
        self.fan_speed = await self.get_fan_speed()
        self.speed_limit = await self.set_speed_limit()
        self.valv_st = await self.get_valv_st()
        self.remote_onoff = await self.remote_onoff_mode()
        self.sd_aux = await self.sd_aux_st()
        self.floor_temp = await self.get_floor_temp()
        # await update_xch_files_from_devices(self)  # Guarda los valores del dispositivo en el archivo de intercambio
        # correspondiente

        self.onoff_st = await self.onoff()
        self.manual_fan = await self.manual_fan_speed()
        await self.valv_manual_open()

        print(f"UPDATE fancoil {self.name}: Valores de los atributos ANTES de comprobar actualización desde la web")

        list_of_modified_rw_attr = []
        for attrname in phi.EXCHANGE_R_FILES.get(self.__class__.__name__):
            print(f"{self.name}.{attrname}: {getattr(self, attrname)}")
            changed = await check_changes_from_web(self.bus_id, self, attrname)
            if changed:
                list_of_modified_rw_attr.append(attrname)
                print(f"{self.name}.{attrname} ha cambiado en la web: {getattr(self, attrname)}")
        if "actmanual_fan" in list_of_modified_rw_attr or "manual_speed" in list_of_modified_rw_attr:
            print(f"Se ha modificado el modo manual del fancoil {self.name} a {self.actmanual_fan}. "
                  f"Velocidad manual {self.manual_speed}")
            await self.manual_fan_speed(self.actmanual_fan, self.manual_speed)
        if "manual_valv_st" in list_of_modified_rw_attr or "manual_valv_pos" in list_of_modified_rw_attr:
            print(f"Se ha modificado el modo manual de la válvula de {self.name} a {self.manual_valv_st}. "
                  f"Posición manual {self.manual_valv_pos}")
            await self.valv_manual_open(self.manual_valv_st, self.manual_valv_pos)

        print(f"UPDATE fancoil {self.name}: Valores de los atributos DESPUÉS de comprobar actualización desde la web")

        for attrname in phi.EXCHANGE_R_FILES.get(self.__class__.__name__):
            print(f"{self.name}.{attrname}: {getattr(self, attrname)}")

    async def upload(self):
        """
        Escribe en el dispositivo ModBus los valores actuales de sus atributos tipo RW:
        Consignas y modo IV
        :return:
        """
        await self.onoff()
        await self.demanda_st()
        await self.iv_mode()
        await self.set_sp()
        await self.set_rt()
        await self.fan_auto_cont_mode()
        await self.manual_fan_speed()
        await self.get_fan_speed()
        await self.get_valv_st()
        await self.set_speed_limit()
        await self.valv_manual_open()
        await self.remote_onoff_mode()
        await self.sd_aux_st()
        await self.get_floor_temp()

        return 1

    def __repr__(self):
        """
        Para imprimir la información actual del fancoil
        :return:
        """
        onoff = {0: "Parado", 1: "En Marcha"}
        modo = {0: "Calefacción", 1: "Refrigeración"}
        demanda = {0: "No hay demanda", 1: "Demanda de calor", 2: "Demanda de frío"}
        manual = {0: "Automático", 1: "Manual"}
        if None in [self.manual_fan, ]:
            msg = f"DEBUGGING {__file__} __repr__: Error leyendo fancoil {self.name}"
            return msg
        estado_manual_ventilador = self.manual_fan[0]
        dev_info = f"\nFancoil {self.name}\n"
        dev_info += f"\tEstado: {onoff.get(self.onoff_st)}\n"
        dev_info += f"\tModo de funcionamiento: {modo.get(self.iv)}\n"
        dev_info += f"\tConsigna: {self.sp}\n"
        dev_info += f"\tTemperatura ambiente: {self.rt}\n"
        dev_info += f"\tDemanda: {demanda.get(self.demand)}\n"
        dev_info += f"\tVelocidad: {self.fan_speed}\n"
        dev_info += f"\tModo ventilador: {manual.get(estado_manual_ventilador)}\n"
        dev_info += f"\tEstado válvula: {self.valv_st}\n"
        return dev_info


class DataSource(phi.MBDevice):
    """
    Dispositivo ModBus de sólo lectura.
    Se utiliza para integrar dispositivos de los que sólo se necesita leer algún registro
    NOTA: LOS ATRIBUTOS DE ESTA CLASE DEBEN COINCIDIR CON LAS CLAVES DEL JSON DATASOURCE.JSON EN LA
    CARPETA DE PROJECT_ELEMENTS.
    Param: device: dispositivo ModBus con el mapa de registros a mapear
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
        self.attrs = []  # Lista donde se almacenan los nombres de los atributos del DataSource
        self.attr_sources = []  # Lista donde se almacenan los orígenes de los atributos del DataSource
        if self.brand and self.model:  # Creo los atributos sólo si se ha definido marca y modelo
            self._create_attrs()

    def _create_attrs(self):
        """
        Crea los atributos del dispositivo en función de su marca y modelo, extrayéndolos de
        PROJECT_ELEMENTS_FOLDER
        Returns: 1 si se han creado bien los atributos
        """
        datasources_file = f"{phi.PROJECT_ELEMENTS_FOLDER}datasources.json"
        ds_file_exists = phi.os.path.isfile(datasources_file)
        if not ds_file_exists:
            print(f"(devices.py - DataSources) - No se encuentra el archivo {datasources_file}")
            return 0

        print(f"Creando atributos de {self.__dict__}")
        ds_type = f"{self.brand}_{self.model}"
        with open(datasources_file, "r") as dsf:
            dss = json.load(dsf)
        print(f"DataSources: {dss}")
        ds_dict = dss.get("datasources")
        if not ds_dict:
            print(f"(devices.py - DataSources) - Falta la clave 'datasources' en {datasources_file}")
            return 0

        datasource = None if not ds_dict else ds_dict.get(ds_type)
        if not datasource:
            print(f"(devices.py - DataSources) - No se ha definido el DataSource {ds_type} en {datasources_file}")
            return 0

        for k, v in datasource.items():
            if "_source" in k:
                attr = k.split("_")[0]
                setattr(self, attr, None)  # Inicializo a None el valor leído
                setattr(self, k, v)  # Cargo el tipo de dato y el registro en el que se lee el atributo
                self.attrs.append(attr)
                self.attr_sources.append(k)
        print(f"Creados los atributos {self.attrs} para {self.name}.\nSe leen desde {self.attr_sources}")
        return 1

    async def upload(self):
        """
        Al ser un DataSource, no se escribe nada en el dispositivo ModBus
        :return:
        """
        pass
        return 1

    async def update(self):
        """
        Se actualizan los valores leídos del DataSource
        """
        print(f"Actualizando DataSource {self.name}")
        for idx, src in enumerate(self.attr_sources):
            # print(f"Procesando {src}")
            src_info = getattr(self, src)
            if src_info is None:
                print(f"No se ha definido el origen de datos para {src} en DataSources.json")
                continue
            datatype = src_info[0]
            adr = src_info[1]
            source = {"bus": int(self.bus_id),
                      "device": int(self.device_id),
                      "datatype": datatype,
                      "adr": adr}
            current_value = get_value(source)
            setattr(self, self.attrs[idx], current_value)
            attr_file = f"{phi.EXCHANGE_FOLDER}/{self.bus_id}/{self.slave}/{self.attrs[idx]}"
            # print(f"Actualizando archivo {attr_file}")
            print(f"\t\t\tProcesando archivo {attr_file}")
            exc_file_exists = phi.os.path.isfile(attr_file)
            if not exc_file_exists:
                try:
                    open(attr_file, 'w').close()
                except OSError:
                    print(f"\n\n\tERROR creando el fichero de intercambio {attr_file} para el esclavo {self.slave}")
                else:
                    print(f"\n\t...creado el archivo de intercambio {attr_file} "
                          f"para el esclavo {self.slave}")
            with open(attr_file, "w") as dsf:
                dsf.write(str(current_value))
        else:
            print(f"Actualización de Datasource {self.name} finalizada")

        # 08/07/23 En la clase DataSource se actualizan directamente los archivos desde el método update
        # await update_xch_files_from_devices(self)  # Guarda los valores del dispositivo en el archivo de intercambio
        # # correspondiente.
        return 1

    def __repr__(self):
        """
        Para imprimir la información actual del DataSource
        :return:
        """
        msg = f"\nInformación extraída de {self.name}:\n"
        ds_regmap = get_regmap(self)  # Diccionario con el mapa de registros del DataSource
        # print(f"{self.name}.__repr__: Registros obtenidos: {ds_regmap}")
        for idx, src in enumerate(self.attr_sources):
            val_src = getattr(self, src)
            datatype = val_src[0]
            adr = str(val_src[1])  # El número de registro en el json de datasourdes es integer
            regs = ds_regmap.get(datatype)
            if not regs:
                print(f"El DataSource {self.name} no tiene definidos {datatype} en su mapa de registros")
                continue
            ds_description = regs.get(adr).get("descr").get(phi.LANGUAGE)
            ds_reg_value = getattr(self, self.attrs[idx])
            msg += f"\t{ds_reg_value}\t\t{ds_description}\n"
        # msg = f"DataSource {self.name}"
        return msg


# DICCIONARIO CON LAS CLASES DE DISPOSITIVOS DEL SISTEMA
SYSTEM_CLASSES = {
    "mbdevice": phi.MBDevice,
    "modbusregistermap": phi.ModbusRegisterMap,
    "ufhccontroller": UFHCController,
    "tempfluidcontroller": TempFluidController,
    "generator": Generator,
    "fancoil": Fancoil,
    "split": Split,
    "heatrecoveryunit": HeatRecoveryUnit,
    "airzonemanager": AirZoneManager,
    "datasource": DataSource
}

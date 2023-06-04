#!/usr/bin/env python3
import json
from bisect import bisect

import phoenix_init as phi
from mb_utils.mb_utils import get_value, set_value, get_h, get_dp, get_roomgroup_values, update_xch_files_from_devices
from regops.regops import set_hb, set_lb
from project_elements.building import get_temp_exterior, get_hrel_exterior, get_h_exterior


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
        self.dhwsp = None  # Consigna ACS
        self.iv_source = None  # Registro para leer el modo actual de funcionamiento, calefacción o refrigeración
        self.iv_target = None  # Registro para fijar el modo actual de funcionamiento, calefacción o refrigeración
        self.heating_value = None # Valor para pasar el generador a calefacción en iv_target
        self.cooling_value = None # Valor para pasar el generador a refrigeración en iv_target
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
                self.onoff_st = new_st_value

        return self.onoff_st


    async def iv_mode(self, new_iv_mode:[int, None] = None):
        """
        Fija el modo iv del generador.
        EN PHOENIX MODO CALEFACCIÓN=0 Y MODO REFRIGERACIÓN=1.
        EN ECODAN, POR EJEMPLO, CALEFACCIÓN=1 (self.heating_value) / REFRIGEREACIÓN = 3 (self.cooling_value)
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
            self.iv = current_iv_mode
        elif new_iv_mode == phi.HEATING:
            res = await set_value(target, self.heating_value)
            self.iv = phi.HEATING
        elif new_iv_mode == phi.COOLING:
            res = await set_value(target, self.cooling_value)
            self.iv = phi.COOLING
        else:
            print(f"ERROR {__file__}\m\tValor no válido, {new_iv_mode}, para modo Calefacción/Refrigeración "
                  f"en {self.name}. Ver JSON {self.brand}-{self.model}.JSON")
            self.iv = current_iv_mode

        return self.iv


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

        if new_sp is not None:
            if new_sp > phi.TMAX_IMPUL_CALEF or new_sp < phi.TMIN_IMPUL_REFR:
                print(f"{self.name}: Error escribiendo la consigna {new_sp} para el generador {self.name}.\n"
                      f"Está fuera de los límites [{phi.TMIN_IMPUL_REFR} - {phi.TMAX_IMPUL_CALEF}]")
                # Se limita a la temperatura máxima en calefacción y a la mínima en refrigeración
                self.sp = phi.TMAX_IMPUL_CALEF if self.iv == phi.HEATING else phi.TMIN_IMPUL_REFR
            else:
                # Se propaga la nueva consigna en el byte bajo
                res = await set_value(source, new_sp)  # Escritura Modbus
                self.sp = new_sp
        return self.sp


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
                self.dhwsp = phi.TMAX_ACS
            else:
                # Se propaga la nueva consigna en el byte bajo
                res = await set_value(source, new_dhwsp)  # Escritura Modbus
                self.dhwsp = new_dhwsp
        else:
            self.dhwsp = current_dhwsp

        return self.dhwsp


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
            attr_source = self.__getattribute__(k)
            if attr_source is None:
                continue
            datatype = attr_source[0]
            adr = attr_source[1]
            source = {"bus": int(self.bus_id),
                      "device": int(self.device_id),
                      "datatype": datatype,
                      "adr": adr}
            current_attr_val = get_value(source)
            if current_attr_val is not None:
                self.__setattr__(v, current_attr_val)
                print(f"{self.name}. Valor de {v}:\t{current_attr_val}")
        return 1


    async def update(self):
        """
        Propaga al generador el modo de funcionamiento, el estado on/off y la consigna del grupo de habitaciones.
        Si la consigna manual está activada, se aplica el valor de la consigna manual.

        Returns: resultado de la escritura modbus de los valores actualizados o los valores manuales.
        """
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
            await self.iv_mode()
        if self.manual_sp_mode:
            await self.set_sp(self.manual_sp)
        else:
            await self.set_sp(group_supply_water_setpoint)
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
            iv =self.__getattribute__(iv_modes[idx])
            sp =self.__getattribute__(setpoints[idx])
            ti =self.__getattribute__(t_imps[idx])
            valv =self.__getattribute__(valv_st[idx])
            dev_info += f"\nCIRCUITO {circuito}"
            dev_info += f"\n=========="
            dev_info += f"\n\tEstado bomba: {onoff_values.get(st)}"
            dev_info += f"\n\tEstado modo de funcionamiento: {mode_values.get(iv)}"
            dev_info += f"\n\tConsigna de impulusión: {sp} ºC"
            dev_info += f"\n\tTemperatura de impulusión: {ti} ºC"
            dev_info += f"\n\tApertura válvula: {valv}%"

        dev_info += f"\n\nEstado salida digital 4 {active_values.get(self.get_st4())}"
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
        self.iv_source = None  # Origen del dato para el modo calefacción / refrigeración
        self.pump_source = None
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

    async def iv_mode(self, new_iv_mode:[int, None] = None):
        """
        Fija el modo iv de la centralita de suelo radiante.
        Si new_iv_mode es None, devuelve el modo actual
        Param:
            new_iv_mode: modo calefacción (0) / refrigeración (1) a establecer
        Returns:
             Modo calefacción / refrigeración actual
        """
        if self.groups is None:
            print(f"ERROR {__file__} - No se ha definido ningún grupo en el dispositivo {self.name}")
            return
        group_values = await get_roomgroup_values(self.groups[0])
        group_iv = group_values.get("iv")
        if group_iv is not None:
            self.iv = group_iv

        if new_iv_mode is not None and new_iv_mode in [phi.COOLING, phi.HEATING]:
            self.iv = new_iv_mode
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

        return self.pump


    async def set_channel_info(self, channel: int) -> [phi.Dict, None]:
        """
        Actualiza los diccionarios de cada canal con la consigna, temperatura ambiente, humedad relativa,
        temperatura del suelo, estado del actuador y autorización para refrigeración
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
        ch_sources = self.__getattribute__(channel_source_attr)
        for key, value in ch_sources.items():
            datatype = value[0]
            adr = value[1]
            source = {"bus": int(self.bus_id),
                      "device": int(self.device_id),
                      "datatype": datatype,
                      "adr": adr}
            current_value = get_value(source)
            if current_value is None:  # El canal no se utiliza
                return
            self.__setattr__(channel_val_attrs.get(key), current_value)  # actualiza los atributos spx, rtx,
            # etc. siendo x el canal
            channel_info[key] = current_value
        self.__setattr__(channel_attr, channel_info)
        # Si los valores de rt y rh son válidos, se calcula el punto de rocío y la entalpía del canal
        rt = self.__getattribute__(channel_val_attrs.get("rt"))
        rh = self.__getattribute__(channel_val_attrs.get("rt"))
        channel_h_attr = f"h{channel}"
        channel_dp_attr = f"dp{channel}"
        channel_h = 0
        channel_dp = None

        if rt is not None and rh not in [None, '0', 0]:
            if float(rt) < 100 and float(rt) > -100:
                channel_h = await get_h(float(rt), float(rh))
                channel_dp = await get_dp(float(rt), float(rh))
        self.__setattr__(channel_h_attr, channel_h)
        self.__setattr__(channel_dp_attr, channel_dp)

        return self.__getattribute__(channel_attr)

    async def update(self):
        """
        Actualiza todos los atributos del dispositivo ModBus según las últimas lecturas
        :return:
        """
        await self.iv_mode()  # Actualizo el modo IV del grupo
        await self.pump_st()  # Actualizo el estado de la bomba
        for ch in range(12):
            await self.set_channel_info(ch + 1)  # Los canales se identifican del 1 al 12, pero
            # range devuelve de 0 a 11
        await update_xch_files_from_devices(self)  # Guarda los valores del dispositivo en el archivo de intercambio
        # correspondiente
        return 1

    def __repr__(self):
        """
        Representación de la centralita para control de sistemas de suelo radiante
        :return:
        """
        iv_mode = ["Calefacción", "Refrigeración"]
        pump_st = ["Parada", "En Marcha"]
        dev_info = f"\nControlador para suelo radiante {self.name}"
        dev_info += f"\n\tModo de funcionamiento: {iv_mode[self.iv]}"
        dev_info += f"\n\tEstado bomba circuladora: {pump_st[self.pump]}"
        for ch in range(12):
            channel_source_attr = f"ch{ch + 1}_source"
            attr_value = self.__getattribute__(channel_source_attr)
            if attr_value is not None:
                channel_attr = f"ch{ch + 1}"
                channel_info = self.__getattribute__(channel_attr)
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
        self.manual = False
        self.hru_modes = {phi.DESHUMIDIFICACION: False,
                          phi.FANCOIL: False,
                          phi.FREE_COOLING: False,
                          phi.VENTILACION: True}
        self.hru_mode = phi.VENTILACION
        self.man_hru_mode_st = phi.OFF  # Para fijar manualmente el modo de funcionamiento
        self.man_hru_mode = phi.VENTILACION
        self.manual = False  # Valor manual de velocidad o caudal de aire
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
        self.bypass_target = None  # Registro y tipo de registro para operar con el bypass
        self.bypass_source = None  # Registro y tipo de registro para leer estado bypass
        self.bypass_st = None
        self.dampers_source = None
        self.dampers_st = None
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
        return self.supply_flow, self.exhaust_flow


    async def set_speed(self, new_speed: [int, None] = None):
        """
        Aplica al recuperador la velocidad 'new_speed'.
        Si 'new_speed' is None, devuelve la velocidad actual del recuperador. Si hay más de un relé de velocidad
        activado, se toma el más alto.
        Si 'new_speed es 0, se ponen a 0 todas las velocidades

        Returns: Velocidad actual del recuperador
        """
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
                self.speed = 0
                if spd_value == phi.ON:
                    res = await set_value(target, phi.OFF)
            elif new_speed is None:
                if spd_value:
                    current_speed = spd
                    self.speed = spd
            elif new_speed == spd:
                res = await set_value(target, phi.ON)
                current_speed = spd
                self.speed = spd
            else:
                res = await set_value(target, phi.OFF)

        if current_speed == 0:  # No se ha seleccionado ninguna velocidad y el recuperador estaba apagado
            self.speed = 0

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
            elif self.manual_speed == spd:
                res = await set_value(target, phi.ON)
                self.speed = spd
            else:
                res = await set_value(target, phi.OFF)

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
        if current_pos == new_pos or new_pos is None:
            self.dampers_st = current_pos
        else:
            res = await set_value(source, new_pos)
            self.dampers_st = new_pos

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
        if current_pos == new_pos or new_pos is None:
            self.valv_st = current_pos
        else:
            res = await set_value(source, new_pos)
            self.valv_st = new_pos

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
            self.bypass_st = new_pos if res else current_pos

        return self.bypass_st

    async def get_op_mode(self) -> int:
        """
        Determina el modo de funcionamiento a fijar en el recuperador.
            0: HRU off
            1: DESHUMIDIFICACION
            2: FANCOIL / APOYO A LA CLIMATIZACIÓN
            4: FREE_COOLING
            5: FREE_COOLING + DESHUMIDIFICACIÓN
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
        group_rt = (float(room.rt()) for room in group.roomgroup)  # Generador con las temperaturas de las habitaciones
        group_sp = group.air_sp  # Consigna de ambiente calculada para el grupo
        group_dp = group.air_dp  # Punto de rocío del grupo
        group_h = group.air_h  # Entalpía del grupo
        if group_cooling_mode:
            for rt in group_rt:
                if rt < group_dp + phi.OFFSET_ACTIVACION_DESHUMIDIFICACION:
                    dehumid_mode = True
                    self.hru_mode = phi.DESHUMIDIFICACION
            building = group.roomgroup[0].building_id  # Edificio al que pertenece el grupo de habitaciones
            t_ext = get_temp_exterior(building)  # Temperatura exterior
            rh_ext = get_hrel_exterior(building)
            if rh_ext == 0 or rh_ext is None:  # El freecooling debe ser térmico
                if t_ext < min(group_rt):  # Se activa el freecooling térmico
                    freecooling_mode = True
            else:  # Se comprueba si se puede habilitar el free-cooling entálpico
                h_ext = get_h_exterior()  # Entalpía exterior
                if h_ext < group_h:
                    freecooling_mode = True

        if not dehumid_mode:
            if group_cooling_mode and group_sp < max(group_rt) + phi.OFFSET_COOLING or \
                    not group_cooling_mode and group_sp > min(group_rt) + phi.OFFSET_HEATING:  # OFFSET_HEATING es
                # siempre < 0
                fancoil_mode = True
                self.hru_mode = phi.FANCOIL

        if freecooling_mode:
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
            Válvula de 3 vías cerrada
            Bypass recuperador abierto
        :return:
        """
        print(f"Activando freecooling en el recuperador {self.name}")
        await self.set_speed(phi.MAX_HRU_SPEED)
        await self.set_airflow(self.max_airflow)
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
                ventilation_airflow = int(self.max_airflow * max_af_pct)  # Se fija el caudal de aire en función de la calidad.
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
            5: FREE_COOLING + DESHUMIDIFICACIÓN
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
                 6: (self.fancoil_mode(), self.freecooling_mode),
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

    async def update(self):
        """
        Propaga al recuperador el modo de funcionamiento y almacena los valores de los distintos atributos
        definidos en phi.HEATRECOVERYUNIT_R_FILES en los archivos correspondientes de phi.HEATRECOVERYUNIT_R_FILES
        TODO comprobar modificaciones desde la web como la consigna de AQ, el on/off, la velocidad del ventilador,
        TODO o el estado de válvula y compuertas
        Returns: resultado de la escritura modbus de los valores actualizados
        """
        if self.man_hru_mode_st == phi.ON:
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
        dev_info += f"\t:Modo de funcionamiento: {hru_modes_descr.get(self.hru_mode)}\n"
        dev_info += f"\t:Modo manual ventilador {manual.get(self.manual)}\n"
        if por_caudal:
            dev_info += f"\t:Caudal del recuperador {self.supply_flow}\n"
        else:
            dev_info += f"\t:Velocidad ventilador {self.speed}\n"
        dev_info += f"\t:Estado válvula {self.valv_st}\n"
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
            self.__setattr__(sp_target, new_sp_value)
        return self.__getattribute__(sp_target)

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
            self.__setattr__(rt_target, new_rt_value)
        return self.__getattribute__(rt_target)

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
            self.fan_speed = auto_speed
        elif man_speed is None:
            self.fan_speed = current_speed
        elif man_speed not in [0, 1, 2, 3]:
            self.fan_speed = current_speed
            print(f"ERROR - No se puede fijar una velocidad de {man_speed} en el fancoil {self.name}.\n"
                  f"Rango: (0, 1, 2, 3)")
        else:
            res = await set_value(manual_speed_target, man_speed)
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
        sp1 = room1.sp()
        rt1 = room1.rt()
        sp2 = room2.sp()
        rt2 = room2.rt()
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
        self.act_man_sp1 = None  # Activación selección manual consigna impulsión circuito 1
        self.man_sp1 = None  # Valor manual consigna impulsión circuito 1
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
        self.act_man_sp2 = None  # Activación selección manual consigna impulsión circuito 2
        self.man_sp2 = None  # Valor manual consigna impulsión circuito 2
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
        self.act_man_sp3 = None  # Activación selección manual consigna impulsión circuito 3
        self.man_sp3 = None  # Valor manual consigna impulsión circuito 3
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
        targets = ("st1_target", "st2_target", "st3_target")
        states = ("st1", "st2", "st3")
        idx = circuit - 1  # Índice de los valores del circuito en las listas de atributos

        st_target = self.__getattribute__(targets[idx])
        if st_target is None or circuit not in (1, 2, 3):
            return
        datatype = st_target[0]
        adr = st_target[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}
        current_st = get_value(target)
        if new_st_value is not None:
            if new_st_value not in [phi.OFF, phi.ON]:
                print(f"{self.name}: Error accionando la bomba del circuito {circuit} con el valor {new_st_value}")
                self.__setattr__(states[idx], current_st)
            else:
                res = await set_value(target, new_st_value)
                self.__setattr__(states[idx], new_st_value)
        else:
            self.__setattr__(states[idx], current_st)

        state = self.__getattribute__(states[idx])
        return state

    async def man_onoff(self, circuit: int = 1,
                        new_man_mode: [int, None] = None,
                        new_st_value: [int, None] = None) -> [phi.Tuple[int, int], None]:
        """
        Activa y desactiva el modo manual de funcionamiento de la bomba circuladora del circuito 'circuit' y, cuando
        está activado, la arranca o para dependiendo del valor de new_st_value
        Si new_man_mode es None, devuelve el valor de activación del modo manual: 1:activado / 0:desactivado
        Returns: Tupla con el estado del modo manual y valor manual configurado para la bomba
        """
        manual_states_attributes = ("act_man_st1", "act_man_st2", "act_man_st3")
        manual_states_values_attributes = ("man_st1", "man_st2", "man_st3")
        idx = circuit - 1  # Índice de los valores del circuito en las listas de atributos
        if new_man_mode is not None:
            if new_man_mode not in [phi.OFF, phi.ON]:
                print(f"\n{self.name}: Error activando modo manual para la bomba del circuito {circuit} con el "
                  f"valor {new_man_mode}")
            else:
                # Actualizo el estado de activación del modo manual
                self.__setattr__(manual_states_attributes[idx], new_man_mode)

        if new_st_value is not None:
            if new_st_value not in [phi.OFF, phi.ON]:
                print(f"\n{self.name}: Error activando la bomba del circuito {circuit} con el "
                      f"valor {new_st_value}")
            else:
                self.__setattr__(manual_states_values_attributes[idx], new_st_value)

        # Bomba en modo manual: propago el valor manual a la salida si está activado
        if new_man_mode == phi.ON:
            await self.onoff(circuit, new_st_value)

        current_man_st = self.__getattribute__(manual_states_attributes[idx])
        current_man_val = self.__getattribute__(manual_states_values_attributes[idx])
        return current_man_st, current_man_val

    async def iv_mode(self, circuit: int = 1, new_iv_mode: [int, None] = None) -> [int, None]:
        """
        Si new_iv_mode es None, devuelve el modo de funcionamiento del circuito 'circuit'
        Param:
            circuit: circuito en el que se gestiona el modo off/refrigeración/calefacción
            new_iv_mode: modo a propagar al controlador de temperatura de impulsión
        Returns: Modo actual de funcionamiento del circuito 
        """
        sources = ("iv1_source", "iv2_source", "iv3_source")
        modes = ("iv1", "iv2", "iv3")
        idx = circuit - 1  # Índice de los valores del circuito en las listas de atributos

        iv_mode_source = self.__getattribute__(sources[idx])
        if iv_mode_source is None or circuit not in (1, 2, 3):
            return
        datatype = iv_mode_source[0]
        adr = iv_mode_source[1]
        target = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}

        current_register_value = None
        current_iv_sp = get_value(value_source=target)  # El SIG610 almacena CONSIGNA en byte bajo y MODO en byte alto
        if current_iv_sp is not None:
            current_iv, current_sp = current_iv_sp
            self.__setattr__(modes[idx], current_iv)
            current_register_value = current_iv * 256 + current_sp
        if new_iv_mode is not None:
            if new_iv_mode not in [0, 1, 2]:
                print(f"{self.name}: Error activando el modo del circuito {circuit} con el valor {new_iv_mode}")
                # Se mantiene el modo actual
            else:
                # Se propaga el nuevo modo de funcionamiento
                # Actualizo el valor del modo de funcionamiento (byte alto)
                new_val = set_hb(current_register_value, int(new_iv_mode))
                res = await set_value(target, new_val)  # Escritura Modbus
                self.__setattr__(modes[idx], new_iv_mode)
        mode = self.__getattribute__(modes[idx])
        return mode

    async def sp(self, circuit: int = 1, new_sp: [int, None] = None) -> [int, None]:
        """
        Si new_sp es None, devuelve el valor actual de la consigna del circuito 'circuit'
        Param:
            circuit: circuito en el que se gestiona la consigna de temperatura de impulsión de agua
            new_sp: Nueva consigna a aplicar
        Returns: Consigna de control de temperatura de impulsión de agua del circuito 'circuit' 
        """
        sources = ("sp1_source", "sp2_source", "sp3_source")
        setpoints = ("sp1", "sp2", "sp3")
        idx = circuit - 1  # Índice de los valores del circuito en las listas de atributos

        sp_source = self.__getattribute__(sources[idx])
        if sp_source is None or circuit not in (1, 2, 3):
            return
        datatype = sp_source[0]
        adr = sp_source[1]
        source = {"bus": int(self.bus_id),
                  "device": int(self.device_id),
                  "datatype": datatype,
                  "adr": adr}

        current_register_value = None
        current_iv_sp = get_value(value_source=source)  # El SIG610 almacena CONSIGNA en byte bajo y MODO en byte alto

        if current_iv_sp is not None:
            current_iv, current_sp = current_iv_sp
            self.__setattr__(setpoints[idx], current_sp)
            current_register_value = current_iv * 256 + current_sp
        if new_sp is not None:
            if new_sp > 55 or new_sp < 5:
                print(f"{self.name}: Error escribiendo la consigna {new_sp} para el circuito {circuit}")
                # Se mantiene la consigna actual
            else:
                # Se propaga la nueva consigna en el byte bajo
                new_val = set_lb(current_register_value, int(new_sp))
                res = await set_value(source, new_val)  # Escritura Modbus
                self.__setattr__(setpoints[idx], new_sp)
        setpoint = self.__getattribute__(setpoints[idx])
        return setpoint

    async def man_sp(self, circuit: int = 1,
                     man_set_sp_mode: [int, None] = None,
                     man_sp: [int, None] = None) -> [phi.Tuple[int, int], None]:
        """
        Fija la consigna de impulsión del circuito 'circuit' en lugar de utilizar el valor calculado
        desde el grupo de habitaciones.

        Activa y desactiva el ajuste manual de la consigna y, cuando está activado, propaga la consigna almacenada
        en 'man_sp'
        Param:
            circuit: circuito en el que se va a fijar la consigna de forma manual en lugar de la calculada
            para el grupo de habitaciones
            man_set_sp_mode: estado activado o desactivado del ajuste manual de la consigna
            man_sp: valor manual de consigna a aplicar.
        Si man_set_sp_mode es None, devuelve el valor de activación del ajuste manual de consigna:
        1:activado / 0:desactivado y el valor de consigna configurado como manual.
        Returns: Tupla con el estado del ajuste manual de la consigna y valor manual configurado
        """
        manual_sp_states = ("act_man_sp1", "act_man_sp2", "act_man_sp3")
        manual_sp_values = ("man_sp1", "man_sp1", "man_sp1")
        idx = circuit - 1  # Índice de los valores del circuito en las listas de atributos

        current_man_st = self.__getattribute__(manual_sp_states[idx])
        current_man_val = self.__getattribute__(manual_sp_values[idx])

        if man_set_sp_mode is not None:
            if man_set_sp_mode not in [phi.OFF, phi.ON]:
                print(f"\n{self.name}: Error activando modo manual para ajuste de consigna del circuito {circuit} "
                      f"con el valor {man_set_sp_mode}")
                self.__setattr__(manual_sp_states[idx], current_man_st)
            else:
                self.__setattr__(manual_sp_states[idx], man_set_sp_mode)
        else:
            self.__setattr__(manual_sp_states[idx], current_man_st)

        if man_sp is not None:
            if man_sp > 55 or man_sp < 5:
                print(f"\n{self.name}: Error estableciendo la consigna del circuito {circuit} con el "
                      f"valor {man_sp} (Rango 5-55 °C)")
                self.__setattr__(manual_sp_values[idx], current_man_val)
            else:
                self.__setattr__(manual_sp_values[idx], man_sp)
        else:
            self.__setattr__(manual_sp_values[idx], current_man_val)

        current_man_st = self.__getattribute__(manual_sp_states[idx])
        current_man_val = self.__getattribute__(manual_sp_values[idx])
        if current_man_st == phi.ON:  # Se aplica la consigna manual
            await self.sp(circuit, current_man_val)

        return current_man_st, current_man_val
    
    async def ti(self, circuit: int = 1):
        """
        Devuelve el valor de la temperatura de impulsión del circuito 'circuit'
        Param:
            circuit: Circuito cuya temperatura de impulsión se desea leer: 1, 2 ó 3.
        Returns: Temperatura de impulsión del circuito 'circuit'
        """
        sources = ("ti1_source", "ti2_source", "ti3_source")
        values = ("ti1", "ti2", "ti3")
        idx = circuit - 1  # Índice de los valores del circuito en las listas de atributos

        ti_source = self.__getattribute__(sources[idx])
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
            self.__setattr__(values[idx], current_ti)
        ti = self.__getattribute__(values[idx])
        return ti

    async def valv(self, circuit: int = 1):
        """
        Devuelve la posición de la válvula del circuito 'circuit'
        Param:
            circuit: Circuito cuya temperatura de impulsión se desea leer: 1, 2 ó 3.
        Returns: % apertura válvula del circuito 'circuit'
        """
        sources = ("v1_source", "v2_source", "v3_source")
        values = ("v1", "v2", "v3")
        idx = circuit - 1  # Índice de los valores del circuito en las listas de atributos

        valv_source = self.__getattribute__(sources[idx])
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
            self.__setattr__(values[idx], current_pos)
        valv_position = self.__getattribute__(values[idx])
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

    async def update(self):
        """
        Propaga a cada circuito, el modo de funcionamiento, el estado on/off y la consigna de cada uno
        de los grupos de habitaciones. Puede haber hasta 3 grupos de habitaciones.
        El circuito 1 corresponde al primer grupo, el circuito 2 al segundo y así sucesivamente
        Returns: resultado de la escritura modbus de los valores actualizados o los valores manuales.
        """
        bomba_manual = {0: self.act_man_st1, 1: self.act_man_st2, 2: self.act_man_st3}
        valores_bomba_manual = {0: self.man_st1, 1: self.man_st2, 2: self.man_st3}
        consigna_manual = {0: self.act_man_sp1, 1: self.act_man_sp2, 2: self.act_man_sp3}
        valores_consigna_manual = {0: self.man_sp1, 1: self.man_sp2, 2: self.man_sp3}
        with open(phi.ROOMGROUPS_VALUES_FILE, "r") as f:
            roomgroups_values = json.load(f)

        for idx, roomgroup_id in enumerate(self.groups):
            circuito = idx + 1
            await self.onoff(circuito)
            await self.iv_mode(circuito)
            await self.sp(circuito)
            await self.ti(circuito)
            await self.valv(circuito)
            self.get_st4()
            update_st = None
            modo_manual_activado = bomba_manual.get(idx)
            valor_bomba_manual = valores_bomba_manual.get(idx)
            consigna_manual_activada = consigna_manual.get(idx)
            valor_consigna_manual = valores_consigna_manual.get(idx)
            roomgroup = roomgroups_values.get(roomgroup_id)  # Objeto del grupo RoomGroup
            if roomgroup is None:
                continue
            if roomgroup.get("demanda") != 0:
                # Hay demanda de refrigeración (demanda = 1) o de calefacción (demanda = 2). Se propaga el modo iv
                iv = 1 if roomgroup.iv else 2  # roomgroup.iv es  1 en refrigeración
                # Se arranca la bomba circuladora SI NO ESTÁ EN MODO MANUAL
                if not modo_manual_activado:
                    update_st = await self.onoff(circuito, phi.ON)
            else:
                iv = 0
                # No hay demanda. Se para la bomba circuladora SI NO ESTÁ EN MODO MANUAL
                if not modo_manual_activado:
                    update_st = await self.onoff(circuito, phi.OFF)
                else:
                    update_st = valor_bomba_manual
            update_iv = await self.iv_mode(circuito, iv)  # Se actualiza el modo de funcionamiento al dispositivo
            sp = int(roomgroup.get("water_sp"))  # water_sp es float, pero en el dispositivo se escribe un int
            if not consigna_manual_activada:
                update_sp = await self.sp(circuito, sp)
            else:
                update_sp = valor_consigna_manual

        await update_xch_files_from_devices(self)  # Guarda los valores del dispositivo en el archivo de intercambio
        # correspondiente

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
            iv =self.__getattribute__(iv_modes[idx])
            sp =self.__getattribute__(setpoints[idx])
            ti =self.__getattribute__(t_imps[idx])
            valv =self.__getattribute__(valv_st[idx])
            dev_info += f"\nCIRCUITO {circuito}"
            dev_info += f"\n=========="
            dev_info += f"\n\tEstado bomba: {onoff_values.get(st)}"
            dev_info += f"\n\tEstado modo de funcionamiento: {mode_values.get(iv)}"
            dev_info += f"\n\tConsigna de impulusión: {sp} ºC"
            dev_info += f"\n\tTemperatura de impulusión: {ti} ºC"
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
        self.man_pos_valv = phi.OPEN  # Posición de la válvula en modo manual
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
            self.onoff_st = new_status
        return self.onoff_st

    async def demanda_st(self):
        """
        Devuelve el valor de la demanda del fancoil
        Returns:
            0: No hay demanda
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
        current_st_mode, current_demand = get_value(source)  # El registro 21 del SIG311 devuelve en el byte alto el
        # estado 0: off, el modo 1: on en calefacción o el modo 2: on en refrigeración. En el byte bajo devuelve
        # 0: si no hay demanda, 1: demanda de calor, 2: demanda de frío
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
        if new_rt_value is None or current_rt > 50 or current_rt < 0:
            print(f"ERROR {self.name} - No se puede leer la temperatura ambiente.\nSe para el fancoil por seguridad")
            await self.manual_fan_speed(manual_mode=phi.ON, man_speed=phi.OFF)  # Parada manual
            self.rt = current_rt
        elif new_rt_value > 50 or new_rt_value < 0:
            await self.manual_fan_speed(manual_mode=phi.OFF)  # Se activa la selección automática de velocidad
            print(f"{self.name}: ERROR estableciendo una temperatura ambiente de {new_rt_value} en el "
                  f"fancoil {self.name} (rango 0-50)")
            self.rt = current_rt
        else:
            await self.manual_fan_speed(manual_mode=phi.OFF)  # Se activa la selección automática de velocidad
            print(f"fancoil.set_sp: Actualizando temperatura ambiente con valor {new_rt_value} en fancoil {self.name}")
            res = await set_value(source, new_rt_value)
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
            cont_cooling = new_val_cooling
        if fan_mode_heating is not None:
            # Actualizo el modo del ventilador para refrigeración (byte alto)
            new_val_heating = set_lb(current_value, int(fan_mode_heating))
            res = await set_value(source, new_val_heating)  # Escritura en el dispositivo ModBus
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
        if not man_speed is None:
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
        else:
            man_speed = current_man_speed

        if manual_mode is not None:
            print(f"{self.name} - Estableciendo al valor {manual_mode} para el Ajuste Manual de Velocidad "
                  f"en el esclavo {self.slave}, dirección  {manual_mode_target}")
            res = await set_value(manual_mode_target, manual_mode)  # Se activa o desactiva el modo manual indicado
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

        if (not max_speed is None and not max_speed in SPEED_VALUES.get(fan_type)) or \
                (not min_speed is None and not min_speed in SPEED_VALUES.get(fan_type)):
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
                self.speed_limit = (max_speed, current_min)
        else:  # Se modifican las velocidades máxima y mínima de funcionamiento del fancoil.
            new_limits = max_speed * 256 + min_speed
            res = await set_value(source, new_limits)
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
        if not new_position is None:
            if new_position not in [phi.CLOSED, phi.OPEN]:
                print(f"La posición seleccionada, {new_position}, para la válvula del fancoil {self.name} "
                      f"no es válida. Debe ser 1 (abierta) o 0 (cerrada). \n"
                      f"Se mantiene la configuración de manual actual.")
                new_position = current_manual_position
            else:
                # Se actualiza el valor de posición manual de la válvula
                res = await set_value(target, new_position)  # Escritura en el dispositivo ModBus

        if manual_mode is not None:
            res = await set_value(source, manual_mode)  # Se activa o desactiva el modo manual indicado
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
        with open(phi.ROOMGROUPS_VALUES_FILE, "r") as f:
            roomgroups_values = json.load(f)

        roomgroup = roomgroups_values.get(self.groups[0])  # Datos del grupo de habitaciones asociado al fancoil
        if roomgroup is None:
            print(f"No se ha encontrado información del grupo de habitaciones {self.groups[0]}")

        self.iv = await self.iv_mode(roomgroup.get("iv"))  # 0:Calefaccion / 1:Refrigeracion
        fancoil_sp = roomgroup.get("air_sp") + phi.OFFSET_COOLING if self.iv \
            else roomgroup.get("air_sp") + phi.OFFSET_HEATING  # Offset heating tiene un valor negativo
        self.sp = await self.set_sp(new_sp_value=fancoil_sp)
        fancoil_rt = roomgroup.get("air_rt")
        self.rt = await self.set_rt(new_rt_value=fancoil_rt)
        self.onoff_st = await self.onoff()
        self.demand = await self.demanda_st()
        self.iv = await self.iv_mode()
        self.fan_type = self._get_fan_type()
        self.fan_auto_cont = await self.fan_auto_cont_mode()
        self.fan_speed = await self.get_fan_speed()
        self.manual_fan = await self.manual_fan_speed()
        self.speed_limit = await self.set_speed_limit()
        await self.valv_manual_open()
        self.valv_st = await self.get_valv_st()
        self.remote_onoff = await self.remote_onoff_mode()
        self.sd_aux = await self.sd_aux_st()
        self.floor_temp = await self.get_floor_temp()
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
        estado_manual_ventilador = self.manual_fan[0]
        dev_info = f"\nFancoil {self.name}\n"
        dev_info += f"\tEstado: {onoff.get(self.onoff_st)}\n"
        dev_info += f"\t:Modo de funcionamiento: {modo.get(self.iv)}\n"
        dev_info += f"\t:Consigna {self.sp}\n"
        dev_info += f"\t:Temperatura ambiente {self.rt}\n"
        dev_info += f"\t:Demanda {demanda.get(self.demand)}\n"
        dev_info += f"\t:Velocidad {self.fan_speed}\n"
        dev_info += f"\t:Modo ventilador {manual.get(estado_manual_ventilador)}\n"
        dev_info += f"\t:Estado válvula {self.valv_st}\n"
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

    async def update(self):
        """
        Se actualizan los valores leídos del DataSource
        """
        raise NotImplementedError(f"ERROR {__file__}. Método UPDATE no implementado en DataSources")
    def __repr__(self):
        """
        Para imprimir la información actual del DataSource
        :return:
        """
        raise NotImplementedError(f"ERROR {__file__}. Método __REPR__ no implementado en DataSources")


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

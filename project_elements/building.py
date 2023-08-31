#!/usr/bin/env python3
"""
Definición de las clases que definen los objetos del edificio: Edificio,
Viviendas, Habitaciones, Grupos de habitaciones...
"""
import sys
from os import path
from gc import collect
import phoenix_init as phi
from asyncio import create_task, gather
from mb_utils.mb_utils import get_value


def init_modo_iv() -> int:
    """
    Inicializa el modo de funcionamiento general en función de la época del año.
    IMPORTANTE que el controlador esté en hora
    Returns: Cooling <=> 1 entre junio y septiembre, Heating <==> 0, el resto de los meses
    """
    mes = phi.datetime.now().month
    modo_iv = phi.COOLING if 5 < mes < 10 else phi.HEATING
    return modo_iv


def get_default_t_exterior() -> float:
    """
    Devuelve el valor por defecto de temperatura exterior del proyecto en función del mes en curso
    Returns: temperatura exterior por defecto
    """
    mes = phi.datetime.now().month
    t_ext = phi.DEFAULT_TEMP_EXTERIOR_VERANO if 5 < mes < 10 else phi.DEFAULT_TEMP_EXTERIOR_INVIERNO
    return t_ext


async def get_modo_iv(bld: str = "1") -> [int, None]:
    """
        Obtiene el modo actual de funcionamiento del sistema: Calefacción = 0, Refrigeración = 1
        """
    modo_iv = init_modo_iv()
    bld_data = phi.prj.get("buildings")[bld]
    if bld_data is None:
        print(f"ERROR (get_modo_iv) - No se ha definido edificio {bld}")
        sys.exit()
    iv_source = bld_data.get("iv_source")
    if iv_source is None:
        msg = f"WARNING (get_modo_iv) - No se indicado origen de lectura del modo Frío/Calor en el " \
              f"edificio {bld}. Se toman valores por defecto"
        print(msg)
        return modo_iv
    modo_iv_from_mbdev_source = iv_source.get("mbdev")
    modo_iv_from_file_source = iv_source.get("file")  # El modo_iv siempre se va a guardar en este archivo
    if modo_iv_from_mbdev_source not in [None, {}]:  # Si el modo IV se obtiene de un  dispositivo, ese dispositivo
        # debe tener un atributo iv que vale 0 en calefacción y 1 en refrigeración
        # modo_iv = get_value(modo_iv_from_mbdev_source)
        bus_id = str(
            modo_iv_from_mbdev_source.get("bus"))  # En el JSON, el bus_id que conecta la habitación con el dispositivo
        # se introduce como un entero, pero la clave del diccionario con los datos leídos son str
        device_id = str(
            modo_iv_from_mbdev_source.get("device"))  # # OJO, es el ID del Device en la base de datos, NO EL SLAVE
        device = phi.buses.get(bus_id).get(device_id)  # Devuelve el dispositivo en el que se va a escribir
        # modo_iv = await device.iv_mode()
        modo_iv = await device.iv_mode()
        print(f"El modo Frío/Calor se lee del dispositivo ModBus {device.name}.\n\tValor leido: {modo_iv}")
        modo_iv_file = phi.EXCHANGE_FOLDER + modo_iv_from_file_source
        modo_iv_file_exists = path.isfile(modo_iv_file)
        if not modo_iv_file_exists:
            try:
                open(modo_iv_file, 'w').close()
            except OSError:
                print(f"\n\n\tERROR creando el fichero para el modo IV {modo_iv_file}")
            else:
                print(f"\n\t...creado el fichero para el modo IV {modo_iv_file}")
        with open(modo_iv_file, "w") as ivf:
            print(f"Guardando el modo Frío/Calor en {modo_iv_file}")
            ivf.write(str(modo_iv))
    elif modo_iv_from_file_source:
        modo_iv_file = phi.EXCHANGE_FOLDER + modo_iv_from_file_source
        if path.isfile(modo_iv_file):
            print("El modo Frío/Calor se lee de un archivo")
            with open(modo_iv_file, "r") as ivf:
                modo_iv = int(ivf.read())
    return modo_iv


def get_temp_exterior(bld: str = "1") -> [float, None]:
    """
        Obtiene el valor actual de la temperatura exterior del edificio según el origen definido en la
        clave 'o_data.te_source' del edificio.
        Cuando dentro de te_source existe la clave mbdev, la temperatura exterior se lee de la base de
        datos que almacena las lecturas de los dispositivos ModBus
        Returns: valor de la temperatura exterior.
        Si no se conoce, se consideran cte.DEFAULT_TEMP_EXTERIOR_VERANO (35 °C) en modo refrigeración y
        cte.DEFAULT_TEMP_EXTERIOR_INVIERNO (3 °C) en modo calefacción
        """
    bld_data = phi.prj.get("buildings")[bld]
    if bld_data is None:
        print(f"ERROR (get_temp_exterior) - No se ha definido edificio {bld}")
        sys.exit()
    o_data = bld_data.get("o_data")
    if o_data is None:
        msg = f"WARNING (get_temp_exterior) - No se indicado origen de lectura de valores exteriores en el " \
              f"edificio {bld}. Se toman valores por defecto"
        print(msg)
        return get_default_t_exterior()
    te_source = o_data.get("te_source")
    if te_source is None:
        msg = f"WARNING (get_temp_exterior) - No se indicado origen de lectura de temperatura exterior en el " \
              f"edificio {bld}. Se toman valores por defecto"
        print(msg)
        return get_default_t_exterior()
    t_ext_from_mbdev_source = te_source.get("mbdev")
    t_ext_from_file_source = te_source.get("file")
    if t_ext_from_mbdev_source not in [None, {}]:
        t_ext = get_value(t_ext_from_mbdev_source)
        print("La temperatura exterior se lee de un dispositivo ModBus")
        print(f"Valor de temperatura exterior leido: {t_ext}\n")
        t_ext_file = phi.EXCHANGE_FOLDER + t_ext_from_file_source
        with open(t_ext_file, "w") as ivf:
            print(f"Guardando temperatura exterior en {t_ext_file}")
            ivf.write(str(t_ext))
        return t_ext
    elif t_ext_from_file_source:
        print("La temperatura exterior se lee de un archivo")
        t_ext_file = phi.EXCHANGE_FOLDER + t_ext_from_file_source
        if path.isfile(t_ext_file):
            with open(t_ext_file, "r") as txf:
                t_ext = float(txf.read())
                return t_ext
    else:
        return get_default_t_exterior()


def get_hrel_exterior(bld: str = "1") -> [float, None]:
    """
        Obtiene el valor actual de la humedad relativa exterior del edificio según el origen definido en la
        clave 'o_data.rhe_source' del edificio.
        Cuando dentro de rh_source existe la clave mbdev, la humedad relativa exterior se lee de la base de
        datos que almacena las lecturas de los dispositivos ModBus
        Returns: valor de la temperatura exterior.
        Si no se conoce, se consideran cte.DEFAULT_TEMP_EXTERIOR_VERANO (35 °C) en modo refrigeración y
        cte.DEFAULT_TEMP_EXTERIOR_INVIERNO (3 °C) en modo calefacción
        """
    bld_data = phi.prj.get("buildings")[bld]
    if bld_data is None:
        print(f"ERROR {__file__} - No se ha definido edificio {bld}")
        sys.exit()
    o_data = bld_data.get("o_data")
    if o_data is None:
        msg = f"WARNING {__file__} - No se indicado origen de lectura de valores exteriores en el " \
              f"edificio {bld}. Se fija la humedad a 0"
        print(msg)
        return 0
    rh_source = o_data.get("rh_source")
    if rh_source is None:
        msg = f"WARNING {__file__} - No se indicado origen de lectura de la humedad relativa exterior en el " \
              f"edificio {bld}. Se fija la humedad a 0"
        print(msg)
        return 0
    rh_ext_from_mbdev_source = rh_source.get("mbdev")
    rh_ext_from_file_source = rh_source.get("file")
    if rh_ext_from_mbdev_source not in [None, {}]:
        print("La humedad relativa exterior se lee de un dispositivo ModBus")
        hr_ext = get_value(rh_ext_from_mbdev_source)
        return hr_ext
    elif rh_ext_from_file_source:
        print("La humedad relativa exterior se lee de un archivo")
        hr_ext_file = phi.EXCHANGE_FOLDER + rh_ext_from_file_source
        if path.isfile(hr_ext_file):
            with open(hr_ext_file, "r") as hrxf:
                hr_ext = float(hrxf.read())
                return hr_ext
    else:
        return 0


def get_h_exterior(bld: str = "1", altitud=phi.ALTITUD) -> [float, None]:
    """
    Calcula la entalpia exterior con temp en celsius y hr en %. Por defecto se toma la altitud de Madrid
    Si no se lee la humedad relativa exterior, se devuelve 0
    """
    te = get_temp_exterior(bld)
    rh = get_hrel_exterior(bld)
    print(f"Calculando entalpía exterior con temperatura:{te} y humedad relativa {rh}")
    if rh is None or rh == 0:
        return 0
    pres_total = 101325 if altitud is None else 101325 * (1 - 2.25577 * 0.00001 * altitud) ** 5.2559
    nullvalues = ("", None, "false")
    if any((te in nullvalues, rh in nullvalues)):
        return
    pres_vap_sat = 10 ** (7.5 * te / (273.159 + te - 35.85) + 2.7858)  # Pa
    # print(f"presion vapor saturado: {pres_vap_sat}")
    pres_vap = pres_vap_sat * rh / 100  # Pa
    # print(f"presion total: {pres_total}")
    # print(f"presion vapor: {pres_vap}")
    pres_aire_seco = pres_total - pres_vap  # Pa
    # print(f"presion aire seco: {pres_aire_seco}")
    hum_especifica = 0.621954 * (pres_vap / pres_aire_seco)  # kg agua / hg aire seco
    entalpia = (1.006 + 1.86 * hum_especifica) * te + 2501 * hum_especifica
    return round(entalpia, 1)


class Room:
    """
    Objeto de clase Room, con información sobre el edificio y la vivienda a la que pertenece,
    el nombre de la habitación, el grupo o grupos de habitaciones a los que pertenece, el origen de
    los datos que son necesarios para el sistema: consigna, temperatura, etc..
    A partir del origen de esos datos, se rellenan los atributos de la habitación del tipo consigna, temperatura,
    estado actuador, punto de rocío, entalpía, etc.
    """

    def __init__(self,
                 building_id: str = "",
                 dwelling_id: str = "",
                 room_id: str = "",
                 name: str = "",
                 groups: [list, None] = None,
                 iv_source: [dict, None] = None,
                 sp_source: [dict, None] = None,
                 rh_source: [dict, None] = None,
                 rt_source: [dict, None] = None,
                 st_source: [dict, None] = None,
                 af: [int, float, None] = None,
                 aq_source: [dict, None] = None,
                 aqsp_source: [dict, None] = None,
                 offsetairref: float = phi.OFFSET_COOLING,  # 2ª etapa refrigeración fancoil/recuperador
                 offsetaircal: float = phi.OFFSET_HEATING  # 2ª etapa calefacción fancoil/recuperador
                 ):
        self.building_id = building_id
        self.dwelling_id = dwelling_id
        self.room_id = room_id
        self.name = name
        self.groups = groups
        self.iv_source = iv_source  # Dispositivo del que leer el modo Calefacción / Refrigeración
        self.iv = self.get_iv_mode()
        self.sp_source = sp_source
        self.sp = self.get_sp()
        self.rt_source = rt_source
        self.rt = self.get_rt()
        self.rh_source = rh_source
        self.rh = self.get_rh()
        self.dp = self.calc_dp()
        self.h = self.calc_h(phi.ALTITUD)
        self.st_source = st_source
        self.st = self.get_st()
        self.af = af  # Caudal de aire asociado a la habitación cuando forma parte de zonificador
        self.aq_source = aq_source
        self.aq = self.get_aq()
        self.aqsp_source = aqsp_source
        self.aqsp = self.get_aqsp()
        self.offsetairref = offsetairref
        self.offsetaircal = offsetaircal

    def __repr__(self):
        """
        Para imprimir la información de la habitación
        Returns:
        """
        modo = "Refrigeración" if self.iv else "Calefacción"
        # sp = self.get_sp()
        # rh = self.get_rh()
        # rt = self.get_rt()
        # st = self.get_st()
        # dp = self.calc_dp()
        # h = self.h()
        room_info = f"""\nDatos de la habitación {self.name}, vivienda {self.dwelling_id}, edificio {self.building_id}
            Modo: {modo}
            Consigna: {self.sp}
            Humedad relativa: {self.rh}
            Temperatura ambiente: {self.rt}
            Estado actuador: {self.st}
            Temperatura de rocío: {self.dp}
            Entalpía: {self.calc_h}
            """
        if None not in (self.sp, self.rt) and self.sp < 50 and self.rt < 50:
            return room_info
        else:
            msg = f"\nHabitación {self.name}, vivienda {self.dwelling_id}, edificio {self.building_id} " \
                  f"tiene una consigna o una temperatura no válidas"
            return msg

    def calc_dp(self):
        """
        Calcula el punto de rocío con temp en celsius y hr en %.
        Si la temperatura o la humedad no tienen valores válidos, se devuelve None
        """
        # print(f"Calculando temperatura de rocío de {self.name}")
        # rt = self.get_rt()
        # rh = self.get_rh()
        nullvalues = ("", None, "false", 0)
        if any((self.rt in nullvalues, self.rh in nullvalues)):
            return
        t_rocio = (self.rh / 100) ** (1 / 8) * (112 + 0.9 * self.rt) + 0.1 * self.rt - 112
        return round(t_rocio, 1)

    def calc_h(self, altitud=phi.ALTITUD):
        """
        Calcula la entalpia con temp en celsius y hr en %. Por defecto se toma la altitud de Madrid
        """
        # print(f"Calculando entalpía de {self.name}")
        entalpia = None
        # rt = self.get_rt()
        # rh = self.get_rh()
        pres_total = 101325 if altitud is None else 101325 * (1 - 2.25577 * 0.00001 * altitud) ** 5.2559
        print(f"DEBUGGING {__file__} Calculando entalpia: {self.rt} / {self.rh}")
        if None in (self.rt, self.rh) or self.rh == 0.0:
            return entalpia
        pres_vap_sat = 10 ** (7.5 * self.rt / (273.159 + self.rt - 35.85) + 2.7858)  # Pa
        # print(f"presion vapor saturado: {pres_vap_sat}")
        pres_vap = pres_vap_sat * self.rh / 100  # Pa
        # print(f"presion total: {pres_total}")
        # print(f"presion vapor: {pres_vap}")
        pres_aire_seco = pres_total - pres_vap  # Pa
        # print(f"presion aire seco: {pres_aire_seco}")
        hum_especifica = 0.621954 * (pres_vap / pres_aire_seco)  # kg agua / hg aire seco
        entalpia = (1.006 + 1.86 * hum_especifica) * self.rt + 2501 * hum_especifica
        self.h = round(entalpia, 1)
        return round(entalpia, 1)

    def get_iv_mode(self):
        """
        Obtiene el modo actual de funcionamiento, calefacción refrigeración de la habitación y está asociado al modo
        iv del edificio, que puede calcularse en función del mes, desde un dispositivo o leerse de un fichero..
        Si se lee un 0 el modo será calefacción y si se lee un 1 el modo será refrigeración.
        Returns: Modo de funcionamiento Calefacción / Refrigeración de la instalación.
        Es un valor booleano asociado a la refrigeración: True = Refrigeración / False = Calefacción
        """
        modo = ("Calefacción", "Refrigeración")
        # iv_mode = get_modo_iv(self.building_id)
        iv_mode = phi.system_iv
        print(f"Modo funcionamiento habitación {self.name} del edificio {self.building_id}:")
        print(f"\t\t{modo[iv_mode]}\n")
        self.iv = iv_mode
        return self.iv

    def get_sp(self):
        """
        Obtiene el valor actual de la consigna de la habitación desde la base de datos que almacena las lecturas
        Returns: valor de la consigna actual de la habitación
        """
        # print(f"leyendo consigna de {self.name}")
        if self.sp_source is None:
            return
        setpoint = get_value(self.sp_source)
        if setpoint is None or setpoint < 0 or setpoint > 55:
            return
        # iv_mode = self.get_iv_mode()
        # Compruebo si la consigna se lee de una centralita tipo X-147
        bus_id = str(
            self.sp_source.get("bus"))  # En el JSON, el bus_id que conecta la habitación con el dispositivo
        # se introduce como un entero, pero la clave del diccionario con los datos leídos son str
        device_id = str(
            self.sp_source.get("device"))  # # OJO, es el ID del Device en la base de datos, NO EL SLAVE
        device = phi.buses.get(bus_id).get(device_id)  # Devuelve el dispositivo en el que se va a escribir
        dev_model = device.model  # Modelo de centralita Uponor

        if dev_model == "x147" and self.iv:
            setpoint += 2
            print(f"Corrigiendo consigna de {self.name} en X-147 refrigeración (se suman 2 gradC).\n"
                  f"Valor corregido {setpoint}\n")
        self.sp = setpoint
        return setpoint

    def get_rh(self):
        """
        Obtiene el valor actual de la humedad relativa de la habitación desde la base de datos que almacena las lecturas
        Returns: valor de la humedad relativa actual de la habitación
        """
        # print(f"leyendo humedad relativa de {self.name}")
        rh_read = get_value(self.rh_source)  # La HR del X148 se obtiene como tupla HB y LB y la HR es el LB
        relative_humidity = rh_read if rh_read is None else rh_read[1]
        self.rh = relative_humidity
        return relative_humidity

    def get_rt(self):
        """
        Obtiene el valor actual de la temperatura de la habitación desde la base de datos que almacena las lecturas
        Returns: valor de la temperatura actual de la habitación
        """
        # print(f"leyendo temperatura ambiente de {self.name}")
        if self.rt_source is None:
            return
        rt_read = get_value(self.rt_source)
        if rt_read is None or rt_read < 0 or rt_read > 55:
            return
        self.rt = rt_read
        return rt_read

    def get_st(self):
        """
        Obtiene el estado actual del actuador de UFHC asociado a la habitación desde la base de datos que
        almacena las lecturas
        Returns: estado actual del actuador, True: abierto / False: cerrado
        """
        # print(f"leyendo estado del actuador de {self.name}")
        actuator_status = get_value(self.st_source) if self.st_source is not None and self.st_source else None
        self.st = actuator_status
        return actuator_status

    def get_aq(self):
        """
        Obtiene el valor actual de la calidad de aire de la habitación desde la base de datos que almacena las lecturas
        Returns: valor de la calidad de aire actual de la habitación
        """
        # print(f"leyendo calidad de aire de {self.name}")
        air_quality = get_value(self.aq_source) if self.aq_source is not None and self.aq_source else None
        self.aq = air_quality
        return air_quality

    def get_aqsp(self):
        """
        Obtiene el valor de la consigna actual de calidad de aire de la habitación desde la base de datos que
        almacena las lecturas.
        Returns: valor de la consigna actual de calidad de aire de la habitación
        """
        # print(f"leyendo consigna calidad de aire de {self.name}")
        air_quality_setpoint = get_value(self.aqsp_source) if self.aqsp_source is not None and self.aqsp_source \
            else None
        self.aqsp = air_quality_setpoint
        return air_quality_setpoint

    async def update(self):
        """
        Actualiza las lecturas de la habitación
        Returns 1 cuando termina la actualización:
        """
        print(f"Iniciando actualización de la habitación {self.name}")
        self.iv = self.get_iv_mode()
        self.rt = self.get_rt()
        self.rh = self.get_rh()
        self.sp = self.get_sp()
        self.dp = self.calc_dp()
        self.h = self.calc_h()
        self.st = self.get_st()
        self.aq = self.get_aq()
        self.aqsp = self.get_aqsp()
        print(f"\nCalefacción/Refrigeración (1=Refrigeración): {self.iv}"
              f"\nTemperatura habitación: {self.rt}"
              f"\nHumedad relativa: {self.rh}"
              f"\nConsigna: {self.sp}"
              f"\nTemperatura de rocío: {self.dp}"
              f"\nEntalpía: {self.h}"
              f"\nEstado actuador: {self.st}"
              f"\nCalidad de aire: {self.aq}"
              f"\nConsigna de calidad de aire: {self.aqsp}\n")
        return 1


class RoomGroup:
    """
    Clase formada por un grupo de habitaciones
    TODO Definir en la base de datos cómo se le pasa el modo de funcionamiento Calefacción/Refrigeración
    TODO al grupo de habitaciones. Normalmente debe proceder de una modbus_source. Debe actualizarse en cada
    TODO lectura. De momento, se toma el modo IV inicial definido en init_modo_iv()
    """

    def __init__(self, id_rg: [str, None] = None, roomgroup=None):
        if roomgroup is None:
            roomgroup = []
        self.id_rg = id_rg  # Identificación del grupo
        self.roomgroup = roomgroup  # Lista de objetos del tipo Room con sus atributos de temperaturas, humedad, etc.
        self.iv = None  # Modo IV del grupo de habitaciones
        self.demand = None
        self.water_sp = None  # Consigna impulsión agua del grupo
        self.air_sp = None  # Consigna impulsión aire del grupo
        self.air_rt = None  # Temperatura ambiente del grupo
        self.air_dp = None  # Punto de rocío más alto del grupo
        self.air_h = None  # Entalpía más alta del grupo
        self.aq = 0  # Valor de calidad de aire del grupo
        self.aq_sp = phi.AIR_QUALITY_DEFAULT_SETPOINT  # Valor de consigna calidad de aire del grupo
        self.offsetref = phi.OFFSET_DEMANDA_REFRIGERACION
        self.offsetcal = phi.OFFSET_DEMANDA_CALEFACCION
        self.habbombaref = phi.TMAX_HAB_REFR
        self.habbombacal = phi.TMIN_HAB_CALEF
        self.offsetwspref = phi.OFFSET_AGUA_REFRIGERACION
        self.offsetwspcal = phi.OFFSET_AGUA_CALEFACCION
        self.offsettrocio = phi.OFFSET_AGUA_T_ROCIO

    async def get_consignas(self):
        """
        Calcula la consigna de impulsión de agua para el conjunto de habitaciones.
        Los valores de consigna, temperatura ambiente, etc. los extrae del fichero
        Returns: diccionario con 4 claves:
        - demanda: vale 0 si no hay demanda, 1 si hay demanda de refrigeración en modo refrigeración, 2 si hay demanda
        de calefacción en modo calefacción
        - water_sp: float con la consigna de la temperatura de impulsión de agua
        - air_sp: float con la consigna de la temperatura de consigna ambiente (para fancoils)
        Recoge la consigna más alta de entre las habitaciones con demanda en calefacción y la más baja en refrigeración
        -air_rt: float con el valor de la temperatura ambiente (para fancoils)
        Recoge el valor de temperatura ambiente más bajo de entre las habitaciones con demanda en modo calefacción
        y la más alta en modo refrigeración.
        - air_dp: punto de rocío más alto del grupo de habitaciones
        - air_h: entalía máxima del grupo de habitaciones
        - aq: Calidad de aire del grupo (se toma el máximo contenido en ppm de CO2
        - aq_sp: Consigna de calidad de aire del grupo (se toma el nivel mínimo de CO2 de aquellas habitaciones con
        demanda de ventilación
        """
        # print(f"\t...Calculando temperatura de impulsión para el grupo de habitaciones {self.id_rg}")
        # Obtengo el modo de funcionamiento Calefacción/Refrigeración del con el método iv() de la
        # primera habitación del grupo
        self.iv = self.iv_mode()
        cooling = self.iv
        if len(self.roomgroup) == 0:
            raise ValueError(f"No se han añadido habitaciones al grupo {self.id_rg}")
        bld = self.roomgroup[0].building_id
        t_exterior = get_temp_exterior(bld)
        # Inicializo los valores de calidad de aire del grupo
        group_aq = 0
        group_aq_sp = phi.AIR_QUALITY_DEFAULT_SETPOINT

        # Inicializo consigna temperatura de impulsion
        group_supply_water_setpoint = self.habbombaref if cooling else self.habbombacal
        group_air_temperature_setpoint = None
        group_air_temperature = None

        # Inicializamos la temperatura de rocio a la temperatura mínima de impulsion en refrigeracion
        min_t_rocio = phi.TMIN_IMPUL_REFR
        t_rocio_lim = min_t_rocio
        h_max = None  # Inicializo la entalpia del grupo
        demanda = 0
        # Se actualizan los atributos de las habitaciones del grupo según las últimas lecturas
        room_updating_tasks = [create_task(r.update())
                               for r in tuple(self.roomgroup)]

        updating_results = await gather(*room_updating_tasks)
        print(f"Resultado actualización habitaciones {updating_results}.\nDebe ser una tupla de 1's")
        for room in self.roomgroup:
            print(f"Calculando consignas del grupo {self.id_rg}. Datos habitación {room.name}")
            null_values = ["", None, 0, 0.0, "0", "0.0", "true", "false"]
            # Calidad de aire
            room_aq = room.aq if room.aq is not None else 0
            room_aq_sp = room.aqsp if room.aqsp is not None else phi.AIR_QUALITY_DEFAULT_SETPOINT
            group_aq = max(group_aq, room_aq)
            if room_aq > room_aq_sp:  # Se necesita ventilar
                group_aq_sp = min(group_aq_sp, room_aq_sp)

            # El primer valor a tomar para la temperatura ambiente y la consigna
            # del grupo de habitaciones es el de la primera habitación.
            rt = room.rt  # Temperatura ambiente del objeto Room
            sp = room.sp  # Consigna del objeto Room
            if None in [sp, rt]:
                print(f"DEBUGGING {__file__}. La consigna {sp} o la temperatura {rt} del grupo {self.roomgroup} "
                      f"son nulos")
                continue
            group_air_temperature = rt if group_air_temperature is None else group_air_temperature
            air_sp = sp + room.offsetairref if cooling else sp + room.offsetaircal
            dp = room.dp  # Temperatura de rocío del objeto Room
            h = room.h  # Entalpia del objeto Room

            group_air_temperature_setpoint = air_sp if group_air_temperature_setpoint is None \
                else group_air_temperature_setpoint

            t_rocio_hab = min_t_rocio if dp in null_values else dp
            t_rocio_lim = max(t_rocio_hab, t_rocio_lim)
            h_hab = h_max if h in null_values else h
            if h_hab is not None:
                h_max = h_hab if h_max is None else max(h_hab, h_max)
            if any([rt in null_values, sp in null_values, isinstance(rt, str), isinstance(sp, str)]):
                continue  # Ignoramos las habitaciones de las que no dispongamos lecturas de temperatura o consigna

            if cooling:  # Modo refrigeracion
                print(f"DEBUGGING {__file__}: sp: {sp} / offsetwspref {self.offsetwspref} / "
                      f"t_exterior {t_exterior} / RT_LIM_REFR {phi.RT_LIM_REFR}")
                if rt - sp > self.offsetref:  # Se necesita la temperatura de impulsion más baja
                    demanda = 1
                    t_impulsion_temp = sp - self.offsetwspref - (t_exterior - max(phi.RT_LIM_REFR, sp)) / 2
                    group_air_temperature_setpoint = min(air_sp, group_air_temperature_setpoint)
                    group_air_temperature = max(rt, group_air_temperature)
                elif rt - sp > 0:  # Se puede impulsar agua a una temperatura algo más alta
                    demanda = 1
                    t_impulsion_temp = sp - self.offsetwspref
                    group_air_temperature_setpoint = min(air_sp, group_air_temperature_setpoint)
                    group_air_temperature = max(rt, group_air_temperature)
                else:  # No hay demanda
                    t_impulsion_temp = sp - self.offsetwspref / 2

                # print(f"Temp impulsion refrigeracion provisional {habitacion.name}: {round(t_impulsion_temp, 1)}")
                # Actualizo el cálculo de la consigna en refrigeración
                group_supply_water_setpoint = min(group_supply_water_setpoint, t_impulsion_temp)
                # Aplico el límite por t_rocio
                group_supply_water_setpoint = max(group_supply_water_setpoint, t_rocio_lim + self.offsettrocio)
            else:  # Modo calefacción
                if sp - rt > self.offsetcal:  # Se necesita mayor temperatura de impulsion
                    demanda = 2
                    t_impulsion_temp = sp + self.offsetwspcal + (min(sp, phi.RT_LIM_CALEF) - t_exterior) / 2
                    group_air_temperature_setpoint = max(air_sp, group_air_temperature_setpoint)
                    group_air_temperature = min(rt, group_air_temperature)
                elif sp - rt > 0:  # Se puede impulsar agua a menor temperatura
                    demanda = 2
                    t_impulsion_temp = sp + self.offsetwspcal
                    group_air_temperature_setpoint = max(air_sp, group_air_temperature_setpoint)
                    group_air_temperature = min(rt, group_air_temperature)
                else:  # No hay demanda
                    t_impulsion_temp = sp + self.offsetwspcal / 2
                # print(f"Temp impulsion calefaccion provisional {room.name}: {round(t_impulsion_temp, 1)}")
                # print(f"Temp aire calefaccion provisional {room.name}: {round(group_air_temperature, 1)}")
                # print(f"Consigna Temp aire calefaccion provisional {room.name}: " + \
                #       f"{round(group_air_temperature_setpoint, 1)}")
                # Actualizo el cálculo de la consigna
                group_supply_water_setpoint = max(t_impulsion_temp, group_supply_water_setpoint)

        if cooling:  # Aplico los límites establecidos a las temperaturas de impulsión
            group_supply_water_setpoint = round(max(phi.TMIN_IMPUL_REFR, group_supply_water_setpoint), 1)
        else:
            group_supply_water_setpoint = round(min(phi.TMAX_IMPUL_CALEF, group_supply_water_setpoint), 1)

        self.demand = demanda
        self.water_sp = group_supply_water_setpoint
        self.air_sp = group_air_temperature_setpoint
        self.air_rt = group_air_temperature
        self.air_dp = t_rocio_lim
        self.air_h = h_max
        self.aq = group_aq
        self.aq_sp = group_aq_sp
        collect()
        print(repr(self))
        return 1

    def iv_mode(self, new_iv_mode: [int, None] = None):
        """
        Procesa el modo de funcionamiento Calefacción (new_iv_mode = 0) / Refrigeración (iv_mode = 1) grupo de
        habitaciones.
        El modo IV del grupo de habitaciones se obtiene a partir del modo IV de las habitaciones que lo componen.
        TODO: Verificar el funcionamiento del modo IV escrito
        Las habitaciones tomarán su modo de funcionamiento de 3 formas posibles:
        - La web (archivo intercambiador en /home/pi/var/tmp/reg/<dev>/iv
        - Algún dispositivo Modbus (iv_source)
        - TODO Calcular modo IV de manera automática
        El modo IV del grupo se selecciona tomando el modo IV de la mayoría de las habitaciones que lo componen.
        Si no se lee el modo IV de ninguna habitación, se toma el modo IV que devuelve init_modo_iv()
        Param:
            new_iv_mode:
                Si None, se devuelve el modo actual
                Si 1, se activa el modo refrigeración del grupo de habitaciones
                Si 0, se activa el modo calefacción del grupo de habitaciones
        Returns:
            Modo iv o None si falta algún dato
        """
        q_hab_cooling = 0  # Contador de habitaciones en modo Cooling
        q_hab_heating = 0  # Contador de habitaciones en modo Heating
        n_hab = len(self.roomgroup)  # nº de habitaciones del grupo
        for room in self.roomgroup:
            room_modo_iv = room.iv  # Obtengo el modo IV de la habitación
            if room_modo_iv in ['1', 1, True, 'True']:
                q_hab_cooling += 1
            elif room_modo_iv in ['0', 0, False, 'False']:
                q_hab_heating += 1

        modo_iv = phi.COOLING if q_hab_cooling > q_hab_heating else phi.HEATING

        if new_iv_mode in [0, 1]:  # Se fuerza el modo IV. TODO Comprobar si esta opción tiene sentido.
            self.iv = new_iv_mode
        elif q_hab_cooling + q_hab_heating == 0:  # No se ha leído el modo IV de ninguna habitación
            # self.iv = get_modo_iv()
            self.iv = phi.system_iv
        else:
            self.iv = modo_iv

        return self.iv

    def __repr__(self):
        # self.get_consignas()
        demanda_str = ("No hay demanda", "Demanda de Refrigeración", "Demanda de Calefacción")

        results = f"""Datos calculados para el grupo {self.id_rg}:
                        Demanda: {demanda_str[self.demand]}
                        Temperatura impulsión de agua: {self.water_sp}
                        Temperatura ambiente grupo: {self.air_rt}
                        Temperatura consigna aire grupo: {self.air_sp}
                        Punto de rocío grupo: {self.air_dp}
                        Entalpia grupo: {self.air_h}
                        Nivel CO2 grupo: {self.aq}
                        Consigna nivel CO2 grupo: {self.aq_sp}"""
        return results

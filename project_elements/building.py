#!/usr/bin/env python3
"""
Definición de las clases que definen los objetos del edificio: Edificio,
Viviendas, Habitaciones, Grupos de habitaciones...
"""
from gc import collect
import phoenix_constants as cte
import phoenix_config as cfg


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
                 aqsp_source: [dict, None] = None
                 ):
        self.building_id = building_id
        self.dwelling_id = dwelling_id
        self.room_id = room_id
        self.name = name
        self.groups = groups
        self.iv_source = iv_source  # Dispositivo del que leer el modo Calefacción / Refrigeración
        self.sp_source = sp_source
        self.rt_source = rt_source
        self.rh_source = rh_source
        self.st_source = st_source
        self.af = af  # Caudal de aire asociado a la habitación cuando forma parte de zonificador
        self.aq_source = aq_source
        self.aqsp_source = aqsp_source

    def __repr__(self):
        """
        Para imprimir la información de la habitación
        Returns:
        """
        sp = self.sp()
        rh = self.rh()
        rt = self.rt()
        st = self.st()
        tr = self.tr()
        h = self.h()
        room_info = f"""Datos de la habitación {self.name}, vivienda {self.dwelling_id}, edificio {self.building_id}
            Consigna: {sp}
            Humedad relativa: {rh}
            Temperatura ambiente: {rt}
            Estado actuador: {st}
            Temperatura de rocío: {tr}
            Entalpía: {h}
            """
        if sp < 50:
            return room_info

    def tr(self):
        """
        Calcula el punto de rocío con temp en celsius y hr en %.
        Si la temperatura o la humedad no tienen valores válidos, se devuelve None
        """
        # print(f"Calculando temperatura de rocío de {self.name}")
        rt = self.rt()
        rh = self.rh()
        nullvalues = ("", None, "false", 0)
        if any((rt in nullvalues, rh in nullvalues)):
            return
        t_rocio = (rh / 100) ** (1 / 8) * (112 + 0.9 * rt) + 0.1 * rt - 112
        return round(t_rocio, 1)

    def h(self, altitud=cte.ALTITUD):
        """
        Calcula la entalpia con temp en celsius y hr en %. Por defecto se toma la altitud de Madrid
        """
        # print(f"Calculando entalpía de {self.name}")
        rt = self.rt()
        rh = self.rh()
        pres_total = 101325 if altitud is None else 101325 * (1 - 2.25577 * 0.00001 * altitud) ** 5.2559
        nullvalues = ("", None, "false")
        if any((rt in nullvalues, rh in nullvalues)):
            return
        pres_vap_sat = 10 ** (7.5 * rt / (273.159 + rt - 35.85) + 2.7858)  # Pa
        # print(f"presion vapor saturado: {pres_vap_sat}")
        pres_vap = pres_vap_sat * rh / 100  # Pa
        # print(f"presion total: {pres_total}")
        # print(f"presion vapor: {pres_vap}")
        pres_aire_seco = pres_total - pres_vap  # Pa
        # print(f"presion aire seco: {pres_aire_seco}")
        hum_especifica = 0.621954 * (pres_vap / pres_aire_seco)  # kg agua / hg aire seco
        entalpia = (1.006 + 1.86 * hum_especifica) * rt + 2501 * hum_especifica
        return round(entalpia, 1)

    def iv(self):
        """
        Obtiene el modo actual de funcionamiento, calefacción refrigeración de la habitación desde la base de
        datos que almacena las lecturas
        Returns: Modo de funcionamiento Calefacción / Refrigeración de la instalación.
        Es un valor booleano asociado a la refrigeración: True = Refrigeración / False = Calefacción
        Si no se dispone del dato, se selecciona automáticamente:
        Junio-Septiembre = Refrigeración
        Resto = Calefacción
        """
        if self.iv_source is None or not self.iv_source:
            mes = cfg.datetime.now().month
            cooling = True if 5 < mes < 10 else False  # Refrigeración entre junio y septiembre
            return cooling
        else:
            cooling = cfg.get_reading(self.iv_source)  # TODO Definir valores para modo Calefacción / Refrigeración
        return cooling

    def sp(self):
        """
        Obtiene el valor actual de la consigna de la habitación desde la base de datos que almacena las lecturas
        Returns: valor de la consigna actual de la habitación
        """
        # print(f"leyendo consigna de {self.name}")
        setpoint = cfg.get_reading(self.sp_source) if self.sp_source is not None else None
        return setpoint

    def rh(self):
        """
        Obtiene el valor actual de la humedad relativa de la habitación desde la base de datos que almacena las lecturas
        Returns: valor de la humedad relativa actual de la habitación
        """
        # print(f"leyendo humedad relativa de {self.name}")
        relative_humidity = cfg.get_reading(self.rh_source) if self.rh_source is not None else None
        return relative_humidity

    def rt(self):
        """
        Obtiene el valor actual de la temperatura de la habitación desde la base de datos que almacena las lecturas
        Returns: valor de la temperatura actual de la habitación
        """
        # print(f"leyendo temperatura ambiente de {self.name}")
        room_temperature = cfg.get_reading(self.rt_source) if self.rt_source is not None else None
        return room_temperature

    def st(self):
        """
        Obtiene el estado actual del actuador de UFHC asociado a la habitación desde la base de datos que
        almacena las lecturas
        Returns: estado actual del actuador, True: abierto / False: cerrado
        """
        actuator_status = cfg.get_reading(self.st_source) if self.st_source is not None else None
        return actuator_status

    def aq(self):
        """
        Obtiene el valor actual de la calidad de aire de la habitación desde la base de datos que almacena las lecturas
        Returns: valor de la calidad de aire actual de la habitación
        """
        air_quality = cfg.get_reading(self.aq_source) if self.aq_source is not None else None
        return air_quality

    def aqsp(self):
        """
        Obtiene el valor de la consigna actual de calidad de aire de la habitación desde la base de datos que
        almacena las lecturas.
        Returns: valor de la consigna actual de calidad de aire de la habitación
        """
        air_quality_setpoint = cfg.get_reading(self.aqsp_source) if self.aqsp_source is not None else None
        return air_quality_setpoint

    def update(self):
        """
        Actualiza las lecturas de la habitación
        Returns:
        """
        print(f"Iniciando actualización de la habitación {self.name}")
        self.iv()
        self.rt()
        self.rh()
        self.sp()
        self.tr()
        self.h()
        self.st()
        self.aq()
        self.aqsp()


class RoomGroup:
    """
    Clase formada por un grupo de habitaciones
    TODO Definir en la base de datos cómo se le pasa el modo de funcionamiento Calefacción/Refrigeración
    TODO al grupo de habitaciones. Normalmente debe proceder de una modbus_source. Debe actualizarse en cada
    TODO lectura. De momento, se toma el modo IV inicial definido en cfg.init_modo_iv()
    """

    def __init__(self, id_rg: [str, None] = None, roomgroup=None):
        if roomgroup is None:
            roomgroup = []
        self.id_rg = id_rg  # Identificación del grupo
        self.roomgroup = roomgroup  # Lista de objetos del tipo Room con sus atributos de temperaturas, humedad, etc.
        self.iv = cfg.init_modo_iv()  # TODO, resolver como pasar modo iv al grupo.
        self.demanda = None
        self.water_sp = None
        self.air_sp = None
        self.air_rt = None
        self.offsetref = cte.OFFSET_DEMANDA_REFRIGERACION
        self.offsetcal = cte.OFFSET_DEMANDA_CALEFACCION
        self.habbombaref = cte.TMAX_HAB_REFR
        self.habbombacal = cte.TMIN_HAB_CALEF
        self.offsetwspref = cte.OFFSET_AGUA_REFRIGERACION
        self.offsetwspcal = cte.OFFSET_AGUA_CALEFACCION
        self.offsettrocio = cte.OFFSET_AGUA_T_ROCIO

    def get_consignas(self):
        """
        Calcula la consigna de impulsión de agua para el conjunto de habitaciones.
        Returns: diccionario con 4 claves:
        - demanda: vale 0 si no hay demanda, 1 si hay demanda de refrigeración en modo refrigeración, 2 si hay demanda
        de calefacción en modo calefacción
        - agua_sp: float con la consigna de la temperatura de impulsión de agua
        - aire_sp: float con la consigna de la temperatura de consigna ambiente (para fancoils)
        Recoge la consigna más alta de entre las habitaciones con demanda en calefacción y la más baja en refrigeración
        -aire_rt: float con el valor de la temperatura ambiente (para fancoils)
        Recoge el valor de temperatura ambiente más bajo de entre las habitaciones con demanda en modo calefacción
        y la más alta en modo refrigeración.
        """
        # print(f"\t...Calculando temperatura de impulsión para el grupo de habitaciones {self.id_rg}")
        # Obtengo el modo de funcionamiento Calefacción/Refrigeración del con el método iv() de la
        # primera habitación del grupo
        cooling = self.iv
        # Obtengo de la primera habitación de roomgroup el edificio del que leer la temperatura exterior
        if len(self.roomgroup) == 0:
            raise ValueError(f"No se han añadido habitaciones al grupo {self.id_rg}")
        bld = self.roomgroup[0].building_id
        t_exterior = cfg.get_temp_exterior(bld)
        # Inicializo consigna temperatura de impulsion
        group_supply_water_setpoint = self.habbombaref if cooling else self.habbombacal
        group_air_temperature_setpoint = None
        group_air_temperature = None

        # Iniciamos la temperatura de rocio a la temperatura mínima de impulsion en refrigeracion
        min_t_rocio = cte.TMIN_IMPUL_REFR
        t_rocio_lim = min_t_rocio
        demanda = 0
        for room in self.roomgroup:
            # room.update()
            null_values = ["", None, 0, 0.0, "0", "0.0", "true", "false"]

            # El primer valor a tomar para la temperatura ambiente y la consigna
            # del grupo de habitaciones es el de la primera habitación.
            rt = room.rt()  # Temperatura ambiente del objeto Room
            group_air_temperature = rt if group_air_temperature is None else group_air_temperature
            sp = room.sp()  # Consigna del objeto Room
            tr = room.tr()
            group_air_temperature_setpoint = sp if group_air_temperature_setpoint is None \
                else group_air_temperature_setpoint

            t_rocio_hab = min_t_rocio if tr in null_values else tr
            t_rocio_lim = max(t_rocio_hab, t_rocio_lim)
            if any([rt in null_values, sp in null_values, isinstance(rt, str), isinstance(sp, str)]):
                continue  # Ignoramos las habitaciones de las que no dispongamos lecturas de temperatura o consigna

            if cooling:  # Modo refrigeracion
                if rt - sp > self.offsetref:  # Se necesita la temperatura de impulsion más baja
                    demanda = 1
                    t_impulsion_temp = sp - self.offsetwspref - (t_exterior -
                                                                 max(cte.RT_LIM_REFR, sp)) / 2
                    group_air_temperature_setpoint = min(sp, group_air_temperature_setpoint)
                    group_air_temperature = max(rt, group_air_temperature)
                elif rt - sp > 0:  # Se puede impulsar agua a una temperatura algo más alta
                    demanda = 1
                    t_impulsion_temp = sp - self.offsetwspref
                    group_air_temperature_setpoint = min(sp, group_air_temperature_setpoint)
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
                    t_impulsion_temp = sp + self.offsetwspcal + (min(sp, cte.RT_LIM_CALEF) - t_exterior) / 2
                    group_air_temperature_setpoint = max(sp, group_air_temperature_setpoint)
                    group_air_temperature = min(rt, group_air_temperature)
                elif sp - rt > 0:  # Se puede impulsar agua a menor temperatura
                    demanda = 2
                    t_impulsion_temp = sp + self.offsetwspcal
                    group_air_temperature_setpoint = max(sp, group_air_temperature_setpoint)
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
            group_supply_water_setpoint = round(max(cte.TMIN_IMPUL_REFR, group_supply_water_setpoint), 1)
        else:
            group_supply_water_setpoint = round(min(cte.TMAX_IMPUL_CALEF, group_supply_water_setpoint), 1)

        self.demanda = demanda
        self.water_sp = group_supply_water_setpoint
        self.air_sp = group_air_temperature_setpoint
        self.air_rt = group_air_temperature
        collect()
        return 1

    def __repr__(self):
        self.get_consignas()
        demanda_str = ("No hay demanda", "Demanda de Refrigeración", "Demanda de Calefacción")

        results = f"""Datos calculados para el grupo {self.id_rg}:
                        Demanda: {demanda_str[self.demanda]}
                        Temperatura impulsión de agua: {self.water_sp}
                        Temperatura ambiente grupo: {self.air_rt}
                        Temperatura consigna aire grupo: {self.air_sp}"""
        return results

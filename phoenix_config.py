#!/usr/bin/env python3
import os
import json
import sys
import phoenix_constants as cte
from project_elements.building import Room, RoomGroup
from devices.devices import ModbusRegisterMap, RoomSensor, Generator, Fancoil, Split, HeatRecoveryUnit, AirZoneManager
from gc import collect
from datetime import datetime

# DICCIONARIO CON LAS CLASES DEL SISTEMA
SYSTEM_CLASSES = {
    "sensor": RoomSensor,
    "generator": Generator,
    "fancoil": Fancoil,
    "split": Split,
    "heatrecoveryunit": HeatRecoveryUnit,
    "airzonemanager": AirZoneManager
}


def get_boardsn() -> str:
    """
    Obtiene el número de serie de la centralita
    :return: Cadena con el número de serie de la ESP32
    """
    command = "cat /proc/cpuinfo | grep Serial"
    rpi3sn = os.popen(command).read().split(':')[1].strip()
    return rpi3sn


# INICIALIZACIÓN DE VARIABLES GLOBALES
boardsn = get_boardsn()


def load_project() -> [dict, None]:
    """
    Crea un diccionario con los datos del proyecto a partir del JSON de configuración.
    Returns: Diccionario con los datos del proyecto
    """
    try:
        with open(cte.CONFIG_FILE, "r") as cfg:
            project = json.load(cfg)
            prj_cfg = project.get("project")
            return prj_cfg
    except FileNotFoundError:
        print(f"\nERROR - No se ha encontrado el fichero de configuración del proyecto {cte.CONFIG_FILE}")
        return


# Cargo el proyecto y compruebo si existe el JSON de configuración y si el proyecto tiene definidos edificios
prj = load_project()
if prj is None:
    print("\nERROR cargando la configuración del proyecto.\n...Abandonando el programa")
    sys.exit()
# print(prj)
datadb = {}  # Variable para almacenar las lecturas de registros ModBus y asociarlas con las Rooms

buildings = prj.get("buildings")
if buildings is None:
    print("ERROR (phoenix-config: load_buildings) - No se ha definido ningún edificio en el fichero de " 
          "configuración del proyecto,\n\n\t...Abandonando el programa.")
    sys.exit()


def get_reading(value_source: [dict, None]) -> [int, float, bool]:
    """
    Extrae el valor de un determinado registro ModBus almacenado en "datadb"
    Params value_source: diccionario que indica el bus, el esclavo, el tipo de registro y el registro a leer
    Returns: valor almacenado en la base de datos (diccionario) datadb
    None si el valor que se quiere leer no existe en la base de datos
    """
    if value_source is None:
        return
    bus_id = str(value_source.get("bus"))  # En el JSON, el bus_id que conecta la habitación con el dispositivo
    # se introduce como un entero, pero la clave del diccionario con los datos leídos son str
    device_id = value_source.get("device")  # El slave (esclavo) se convirtió a str con anterioridad
    datatype = value_source.get("datatype")
    adr = str(value_source.get("adr"))  # Sucede lo mismo que con el bus_id
    if any([bus_id is None, device_id is None, datatype is None, adr is None]):
        print(f"ERROR - No se ha podido leer el valor del {datatype} {adr} en esclavo {device_id}/bus{bus_id}")
        return
    if datadb is not None:
        buses_data = datadb.get("buses")
        if buses_data is not None:
            bus = buses_data.get(bus_id)
            if bus is not None:
                # Busco bus_id del dispositivo con el esclavo slave_id
                device_data = None
                for id_device, device in bus.items():
                    if device.get("slave") == device_id:
                        device_data = device
                        break
                if device_data is not None:
                    regs = device_data["data"].get(datatype)
                    if regs is not None:
                        value = regs.get(adr)
                        return value


def init_modo_iv() -> bool:
    """
    Inicializa el modo de funcionamiento general en función de la época del año.
    IMPORTANTE que el controlador esté en hora
    Returns: True entre junio y septiembre, False el resto de los meses
    """
    mes = datetime.now().month
    cooling = True if 5 < mes < 10 else False
    return cooling


def get_default_t_exterior() -> float:
    """
    Devuelve el valor por defecto de temperatura exterior del proyecto en función del mes en curso
    Returns: temperatura exterior por defecto
    """
    mes = datetime.now().month
    t_ext = cte.DEFAULT_TEMP_EXTERIOR_VERANO if 5 < mes < 10 else cte.DEFAULT_TEMP_EXTERIOR_INVIERNO
    return t_ext


def get_temp_exterior(bld: str = "1") -> [float, None]:
    """
        Obtiene el valor actual de la temperatura exterior del edificio según el origen definido en la
        clave 'o_data.te_source' del edificio.
        Cuando dentro de te_source existe la clave mbdev, la temperatura exterior se lee de la base de
        datos que almacena las lecturas de los dispositivos ModBus
        Returns: valor de la temperatura exterior.
        Si no se conoce, se consideran cte.DEFAULT_TEMP_EXTERIOR_VERANO (35 ºC) en modo refrigeración y
        cte.DEFAULT_TEMP_EXTERIOR_INVIERNO (3 ºC) en modo calefacción
        """
    bld_data = prj.get("buildings")[bld]
    if bld_data is None:
        print(f"ERROR (get_temp_exterior) - No se ha definido edificio {bld}")
        sys.exit()
    o_data = bld_data.get("o_data")
    if o_data is None:
        msg = f"""WARNING (get_temp_exterior) - No se indicado origen de lectura de valores exteriores en el 
edificio {bld}. Se toman valores por defecto"""
        print(msg)
        return get_default_t_exterior()
    te_source = o_data.get("te_source")
    if te_source is None:
        msg = f"""WARNING (get_temp_exterior) - No se indicado origen de lectura de temperatura exterior en el 
        edificio {bld}. Se toman valores por defecto"""
        print(msg)
        return get_default_t_exterior()
    t_ext_from_mbdev_source = te_source.get("mbdev")
    if t_ext_from_mbdev_source is None:
        print("La temperatura exterior debe obtenerse por un método que aún no está definido")
        return get_default_t_exterior()
    else:
        t_ext_from_mbdev = get_reading(t_ext_from_mbdev_source)
        return t_ext_from_mbdev


def load_roomgroups():
    """
    Crea las instancias de las clases que forman parte del edificio: Rooms y RoomGroups.
    Dichas clases se almacenan en el módulo "building.py"
    Se considera que tanto cada vivienda como cada edificio son RoomGroups formados por distintas habitaciones
    Returns: Diccionario con todos los grupos de habitaciones siendo la clave el "id" del grupo de habitaciones y
    el valor una lista formada por los objetos RoomGroup del edificio, siendo uno de los atributos de dichos objetos
    una lista de los objetos Room que componen el grupo.
    """
    roomgroups = {}

    hay_habitaciones = False  # Si no hay ninguna habitación definida en el proyecto se genera un aviso y se
    # para el programa

    for bldid, bld in buildings.items():
        dwellings = bld.get("dwellings")
        if dwellings is None:
            print(f"WARNING (phoenix-config: load_buildings) - El edificio {bld.get('name')} no tiene "
                  "definidas viviendas.")
            continue
        for dwellid, dwell in dwellings.items():
            rooms = dwell.get("rooms")
            if rooms is None:
                print(f"WARNING (phoenix-config: load_buildings) - La vivienda {dwell.get('name')} del edificio "
                      f"{bld.get('name')} no tiene definidas habitaciones")
                continue
            hay_habitaciones = True
            for roomid, room in rooms.items():
                # Se instancia cada habitación.
                groups = room.get("groups")
                new_room = Room(
                    building_id=bldid,
                    dwelling_id=dwellid,
                    room_id=roomid,
                    name=room.get("name"),
                    sp_source=room.get("sp_source"),
                    rh_source=room.get("rh_source"),
                    rt_source=room.get("rt_source"),
                    st_source=room.get("st_source"),
                    af=room.get("af"),
                    aq_source=room.get("aq_source"),
                    aqsp_source=room.get("aqsp_source")
                )
                for idx, group in enumerate(groups):
                    # print(f"(load_roomgroups) grupo {idx} con 'id': {group}")
                    # Compruebo si existe el grupo de habitaciones
                    grp = roomgroups.get(str(group))
                    if grp is None:
                        # print(f"No existia el grupo {group}. Lo creo")
                        # No existía el grupo, creo la clave en el diccionario all_rooms y el
                        # objeto RoomGroup
                        roomgroups[str(group)] = RoomGroup(id_rg=str(group))
                    # Se añade la habitación a la lista de habitaciones del RoomGroup.
                    roomgroups[str(group)].roomgroup.append(new_room)
                    # print(f"Creando grupos de habitaciones\nGrupo: {str(group)}\nHabitacion:{new_room.name}", )

    if not hay_habitaciones:
        print("ERROR (phoenix-config: load_buildings) - No se ha definido ninguna habitación en todo el "
              "edificio en el fichero de configuración")
        sys.exit()
    # for k, v in roomgroups.items():
    #     print(f"Grupo {k}: {[x.name for x in v.roomgroup]}")
    collect()
    return roomgroups


all_rooms = load_roomgroups()  # Diccionario con todos los grupos de habitaciones. Clave principal es id del grupo


# print(all_rooms)

def load_buses():
    """
    Genera un diccionario con los dispositivos ModBus físicos del sistema.
    Los dispositivos deben existir como clase en el paquete "devices" y se importarán al proyecto
    las clases que formen parte del mismo.
    Los dispositivos están definidos bajo los identificadores de cada bus.
    Params:
    project: diccionario de configuración del sistema
    Returns: diccionario con el "id" de los buses como clave y como valor otro diccionario con el "id"
    del dispositivo como clave y el objeto del dispositivo físico como valor.
    """
    prj_buses = prj.get("buses")
    if prj_buses is None:
        print("ERROR (load_devices) - No se han definido los buses de comunicaciones del proyecto")
        print("ERROR (load_devices) - ... Saliendo del programa")
        sys.exit()
    devices = {}
    for bus in prj_buses:
        # Extraigo los dispositivos del bus
        bus_devices = prj_buses[bus].get("devices")
        bus_port = prj_buses[bus].get("port")
        if bus_devices is None:
            msg = f"WARNING (load_devices) - No hay dispositivos asociados al bus {bus}"
            print(msg)
            continue
        devices[bus] = {}
        for device in bus_devices:
            dev_info = bus_devices[device]
            name = dev_info.get("name")
            cls = dev_info.get("class")
            dev_parity = cte.PARITY.get(dev_info.get("parity"))
            # print(f"(phoenix-config) - Paridad del dispositivo: {dev_parity}")
            if cls is None:
                msg = f"""WARNING (load_devices) - El dispositivo {name} no tiene definida su Clase Python  
                en el fichero de configuración"""
                print(msg)
                continue
            # Se instancia el dispositivo
            mbdevice = SYSTEM_CLASSES.get(cls)(
                name=name,
                groups=dev_info.get("groups"),
                brand=dev_info.get("brand"),
                model=dev_info.get("model")
            )
            # Cargando parámetros de comunicación del dispositivo
            mbdevice.port = bus_port
            mbdevice.slave = dev_info.get("slave")
            mbdevice.baudrate = dev_info.get("baudrate")
            mbdevice.databits = dev_info.get("databits")
            mbdevice.parity = dev_parity  # Obtenida desde el diccionario PARITY para ESP32
            mbdevice.dev_stopbits = dev_info.get("stopbits")

            devices[bus][device] = mbdevice
            collect()

    if not devices:
        msg = """WARNING (load_devices) - No se ha definido ningún dispositivo en ningún bus del proyecto.
        ... Abandonando el programa"""
        print(msg)
        sys.exit()

    return devices


buses = load_buses()


def config_devices():
    """
    Módulo para terminar de configurar los Objetos-Dispositivos del proyecto según su clase.
    Actualiza el diccionario buses
    Returns: diccionario buses con los objetos actualizados según su clase
    """
    # Buscamos todos los tipos de dispositivo existentes bajo la clave 'class' en cada 'devices' de cada 'bus'
    # device_dbs = set()  # SET con los Nombres de los ficheros JSON que contienen las bases de datos de cada tipo
    # de dispositivo
    devtypes = {}  # Lista de diccionarios con los objetos del proyecto según su tipo, generator, fancoil, etc. y
    # su brand_model (marca_modelo), me_ecodan, uponor_x148...
    for bus in buses:
        bus_devices = buses.get(bus)
        if bus_devices is None:
            continue
        # Set con los tipos de dispositivo de proyecto, marca y modelo: dispositivo_marca_modelo
        device_dbs = [
            f"{bus_devices[device].__class__.__name__}_{bus_devices[device].brand}_{bus_devices[device].model}"
            for device in bus_devices if
            bus_devices[device].brand is not None and bus_devices[device].model is not None and bus_devices[
                device].__class__.__name__ is not None]
        device_dbs = set(device_dbs)
        # Se carga el diccionario con la información POR TIPO de los dispositivos del proyecto
        collect()
        for typedb in device_dbs:
            devtype, brand, model = typedb.split("_")
            devtypefilename = cte.PRJ_DEVICES_DB.get(devtype)
            if devtypefilename is not None:
                dev_info = {}
                dev_id = f"{brand}_{model}"
                dev_info[typedb] = {}
                with open(devtypefilename, "r") as f:
                    cls_info = json.load(f)
                    obj, obj_info = tuple(cls_info.items())[0]  # La clave principal del diccionario es el tipo de
                    # Dispositivo. Tengo que coger los datos del dispositivo concreto dentro de los valores de
                    # esa clave principal
                    devtypes[typedb] = obj_info.get(dev_id)  # Diccionario para, por ejemplo, un generador tipo
                    # ecodan: Generator_me_ecodan
        # Ahora se completa la definición de los objetos del proyecto: Generadores, Fancoils, etc.
        null_values = (None, "")
        for device in bus_devices:
            dev_to_config = bus_devices[device]
            dev_data_key = f"{dev_to_config.__class__.__name__}_{dev_to_config.brand}_{dev_to_config.model}"
            # Obtengo los atributos de la clase de objeto
            attrs = tuple(dev_to_config.__dict__.keys())
            # print(f"Atributos del Dispositivo:{attrs}")
            # Actualizo todos los atributos con valor None o ''
            for attr in attrs:
                attr_val = dev_to_config.__dict__.__getitem__(attr)
                # print(f"Valor actual de {attr}: {attr_val}")
                if attr_val in null_values:
                    # Hay que actualizar el atributo porque está vacío
                    new_val = devtypes[dev_data_key].get(attr)
                    # print(f"Actualizando atributo {attr} con el valor {new_val}")
                    setattr(dev_to_config, attr, new_val)
            collect()
            # print(f"Configurando dispositivo:\n{dev_to_config.__dict__}")
    return 1


dev_config = config_devices()


def load_regmapfiles() -> tuple:
    """
    Crea los mapas de registros modbus de los dispositivos del proyecto y completa los atributos qregsmax (máximo
    número de registros que se pueden leer en una operación ModBus) y write_operations (operaciones admitidas
    de escritura ModBus) de los dispositivos.
    Returns:
         Tupla de objetos ModbusRegisterMap con los mapas de registros de los dispositivos

         Los mapas de registros se importan de unos ficheros JSON almacenados en el Paquete "devices".
    """
    # Buscamos todos los mapas de registros existentes bajo la clave 'devices' de cada 'bus'
    regmapfilenames = set()  # SET con los Nombres de los ficheros JSON que contienen los mapas de registros
    regmaps = []  # Lista de diccionarios con los mapas de registros
    for bus in buses:
        bus_devices = buses.get(bus)
        if bus_devices is None:
            continue
        for device in bus_devices:
            brand = bus_devices[device].brand
            model = bus_devices[device].model
            if brand is None or model is None:
                continue
            devregmapfilename = f"./devices/{brand}_{model}.json"  # Debe haber un fichero brand_model.json
            # por cada dispositivo
            if devregmapfilename not in regmapfilenames:
                regmapfilenames.add(devregmapfilename)
                # Se crea el objeto ModbusRegisterMap
                new_map = ModbusRegisterMap(f"{brand}_{model}")
                try:
                    with open(devregmapfilename, "r") as f:
                        rmap = json.load(f)
                        new_map.rmap = rmap.get(f"{brand}_{model}")
                        regmaps.append(new_map)
                        # Actualizo los valores de los atributos 'qregsmax' y 'write_operations' del dispositivo
                        qregsmax = rmap.get("qregsmax")
                        write_operations = rmap.get("wop")
                        bus_devices[device].qregsmax = qregsmax
                        bus_devices[device].write_operations = write_operations
                except Exception as e:
                    print(f"\n{e}\nERROR (load_regmapfiles) - Mapa de registros {devregmapfilename} no encontrado.")
            collect()
    return tuple(regmaps)


mbregmaps = load_regmapfiles()  # Tupla de objetos tipo mapa de registros modbus ModbusRegisterMap. La clave
# principal de cada diccionario permite identificar cada dispositivo por marca y modelo

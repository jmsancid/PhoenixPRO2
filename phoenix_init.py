#!/usr/bin/env python3
import json
import sys
import pickle
from datetime import datetime
from gc import \
    collect
from phoenix_config import *
from phoenix_constants import *
from project_elements.building import Room, RoomGroup, init_modo_iv, get_modo_iv
from devices.devices import SYSTEM_CLASSES


init_time = datetime.now()
print(f"Hora inicio: {str(init_time)}")

system_iv = init_modo_iv()  # Inicializamos el modo de funcionamiento frío_calor


# system_classes = list(SYSTEM_CLASSES.values())  # Clases de dispositivos del sistema
def create_device_files(device) -> int:
    """
    Se crea una carpeta (si no existe) en el directorio phoenix_constants.EXCHANGE_FOLDER (/home/pi/var/tmp/reg/)
    con el nombre 'slave, y se crean, si no existen, los archivos de intercambio correspondientes según
    aparecen en phoenix_constants.'dev_class'_FILES, que son tuplas con los nombres de los archivos a crear.
    Params:
        device: dispositivo ModBus
    Returns:
        0 - Si no se pueden crear los archivos
        1 - Si se pueden crear los archivos
    """
    bus_id = device.bus_id
    slave = str(device.slave)
    dev_class = device.__class__.__name__

    file_names = EXCHANGE_R_FILES.get(dev_class)
    if file_names is None:
        return 0
    # Compruebo si existe el directorio de intercambio de registros:
    reg_folder_exists = os.path.isdir(EXCHANGE_FOLDER)
    if not reg_folder_exists:
        try:
            os.mkdir(EXCHANGE_FOLDER)
        except OSError:
            print(f"ERROR Creando el directorio de intercambio con la web: {EXCHANGE_FOLDER}")
        else:
            print(f"\n\n\tDirectorio de intercambio con la web {EXCHANGE_R_FILES}  -  CREADO\n")
    else:
        print(f"\n\tEl fichero de intercambio, {EXCHANGE_FOLDER}, ya existe.")
    bus_folder_name = EXCHANGE_FOLDER + r"/" + bus_id
    bus_folder_exists = os.path.isdir(bus_folder_name)
    if not bus_folder_exists:
        try:
            os.mkdir(bus_folder_name)
        except OSError:
            print(f"\n\tERROR Creando el directorio de intercambio con la web: {bus_folder_name} para el "
                  f"bus {bus_id}\n")
            return 0
        else:
            print(f"\n\t\t...directorio para bus {bus_id} en {bus_folder_name}  -  CREADO")
    sl_folder_name = bus_folder_name + r"/" + slave
    print(f"\t\tProcesando carpeta {sl_folder_name}")
    sl_folder_exists = os.path.isdir(sl_folder_name)
    if not sl_folder_exists:
        try:
            os.mkdir(sl_folder_name)
        except OSError:
            print(f"\n\tERROR Creando el directorio de intercambio con la web: {sl_folder_name} para el "
                  f"esclavo {slave}\n")
        else:
            print(f"\n\t\t...directorio para esclavo {slave} en {sl_folder_name}  -  CREADO")
    contador_archivos_creados = 0
    for exc_filename in file_names:
        exc_file_path = sl_folder_name + r"/" + exc_filename
        print(f"\t\t\tProcesando archivo {exc_file_path}")
        exc_file_exists = os.path.isfile(exc_file_path)
        if not exc_file_exists:
            try:
                open(exc_file_path, 'w').close()
                if dev_class == "UFHCController" and "sp" in exc_filename:  # Es centralita de suelo radiante
                    sp_bus_filename = exc_file_path + "_bus"
                    open(sp_bus_filename, 'w').close()  # Archivo para almacenar cada X148/canal/consigna
            except OSError:
                print(f"\n\n\tERROR creando el fichero de intercambio {exc_file_path} para el esclavo {slave}")
            else:
                contador_archivos_creados += 1
                print(f"\n\t...creado el archivo de intercambio nº {contador_archivos_creados}: {exc_file_path} "
                      f"para el esclavo {slave}")
    return 1


def get_boardsn() -> str:
    """
    Obtiene el número de serie de la centralita
    :return: Cadena con el número de serie de la ESP32
    """
    command = "cat /proc/cpuinfo | grep Serial"
    rpi3sn = os.popen(command).read()
    if rpi3sn:
        return rpi3sn.split(':')[1].strip()
    else:
        print("PHOENIX_INIT: No hay ninguna centralita conectada.\n\t... Abandonando el programa.")
        sys.exit()


# INICIALIZACIÓN DE VARIABLES GLOBALES
boardsn = get_boardsn()


def load_project() -> [dict, None]:
    """
    Crea un diccionario con los datos del proyecto a partir del JSON de configuración.
    Returns: Diccionario con los datos del proyecto
    """
    try:
        with open(CONFIG_FILE, "r") as f:
            project = json.load(f)
            prj_cfg = project.get("project")
            return prj_cfg
    except FileNotFoundError:
        print(f"\nERROR - No se ha encontrado el fichero de configuración del proyecto {CONFIG_FILE}")
        return


# Cargo el proyecto y compruebo si existe el JSON de configuración y si el proyecto tiene definidos edificios
prj = load_project()
if prj is None:
    print("\nERROR cargando la configuración del proyecto.\n...Abandonando el programa")
    sys.exit()
# print(prj)

buildings = prj.get("buildings")
if buildings is None:
    print("ERROR (phoenix-config: load_buildings) - No se ha definido ningún edificio en el fichero de "
          "configuración del proyecto,\n\n\t...Abandonando el programa.")
    sys.exit()

def create_o_data_files():
    """
    Se crean los archivos generales de intercambio de Modo_IV, Temperatura exterior, humedad relativa exterior y
    calidad de aire exterior

    Returns: 1 si se crea, 0 si no se crea

    """
    print("\nCREANDO ARCHIVOS DE INTERCAMBIO DE T, HR Y AQ EXTERIORES Y DE MODO IV DEL SISTEMA")
    bus_id = "1"  # Los archivos exteriores siempre irán en el bus 1
    # Compruebo si existe el directorio de intercambio de registros:
    reg_folder_exists = os.path.isdir(EXCHANGE_FOLDER)
    if not reg_folder_exists:
        try:
            os.mkdir(EXCHANGE_FOLDER)
        except OSError:
            print(f"ERROR Creando el directorio de intercambio con la web: {EXCHANGE_FOLDER}")
        else:
            print(f"\n\n\tDirectorio de intercambio con la web {EXCHANGE_FOLDER}  -  CREADO\n")
    else:
        print(f"\n\tEl fichero de intercambio, {EXCHANGE_FOLDER}, ya existe.")
    bus_folder_name = EXCHANGE_FOLDER + r"/" + bus_id
    bus_folder_exists = os.path.isdir(bus_folder_name)
    if not bus_folder_exists:
        try:
            os.mkdir(bus_folder_name)
        except OSError:
            print(f"\n\tERROR Creando el directorio de intercambio con la web: {bus_folder_name} para el "
                  f"bus {bus_id}\n")
            return 0
        else:
            print(f"\n\t\t...directorio para bus {bus_id} en {bus_folder_name}  -  CREADO")

    o_files = {"1000": TEMP_EXT_FILE, "2000": HR_EXT_FILE, "3000": AQ_EXT_FILE, "5000": MODO_IV_FILE}
    for d, f in o_files.items():
        full_d_name = bus_folder_name + r"/" + d
        d_exists = os.path.isdir(full_d_name)
        if not d_exists:
            try:
                os.mkdir(full_d_name)
            except OSError:
                print(f"ERROR Creando el directorio de intercambio con la web: {full_d_name}")
            else:
                print(f"\n\n\tDirectorio de intercambio con la web {full_d_name}  -  CREADO\n")
        else:
            print(f"\n\tEl fichero de intercambio, {full_d_name}, ya existe.")

        f_exists = os.path.isfile(f)
        if not f_exists:
            print(f"Intentando crear {f}")
            try:
                open(f, 'w').close()
            except OSError:
                print(f"\n\n\tERROR creando el fichero de valores exteriores o modo IV: {f}")
                return 0
            else:
                print(f"\n\t...creado el fichero{f}")
    print("Ficheros de valores exteriores y modo IV creados\n")
    return 1
create_o_data_files()


def load_roomgroups():
    """
    Crea las instancias de las clases que forman parte del edificio: Rooms y RoomGroups.
    Dichas clases se almacenan en el módulo "building.py"
    Se considera que tanto cada vivienda como cada edificio son RoomGroups formados por distintas habitaciones
    Returns: Diccionario con todos los grupos de habitaciones siendo la clave el "id" del grupo de habitaciones y
    el valor los objetos RoomGroup del edificio, siendo uno de los atributos de dichos objetos
    una lista de los objetos Room que componen el grupo.
    """
    print(f"\n(load_roomgroups)\tPROCESANDO GRUPOS DE HABITACIONES\n")
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
            print(f"Procesando vivienda {dwell.get('name')}")
            rooms = dwell.get("rooms")
            if rooms is None:
                print(f"WARNING (phoenix-config: load_buildings) - La vivienda {dwell.get('name')} del edificio "
                      f"{bld.get('name')} no tiene definidas habitaciones")
                continue
            hay_habitaciones = True
            for roomid, room in rooms.items():
                print(f"\n\tProcesando habitación {room.get('name')}")
                # Se instancia cada habitación.
                groups = room.get("groups")
                new_room = Room(
                    building_id=bldid,
                    dwelling_id=dwellid,
                    room_id=roomid,
                    name=room.get("name"),
                    groups=groups,
                    iv_source=room.get("iv_source"),
                    sp_source=room.get("sp_source"),
                    rh_source=room.get("rh_source"),
                    rt_source=room.get("rt_source"),
                    st_source=room.get("st_source"),
                    af=room.get("af"),
                    aq_source=room.get("aq_source"),
                    aqsp_source=room.get("aqsp_source"),
                    offsetairref=room.get("offsetairref"),
                    offsetaircal=room.get("offsetaircal")
                )
                # print(f"DEBUGGING {__file__} - Atributos Room\n{new_room.__dict__}")
                for idx, group in enumerate(groups):
                    print(f"\t\t(load_roomgroups) Procesando grupo {idx} con 'id': {group}")
                    # Compruebo si existe el grupo de habitaciones
                    grp = roomgroups.get(str(group))
                    if grp is None:
                        print(f"\t\t\tNo existia el grupo {group}. Lo creo")
                        # No existía el grupo, creo la clave en el diccionario all_rooms y el
                        # objeto RoomGroup
                        roomgroups[str(group)] = RoomGroup(id_rg=str(group))
                        print(f"\t\t\t... creado grupo de habitaciones\nGrupo: {str(group)}")
                    # Se añade la habitación a la lista de habitaciones del RoomGroup.
                    roomgroups[str(group)].roomgroup.append(new_room)
                    print(f"\t\t\t... añadiendo habitación {new_room.name} al grupo {str(group)}")

    if not hay_habitaciones:
        print("ERROR (phoenix-config: load_buildings) - No se ha definido ninguna habitación en todo el "
              "edificio en el fichero de configuración")
        sys.exit()
    # for k, v in roomgroups.items():
    #     print(f"Grupo {k}: {[x.name for x in v.roomgroup]}")
    collect()
    return roomgroups


if not os.path.isdir(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)
if not os.path.isfile(ROOMGROUPS_INSTANCES_FILE):
    all_room_groups = load_roomgroups()  # Diccionario con todos los grupos de habitaciones.
    # Clave principal es id del grupo
    with open(ROOMGROUPS_INSTANCES_FILE, "wb") as rgf:
        pickle.dump(all_room_groups, rgf)
else:
    # Ya se habían creado los grupos de habitaciones
    with open(ROOMGROUPS_INSTANCES_FILE, "rb") as rgf:
        all_room_groups = pickle.load(rgf)


# print(all_rooms)

def load_buses():
    """
    Genera un diccionario con los dispositivos ModBus físicos del sistema.
    Además, se crearán los archivos de intercambio de datos con la web para cada esclavo en función del
    tipo de dispositivo de que se trate.
    Se crea una carpeta (si no existe) en el directorio phoenix_constants.EXCHANGE_FOLDER (/home/pi/var/tmp/reg/)
    con el nombre del esclavo, y se crean, si no existen, los archivos de intercambio correspondientes según
    aparecen en phoenix_constants.xxx_FILES, que son tuplas con los nombres de los archivos a crear.
    Los dispositivos deben existir como clase en el paquete "devices" y se importarán al proyecto
    las clases que formen parte del mismo.
    Los dispositivos están definidos bajo los identificadores de cada bus.
    Params:
    project: diccionario de configuración del sistema
    Returns: diccionario con el "id" de los buses como clave y como valor otro diccionario con el "id"
    del dispositivo como clave y el objeto del dispositivo físico como valor.
    """
    print(f"\n(load_buses)\tPROCESANDO BUSES DEL PROYECTO\n")
    prj_buses = prj.get("buses")
    if prj_buses is None:
        print("ERROR (load_devices) - No se han definido los buses de comunicaciones del proyecto")
        print("ERROR (load_devices) - ... Saliendo del programa")
        sys.exit()
    devices = {}
    for bus in prj_buses:
        # Extraigo los dispositivos del bus
        bus_devices = prj_buses[bus].get("devices")
        bus_key = prj_buses[bus].get("port")
        bus_port = SERIAL_PORTS.get(bus_key)
        # bus_id = prj_buses[bus].get('id')
        bus_id = bus
        bus_name = prj_buses[bus].get('name')
        if bus_devices is None:
            msg = f"WARNING (load_devices) - No hay dispositivos asociados al bus {bus}"
            print(msg)
            continue
        print(f"\tProcesando bus {bus_id} - {bus_name}")
        devices[bus] = {}
        for device in bus_devices:
            # Datos del dispositivo específicos para el proyecto (extraídos del JSON con los datos del proyecto)
            dev_info = bus_devices[device]
            dev_id = dev_info.get("id")
            name = dev_info.get("name")
            slave = dev_info.get("slave")
            cls = dev_info.get("class")
            brand = dev_info.get("brand")
            model = dev_info.get("model")
            groups = dev_info.get("groups")
            print(f"\n\t\t... procesando el dispositivo {dev_id} - {name}: clase {cls} (esclavo {slave})")
            dev_parity = PARITY.get(dev_info.get("parity"))
            # print(f"(phoenix-config) - Paridad del dispositivo: {dev_parity}")
            if cls is None:
                msg = f"""WARNING (load_devices) - El dispositivo {name} no tiene definida su Clase Python  
                en el fichero de configuración"""
                print(msg)
                continue

            # Se instancia el dispositivo
            mbdevice = SYSTEM_CLASSES.get(cls)(
                bus_id=bus_id,
                device_id=dev_id,
                name=name,
                groups=groups,
                brand=brand,
                model=model
            )
            # Cargando parámetros de comunicación del dispositivo
            mbdevice.port = bus_port
            mbdevice.slave = dev_info.get("slave")
            mbdevice.baudrate = dev_info.get("baudrate")
            mbdevice.databits = dev_info.get("databits")
            mbdevice.parity = dev_parity  # Obtenida desde el diccionario PARITY para ESP32 (phoenix_constants)
            mbdevice.dev_stopbits = dev_info.get("stopbits")

            devices[bus][device] = mbdevice
            print(f"\t\t\t... dispositivo {dev_id} - {name}: clase {cls} (esclavo {slave}) CREADO")
            print(f"\t... creando los archivos de intercambio del dispositivo {mbdevice.slave} - {cls}")
            ex_file_creation = create_device_files(mbdevice)
            if not ex_file_creation:
                print(f"ERROR - No se han podido crear los archivos de intercambio del esclavo "
                      f"{mbdevice.slave}, de la clase {cls}")
            collect()

    if not devices:
        msg = """WARNING (load_devices) - No se ha definido ningún dispositivo en ningún bus del proyecto.
        ... Abandonando el programa"""
        print(msg)
        sys.exit()

    print(f"\n(load_buses)\tFINALIZADO EL PROCESAMIENTO DE LOS BUSES DEL PROYECTO\n\n")

    return devices


# buses = load_buses()
if not os.path.isfile(BUSES_INSTANCES_FILE):
    buses = load_buses()  # Diccionario con todos los buses.
    # Clave principal es id del grupo
    with open(BUSES_INSTANCES_FILE, "wb") as bf:
        print(
            f"{__file__}\n\tPRIMERA EJECUCIÓN\nCREANDO ARCHIVO DE BUSES CON LAS INSTANCIAS DE LOS DISPOSITIVOS MODBUS")
        pickle.dump(buses, bf)
else:
    # Ya se habían creado los grupos de habitaciones
    with open(BUSES_INSTANCES_FILE, "rb") as bf:
        print(f"{__file__}\n\t...CARGANDO ARCHIVO DE BUSES CON LAS INSTANCIAS DE LOS DISPOSITIVOS MODBUS")
        buses = pickle.load(bf)


def load_regmapfiles() -> Tuple:
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
    regmaps = []  # Lista con objetos de la clase ModbusRegisterMap
    for bus in buses:
        bus_devices = buses.get(bus)
        if bus_devices is None:
            continue
        for device in bus_devices:
            brand = bus_devices[device].brand
            model = bus_devices[device].model
            if brand is None or model is None:
                continue
            devregmapfilerelpath = f"/devices/{brand}_{model}.json"
            devregmapfilename = MODULE_PATH + devregmapfilerelpath  # Debe haber un fichero brand_model.json
            # por cada dispositivo
            if devregmapfilename not in regmapfilenames:
                regmapfilenames.add(devregmapfilename)
                # Se crea el objeto ModbusRegisterMap
                new_map = SYSTEM_CLASSES.get("modbusregistermap")(f"{brand}_{model}")
                try:
                    with open(devregmapfilename, "r") as f:
                        rmap = json.load(f)
                        new_map.rmap = rmap.get(f"{brand}_{model}")
                        regmaps.append(new_map)
                except Exception as e:
                    print(f"\n{e}\nERROR (load_regmapfiles) - Mapa de registros {devregmapfilename} no encontrado.")
            # Actualizo los valores de los atributos 'qregsmax' y 'write_operations' del dispositivo
            dev_regmap_key = f"{brand}_{model}"
            mapa_registros = [x.rmap for x in regmaps if x.map_id == dev_regmap_key][0]  # Diccionario con el mapa
            # modbus
            qregsmax = mapa_registros.get("qregsmax")
            write_ops = mapa_registros.get("write_ops")
            bus_devices[device].qregsmax = qregsmax
            bus_devices[device].write_ops = write_ops
        collect()
    return tuple(regmaps)


def config_devices():
    """
    Módulo para terminar de configurar los Objetos-Dispositivos del proyecto según su clase.
    Actualiza el diccionario buses
    Returns: diccionario buses con los objetos actualizados según su clase
    """
    # Buscamos todos los tipos de dispositivo existentes bajo la clave 'class' en cada 'devices' de cada 'bus'
    # device_dbs = set()  # SET con los Nombres de los ficheros JSON que contienen las bases de datos de cada tipo
    # de dispositivo
    print(f"\n(load_buses)\tCONFIGURANDO DISPOSITIVOS MODBUS DEL PROYECTO")
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
        print(f"\t... (config_devices) Bases de datos de configuración de dispositivos encontrados "
              f"en el bus {bus}: \n\t\t{device_dbs}")
        # Se carga el diccionario con la información POR TIPO de los dispositivos del proyecto
        collect()
        for typedb in device_dbs:
            devtype, brand, model = typedb.split("_")
            devtypefilename = PRJ_DEVICES_DB.get(devtype)
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
                    print(f"\t\t... cargada base de datos {dev_id}")
        # Ahora se completa la definición de los objetos del proyecto: Generadores, Fancoils, etc.
        null_values = (None, "")
        for device in bus_devices:
            dev_to_config = bus_devices[device]
            print(f"\t\t... finalizando configuración del dispositivo {dev_to_config.name}")
            dev_data_key = f"{dev_to_config.__class__.__name__}_{dev_to_config.brand}_{dev_to_config.model}"
            # print(f"Base datos dispositivo:\n{devtypes[dev_data_key]}\n")
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
                    if new_val is not None:  # Se evalúa esta condición por si el MBDevice tuviera atributos no
                        # definidos en el fichero de configuración
                        setattr(dev_to_config, attr, new_val)
            print(f"\t\t... configuración del dispositivo {dev_to_config.name} FINALIZADA\n")
            collect()
            # print(f"Configurando dispositivo:\n{dev_to_config.__dict__}")

    print(f"\n(load_buses)\nCONFIGURACIÓN DE LOS DISPOSITIVOS MODBUS DEL PROYECTO FINALIZADA\n\n")

    return 1


# mbregmaps = load_regmapfiles()
if not os.path.isfile(REGMAP_INSTANCES_FILE):
    mbregmaps = load_regmapfiles()  # Diccionario con todos los buses.
    # Clave principal es id del grupo
    with open(REGMAP_INSTANCES_FILE, "wb") as rmf:
        pickle.dump(mbregmaps, rmf)
else:
    # Ya se habían creado los grupos de habitaciones
    with open(REGMAP_INSTANCES_FILE, "rb") as rmf:
        mbregmaps = pickle.load(rmf)

dev_config = config_devices()

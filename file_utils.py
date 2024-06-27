#!/usr/bin/env python3

import pickle

from phoenix_constants import *
from datetime import datetime
from os import stat


def get_f_modif_timestamp(path_to_file: str) -> [datetime, None]:
    """
    Devuelve la fecha de la última modificación del archivo o None si el archivo no existe.
    Se utiliza en el intercambio de datos con la web para ver si hay que escribir en el archivo de intercambio
    la última lectura del dispositivo o si hay que propagar al dispositivo modbus el valor almacenado en el archivo.
    Param:
        path_to_file: path hasta el archivo
    Returns:
         Fecha de modificación del archivo (str de datetime) o None si no se encuentra el archivo
    """
    file_exists = os.path.isfile(path_to_file)
    if file_exists:
        last_mod_date = datetime.fromtimestamp(os.stat(path_to_file).st_mtime)
        print(f"DEBUGGING {__file__}: Obteniendo fecha ultima modificacion {path_to_file}: {last_mod_date}")
        return last_mod_date
    else:
        return None


def create_outdoors_data_files():
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
            return 0
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


def create_device_files(device) -> int:
    """
    Se crea una carpeta (si no existe) en el directorio phoenix_constants.EXCHANGE_FOLDER (/home/pi/var/tmp/reg/)
    con el nombre 'slave, y se crean, si no existen, los archivos de intercambio correspondientes según
    aparecen en phoenix_constants.'dev_class'_FILES, que son tuplas con los nombres de los archivos a crear.
    Sólo se crean los archivos de los dispositivos definidos en el JSON del proyecto.
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
            print(f"\n\tERROR Creando el directorio del bus de intercambio con la web: {bus_folder_name} para el "
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
            print(f"\n\tERROR Creando el directorio de intercambio del dispositivo "
                  f"con la web: {sl_folder_name} para el esclavo {slave}\n")
        else:
            print(f"\n\t\t...directorio para esclavo {slave} en {sl_folder_name}  -  CREADO")
    contador_archivos_creados = 0
    for exc_filename in file_names:
        exc_file_path = sl_folder_name + r"/" + exc_filename
        # print(f"\t\t\tProcesando archivo {exc_file_path}")
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
                # print(f"\n\t...creado el archivo de intercambio nº {contador_archivos_creados}: {exc_file_path} "
                #       f"para el esclavo {slave}")
    return 1


def save_devices_instances_file(prj_buses: dict) -> int:
    """
    Módulo para guardar en un pickle el diccionario con todos los buses y con las instancias de los dispositivos
    Args:
        prj_buses (diccionario con los id de los buses como clave e instancias de los dispositivos modbus como valor)

    Returns: 1 si se crea el archivo
    """
    if not os.path.isdir(TEMP_FOLDER):
        os.makedirs(TEMP_FOLDER)

    print(f"{__file__}\n\tCONTENIDO PICKLE CON BUSES DE INSTANCIAS DE DISPOSITIVOS\n{type(prj_buses)}\n")
    # Clave principal es id del bus
    with open(BUSES_INSTANCES_FILE, "wb") as bf:  # el parámetro "w" crea el archivo si no existe
        print(
            f"{__file__}\n\tGUARDANDO ARCHIVO DE BUSES CON LAS INSTANCIAS "
            f"DE LOS DISPOSITIVOS MODBUS\n")
        pickle.dump(prj_buses, bf)
        print(f"\tTamaño archivo: {stat(BUSES_INSTANCES_FILE).st_size}\n")
        return 1


def load_devices_instances() -> dict:
    """
    Módulo para cargar desde el archivo pickle los datos de los buses y las instancias de los dispositivos modbus
    Args:

    Returns: diccionario con los id de los buses como clave e instancias de los dispositivos modbus como valor o
    un diccionario vacío si no existe el archivo pickle
    """
    # prj_buses = {}
    with open(BUSES_INSTANCES_FILE, "rb") as bf:
        print(
            f"{__file__}\n\t...CARGANDO ARCHIVO DE BUSES, {BUSES_INSTANCES_FILE}, "
            f"CON LAS INSTANCIAS DE LOS DISPOSITIVOS MODBUS\n")
        prj_buses = pickle.load(bf)
    return prj_buses

def save_room_instances_file(prj_rooms: dict) -> int:
    """
    Módulo para guardar en un pickle el diccionario con todas las habitaciones
    Args:
        prj_rooms (diccionario con los id de todas las habitaciones)

    Returns: 1 si se crea el archivo
    """
    # Clave principal es id del grupo
    with open(ROOM_INSTANCES_FILE, "wb") as rf:  # el parámetro "w" crea el archivo si no existe
        print(
            f"{__file__}\n\tGUARDANDO ARCHIVO CON LAS INSTANCIAS DE LAS HABITACIONES: {ROOM_INSTANCES_FILE}")
        pickle.dump(prj_rooms, rf)  # all_rooms variable creada en phoenix_config
        return 1


def load_room_instances() -> dict:
    """
    Módulo para cargar desde el archivo pickle con las instancias de las habitaciones
    Args:

    Returns: diccionario con los id de las habitaciones (<bus>_<building>_<habitación> e instancias de las mismas o
    un diccionario vacío si no existe el archivo pickle
    """
    with open(ROOM_INSTANCES_FILE, "rb") as rf:
        print(f"{__file__}\n\t...CARGANDO ARCHIVO DE HABITACIONES CON INSTANCIAS DE LAS MISMAS")
        prj_rooms = pickle.load(rf)  # all_rooms variable creada en phoenix_config
    return prj_rooms


def save_roomgroups_instances_file(prj_roomgroups: dict) -> int:
    """
    Módulo para guardar en un pickle el diccionario con todos los grupos de habitaciones
    Args:
        prj_roomgroups (diccionario con los id de todos los grupos de habitaciones)

    Returns: 1 si se crea el archivo
    """
    # Clave principal es id del grupo
    with open(ROOMGROUPS_INSTANCES_FILE, "wb") as rgf:  # el parámetro "w" crea el archivo si no existe
        print(
            f"{__file__}\n\tGUARDANDO ARCHIVO CON LAS INSTANCIAS DE LOS GRUPOS DE HABITACIONES")
        pickle.dump(prj_roomgroups, rgf)
        return 1


def load_roomgroups_instances() -> dict:
    """
    Módulo para cargar desde el archivo pickle con las instancias de los grupos de habitaciones
    Args:

    Returns: diccionario con los id de los grupos de habitaciones e instancias de los mismos o
    un diccionario vacío si no existe el archivo pickle
    """
    with open(ROOMGROUPS_INSTANCES_FILE, "rb") as rgf:
        print(f"{__file__}\n\t...CARGANDO ARCHIVO DE GRUPOS DE HABITACIONES CON INSTANCIAS DE LOS MISMOS")
        prj_roomgroups = pickle.load(rgf)  # all_room_groups variable creada en phoenix_config
    return prj_roomgroups

def save_mbregmaps_file(prj_mbregmaps: tuple) -> int:
    """
    Módulo para guardar en un pickle los mapas de registros de los dispositivos modbus
    Args:
        prj_mbregmaps (diccionario con los mapas de registros de los dispositivos modbus)

    Returns: 1 si se crea el archivo
    """

    with open(REGMAP_INSTANCES_FILE, "wb") as rmf:  # el parámetro "w" crea el archivo si no existe
        print(
        f"{__file__}\n\tGUARDANDO ARCHIVO DE MAPAS DE REGISTROS MODBUS")
        pickle.dump(prj_mbregmaps, rmf)
        return 1


def load_mbregmaps() -> tuple:
    """
    Módulo para cargar desde el archivo pickle el diccionario con los mapas de registros modbus
    Args:

    Returns: diccionario con los mapas de registros modbus o un diccionario vacío si no existe el archivo pickle
    """
    prj_mbregmaps = {}
    # Ya se habían creado los mapas de registros
    if os.path.isfile(REGMAP_INSTANCES_FILE):
        with open(REGMAP_INSTANCES_FILE, "rb") as rmf:
            print(f"{__file__}\n\t...CARGANDO ARCHIVO DE MAPAS DE REGISTROS MODBUS")
            prj_mbregmaps = pickle.load(rmf)
    return prj_mbregmaps



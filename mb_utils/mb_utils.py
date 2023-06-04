#!/usr/bin/env python3
from asyncio import create_task, gather
from os import path
import phoenix_init as phi
from regops.regops import group_adrs, recursive_conv_f


def get_value(value_source: [dict, None]) -> [int, float, bool, phi.Tuple]:
    """
    Extrae el valor de un determinado registro ModBus almacenado en "datadb"
    Params value_source: diccionario que indica el bus, id del dispositivo en el bus (no confundir con la
    dirección del esclavo en el ModBus), el tipo de registro y el registro a leer
    Returns: valor almacenado en la base de datos (diccionario) datadb
    None si el valor que se quiere leer no existe en la base de datos
    """
    # print(f"get_value value_source: {value_source}")
    if value_source is None:
        return
    bus_id = str(value_source.get("bus"))  # En el JSON, el bus_id que conecta la habitación con el dispositivo
    # se introduce como un entero, pero la clave del diccionario con los datos leídos son str
    device_id = str(value_source.get("device"))  # OJO, es el ID del Device en la base de datos, NO EL SLAVE
    datatype = value_source.get("datatype")
    adr = str(value_source.get("adr"))  # Sucede lo mismo que con el bus_id
    if any([bus_id is None, device_id is None, datatype is None, adr is None]):
        print(f"ERROR - No se ha podido leer el valor del {datatype} {adr} en esclavo {device_id}/bus{bus_id}")
        return
    if phi.datadb is not None:
        buses_data = phi.datadb.get("buses")
        if buses_data is not None:
            bus = buses_data.get(bus_id)
            if bus is not None:
                # Busco bus_id del dispositivo con el esclavo slave_id
                device_data = {}
                for device in bus:
                    if device == device_id:
                        device_data = bus[device]
                        break
                if device_data is not None:
                    regs = device_data["data"].get(datatype)
                    if regs is not None:
                        value = regs.get(adr)
                        return value
                else:
                    print(f"get_value - No se han encontrado datos del dispositivo {device_id} en el bus {bus_id}")
                    print(f"get_value\n{phi.datadb}")


async def set_value(value_source: [dict, None], new_value: [int, float]) -> [int, None]:
    """
    Escribe el valor 'new_value' en el destino indicado en value_source.
    El valor new_value es un valor real de la magnitud que representa.
    Si la base de datos contiene una operación u operaciones a realizar en el campo conv_f_write, se aplican
    esas operaciones de transformación de new_value antes de escribir el valor en el dispositivo.
    Las clases python de los dispositivos que trabajan con los bytes alto y bajo deben incluir métodos que hagan la
    conversión de new_value antes de llamar a esta función set_value.
    Params value_source: diccionario que indica el bus, el esclavo, el tipo de registro y el registro en el que se
    va a escribir
    new_value: valor a escribir
    Returns: Resultado de la operación de escritura
    None si el valor que se quiere leer no existe en la base de datos
    """
    if value_source is None or new_value is None:
        return
    bus_id = str(value_source.get("bus"))  # En el JSON, el bus_id que conecta la habitación con el dispositivo
    # se introduce como un entero, pero la clave del diccionario con los datos leídos son str
    device_id = str(value_source.get("device"))  # # OJO, es el ID del Device en la base de datos, NO EL SLAVE
    datatype = value_source.get("datatype")
    adr = str(value_source.get("adr"))  # Para la escritura ModBus, la dirección debe ser int, pero para buscar las
    # operaciones de conversión de 'new_value', el registro 'adr' se busca como clave str en la base de datos del
    # dispositivo
    if any([bus_id is None, device_id is None, datatype is None, adr is None]):
        print(f"ERROR - No se puede escribir el valor {new_value} en el {datatype} {adr} del "
              f"esclavo {device_id}/bus{bus_id}")
        return
    device = phi.buses.get(bus_id).get(device_id)  # Devuelve el dispositivo en el que se va a escribir
    device_register_map = get_regmap(device)
    conv_f_write = device_register_map.get(datatype).get(adr).get("conv_f_write")  # Función de transformación
    # del registro a escribir
    if conv_f_write is not None:
        modbus_value = recursive_conv_f(conv_f_write, new_value, dtype=phi.TYPE_INT, prec=1)
        print(f"Escribiendo el valor real {new_value}, convertido para el dispositivo en {modbus_value}, "
              f"en el dispositivo {device.name}")
    else:
        modbus_value = new_value
        print(f"Escribiendo el valor {new_value} en el dispositivo {device.name}")

    # Compruebo las operaciones de escritura admitidas para el dispositivo
    modbus_operation = None
    if datatype == phi.MODBUS_DATATYPES_KEYS[phi.COIL_ID]:
        modbus_operation = phi.MODBUS_WRITE_OPERATIONS["SINGLE_COIL"] \
            if phi.MODBUS_WRITE_OPERATIONS["SINGLE_COIL"] in device.write_ops \
            else phi.MODBUS_WRITE_OPERATIONS["MULTIPLE_COILS"]
    elif datatype == phi.MODBUS_DATATYPES_KEYS[phi.HOLDING_REGISTER_ID]:
        modbus_operation = phi.MODBUS_WRITE_OPERATIONS["SINGLE_REGISTER"] \
            if phi.MODBUS_WRITE_OPERATIONS["SINGLE_REGISTER"] in device.write_ops \
            else phi.MODBUS_WRITE_OPERATIONS["MULTIPLE_REGISTERS"]
    else:
        print(f"Operación de escritura no habilitada para el registro {adr} de tipo {datatype}")

    res = await device.write(modbus_operation, int(adr), modbus_value)

    return res


def get_h(temp:[int, float], rel_hum:[int, float], altitud=phi.ALTITUD) -> [float, None]:
    """
    Calcula la entalpia a partir de un valor de temp en celsius y hr en %. Por defecto se toma la altitud de Madrid
    Si no se lee la humedad relativa, se devuelve 0
    """
    # print(f"Calculando entalpía de {self.name}")
    if rel_hum is None or rel_hum == 0:
        return 0
    pres_total = 101325 if altitud is None else 101325 * (1 - 2.25577 * 0.00001 * altitud) ** 5.2559
    nullvalues = ("", None, "false")
    if any((temp in nullvalues, rel_hum in nullvalues)):
        return
    pres_vap_sat = 10 ** (7.5 * temp / (273.159 + temp - 35.85) + 2.7858)  # Pa
    # print(f"presion vapor saturado: {pres_vap_sat}")
    pres_vap = pres_vap_sat * rel_hum / 100  # Pa
    # print(f"presion total: {pres_total}")
    # print(f"presion vapor: {pres_vap}")
    pres_aire_seco = pres_total - pres_vap  # Pa
    # print(f"presion aire seco: {pres_aire_seco}")
    hum_especifica = 0.621954 * (pres_vap / pres_aire_seco)  # kg agua / hg aire seco
    entalpia = (1.006 + 1.86 * hum_especifica) * temp + 2501 * hum_especifica
    return round(entalpia, 1)


def get_dp(temp:[int, float], rel_hum:[int, float]) -> [float, None]:
        """
        Calcula el punto de rocío a partir de una temp en celsius y hr en %.
        Si la temperatura o la humedad no tienen valores válidos, se devuelve None
        """
        nullvalues = ("", None, "false", 0)
        if any((temp in nullvalues, rel_hum in nullvalues)):
            return
        t_rocio = (rel_hum / 100) ** (1 / 8) * (112 + 0.9 * temp) + 0.1 * temp - 112
        return round(t_rocio, 1)


def get_regmap(device: phi.MBDevice) -> [dict, None]:
    """
    Devuelve, si existe, un diccionario con el mapa de registros del dispositivo
    Param: device: dispositivo ModBus del sistema
    Returns: diccionario con el mapa de registros
    """
    dev_regmap_key = f"{device.brand}_{device.model}"
    mapa_registros = [x.rmap for x in phi.mbregmaps if x.map_id == dev_regmap_key][0]  # Diccionario con el mapa modbus
    # del dispositivo
    # print(f"(read_project_device) - {rmap.keys()}")
    # print(f"(read_project_device) - {dev_regmap_key}")
    return mapa_registros


async def read_device_datatype(device: phi.MBDevice, regmap: dict, dtype: int) -> [dict, None]:
    """
    Módulo para leer en el bus todos los registros de un dispositivo de un determinado tipo
    Param: device: Dispositivo Modbus a leer
    Param: regmap: Mapa de registros del dispositivo
    Param: dtype: Tipo de datos a leer. Coincide con la operación de lectura ModBus
    Returns: diccionario con el número de registro (str) y el valor devuelto por el dispositivo
        None si no hay registros del tipo solicitado
    """
    modbus_operation = dtype
    regs = regmap.get(
        phi.MODBUS_DATATYPES_KEYS.get(dtype))  # Diccionario con todos los datos de tipo "dtype" del dispositivo
    # modbus_operation = MODBUS_DATATYPES_KEYS.get(dtype)
    # regs = regmap.get(modbus_operation)  # Diccionario con todos los datos de tipo "dtype" del dispositivo
    if regs is not None:  # El dispositivo tiene registros del tipo "dtype"
        addresses = sorted([int(adr) for adr in regs.keys()])  # Lista ordenada de registros a leer
        # print(f"Registros del JSON: {addresses}")
        grouped_addresses = group_adrs(addresses)  # Agrupo las direcciones de registros que van consecutivas
        # print(f"\nRegistros tipo {MODBUS_DATATYPES[dtype]}: {grouped_addresses}")
        read_data = []
        # print(f"read_device_datatype - Grupos de registros: \n{grouped_addresses}")
        for reggr in grouped_addresses:
            reading = await device.read(modbus_operation, reggr[0], reggr[1])
            if reading is not None:
                read_data += reading[:reggr[1]]  # Ajusto la cantidad de valores devueltos porque con COILS y
                # DISCRETE INPUTS la librería devuelve múltiplos de 8 valores y necesito que la respuesta coincida
                # con el número de registros solicitados
                # print(f"Lectura {phi.MODBUS_DATATYPES[dtype]}: {reading}")
        # print(f"Lectura completa: {read_data}")
        if read_data:
            adr_value_tuples = list(zip(addresses, read_data))
            # print(f"read_device_datatype:\n{adr_value_tuples}")
            for idx, result in enumerate(adr_value_tuples):
                regadr = str(result[0])  # En el JSON, los registros son keys y, por tanto, strings
                valor = result[1]
                funciones_de_conversion = regs[regadr].get("conv_f_read")
                if funciones_de_conversion is not None:
                    converted_val = recursive_conv_f(funciones_de_conversion, valor, phi.TYPE_FLOAT, 1)
                    # print(f"El valor {valor} del registro {regadr} de tipo {MODBUS_DATATYPES[dtype]} tiene " +\
                    #       f"un valor convertido de {converted_val}")
                    adr_value_tuples[idx] = (regadr, converted_val)
                else:
                    adr_value_tuples[idx] = (
                        str(regadr), valor)  # Hay que convertir a string la dirección del registro por
                    # ser keys en los JSON con los datos de los dispositivos
            # Convierto la lista de tuplas en un diccionario para facilitar el acceso a los datos
            results = {phi.MODBUS_DATATYPES_KEYS.get(dtype): {}}
            for data_pair in adr_value_tuples:
                results[phi.MODBUS_DATATYPES_KEYS.get(dtype)][data_pair[0]] = data_pair[1]
            phi.collect()
            # print(f"read_device_datatype: {results}")
            return results
        else:
            return  # Si el dispositivo no ha devuelto nada, se devuelve None
    else:
        results = {phi.MODBUS_DATATYPES_KEYS.get(dtype): None}
        return results  # Si no hay registros del tipo "dtype" devuelve None para ese tipo de registro


async def read_project_device(device: phi.MBDevice) -> [str, None]:
    """
    Lee todos los registros descritos en el JSON de "device" y los almacena en un fichero en memoria.
    Los campos de la base de datos tendrán como clave el número de registro (str) y los campos
    hora, descripción (en español por defecto) y valor real tras aplicar las operaciones de conversión al
    valor leído, por ejemplo dividir por 10 y pasar de Celsius a Farenheit.
    Params:
        device: Dispositivo ModBus, subclase de MBDevice
    Returns:
        JSON con formato str con los tipos de registro y los valores leídos en cada registro
        Si falla la lectura, el programa se detiene
    """
    rmap = get_regmap(device)
    name = rmap.get("name")
    print(f"Nombre del dispositivo: {name}")
    reading_tasks = [create_task(read_device_datatype(device, rmap, datatype))
                     for datatype in tuple(phi.MODBUS_DATATYPES.keys())]

    readings = await gather(*reading_tasks)

    return readings


async def read_all_buses(id_lectura: int = 0):
    """
    Recorre todos los buses y guarda en READINGS_FILE el diccionario con los valores leídos en los registros
    ModBus de todos los dispositivos.
    Returns: diccionario con la última lectura
    """
    # print(f"mb_utils - Variable buses al llamar read_all_buses:\n{phi.buses}\n\n{id(phi.buses)}\n\n")

    hora_lectura = phi.datetime.now()  # Hora actual en formato datetime

    # historico_lecturas["lecturas"][id_lectura_actual] = {}
    lectura_actual = {
        "id": id_lectura,
        "hora": str(hora_lectura),
        "buses": {}
    }
    print(f"(read_all_buses) {hora_lectura}: LEYENDO TODOS LOS BUSES\n")
    for idbus, bus in phi.buses.items():
        lectura_actual["buses"][idbus] = {}
        for iddevice, device in bus.items():
            lectura_actual["buses"][idbus][iddevice] = {"slave": device.slave, "data": {}}
            # lectura_actual["buses"][idbus][iddevice]["slave"] = device.slave
            # Lee el dispositivo completo y almacena la información en un fichero en memoria StringIO?
            device_readings = await read_project_device(device)  # Lectura ModBus
            # print(f"\n\tLECTURA DISPOSITIVO\t{device.name}\n\t\t{device_readings}")
            print(f"\n{str(phi.datetime.now())}\nDuración:\t{str(phi.datetime.now() - hora_lectura)}\n")
            print(f"device_readings: {device_readings}")
            if all([x is None for x in device_readings]):
                print(f"No hay lecturas del dispositivo {device.name}")
                continue
            # lectura_actual["buses"][idbus][iddevice]["data"] = {}
            for regtype_readings in device_readings:
                if regtype_readings is None:
                    print(f"DEBBUGGING {__file__}: El dispositivo {device.name} no tiene registros: {regtype_readings}")
                    continue  # JSC Modification on SETUP
                for regtype, dev_response in regtype_readings.items():
                    lectura_actual["buses"][idbus][iddevice]["data"][regtype] = dev_response

    # Guardo en el disco la última lectura
    with open(phi.READINGS_FILE, "w") as f:  # El fichero se reescribe en cada bucle. No acumula históricos
        phi.json.dump(lectura_actual, f)
    return lectura_actual


def get_f_modif_timestamp(path_to_file:str) -> [str, None]:
    """
    Devuelve la fecha de la última modificación del archivo o None si el archivo no existe.
    Se utiliza en el intercambio de datos con la web para ver si hay que escribir en el archivo de intercambio
    la última lectura del dispositivo o si hay que propagar al dispositivo modbus el valor almacenado en el archivo.
    Param:
        path_to_file: path hasta el archivo
    Returns:
         Fecha de modificación del archivo (str de datetime) o None si no se encuentra el archivo
    """
    file_exists = phi.os.path.isfile(path_to_file)
    if file_exists:
        last_mod_date = str(phi.datetime.fromtimestamp(phi.os.stat(path_to_file).st_mtime))
        return last_mod_date
    else:
        return None


async def check_changes_from_web() -> int:
    """
    Módulo para intercambiar información con la web a través de los archivos almacenados en /home/pi/var/tmp/reg
    Habrá un directorio por cada esclavo y dentro de cada directorio un archivo con el último valor de cada
    atributo: consignas, modos, temperaturas, etc.
    Algunos de los archivos se pueden escribir tanto desde la web como desde el código. En función de la fecha
    de la última modificación del archivo, se actualizará la web o el atributo correspondiente.
    Returns:
         1 si se ha hecho alguna modificación desde la web
         0 si no hay que modificar nada desde la web
    """
    first_time = False
    # Obtengo la fecha de la última lectura guardada:
    if not path.isfile(phi.READINGS_FILE):
        # No se ha generado el archivo con las últimas lecturas ModBus.
        # Se recogen los valores almacenados en los ficheros de intercambio.
        first_time = True
        last_reading_time = None
        # return 0
    else:
        with open(phi.READINGS_FILE, "r") as rf:
            last_reading = phi.json.load(rf)
            last_reading_time = last_reading.get("hora")
            print (f"\nComprobando cambios desde la WEB:\n\tHora de la última lectura: {last_reading_time}")

    # Recorro todos los esclavos para ver si hay que actualizar algún valor
    attr_mod = {}
    attr_not_mod = {}
    checked = []
    for bus_id, bus in phi.buses.items():
        # devs = phi.buses.get(bus)
        for dev_id, dev in bus.items():
            if first_time:  # La primera vez configuramos los dispositivos con los valores de los ficheros de
                # intercambio
                await update_devices_from_xch_files(dev)
                continue
            dev_sl = str(dev.slave)
            checked_device = (bus_id, dev_sl)
            if checked_device in checked:  # Si ya he comprobado el dispositivo, no vuelvo a hacerlo (normalmente
                # no va a haber dispositivos repetidos, pero por si acaso...
                continue
            else:
                checked.append(checked_device)
            clase = dev.__class__.__name__
            xch_rw_files = phi.EXCHANGE_RW_FILES.get(clase)
            ex_folder_name = phi.EXCHANGE_FOLDER + r"/" + bus_id + r"/" + dev_sl
            print(f"Comprobando esclavo {dev_sl} (clase {clase})) del bus {bus_id}")
            # print(f"\tArchivos\n{xch_rw_files}")
            for f in xch_rw_files:
                file_to_check = ex_folder_name + r"/" + f
                last_mod_time = get_f_modif_timestamp(file_to_check)
                current_value = getattr(dev, f)  # el nombre del fichero f coincide con el atributo a comprobar
                if any([x is None for x in (last_mod_time, last_reading_time)]):
                    print (f"ERROR al recuperar las fechas de última modificación y última lectura:\n\t"
                           f"Última modificación: {last_mod_time}\n\t"
                           f"Última lectura: {last_reading_time}")
                    continue
                if last_mod_time > last_reading_time:  # Ha habido modificaciones desde la Web
                    with open(file_to_check, "r") as modf:
                        new_value = modf.read()
                    print(f"Se ha modoficado desde la Web el fichero:\n\t{file_to_check}\n"
                          f"Valor anterior:\t{current_value} (tipo {type(getattr(dev, f))})\n"
                          f"Valor desde web:\t{new_value} (tipo {type(new_value)})")
                    attr_mod[file_to_check] = new_value
                    if new_value is not None:
                        if '(' in new_value: # Is Tuple
                            val_to_write = tuple(map(int, new_value.strip('()').split(', ')))
                            setattr(dev, f, val_to_write)
                        elif '.' in new_value: # Is float
                            setattr(dev, f, float(new_value))
                        elif new_value.isdecimal():  # Is int
                            setattr(dev, f, int(new_value))
                        else:
                            setattr(dev, f, str(new_value))
                else:
                    attr_not_mod[file_to_check] = current_value
        print(f"Archivos modificados: {attr_mod}")
        print(f"Archivos NO modificados: {attr_not_mod}")

    return 1


async def update_roomgroups_values():
    """
    Actualiza los cálculos para todos los grupos de habitaciones y los guarda en ROOMGROUPS_VALUES_FILE
    Returns: si la actualización de grupos de habitaciones y la escritura de ROOMGROUPS_VALUES_FILE ha sido un éxito
    """
    roomgroup_updating_tasks = [create_task(r.get_consignas())
                                for r in tuple(phi.all_room_groups.values())]
    roomgroup_updating_results = await gather(*roomgroup_updating_tasks)
    roomgroups_values = {}
    for roomgroup_id, roomgroup in phi.all_room_groups.items():
        roomgroups_values[roomgroup_id] = {}
        roomgroups_values[roomgroup_id]["iv"] = roomgroup.iv
        roomgroups_values[roomgroup_id]["demanda"] = roomgroup.demand
        roomgroups_values[roomgroup_id]["water_sp"] = roomgroup.water_sp
        roomgroups_values[roomgroup_id]["air_sp"] = roomgroup.air_sp
        roomgroups_values[roomgroup_id]["air_rt"] = roomgroup.air_rt
        roomgroups_values[roomgroup_id]["air_dp"] = roomgroup.air_dp
        roomgroups_values[roomgroup_id]["air_h"] = roomgroup.air_h
        roomgroups_values[roomgroup_id]["aq"] = roomgroup.aq
        roomgroups_values[roomgroup_id]["aq_sp"] = roomgroup.aq_sp
    # Actualizo el fichero con la información de los grupos de habitaciones para actualizar los dispositivos del
    # proyecto vinculados a los mismos
    with open(phi.ROOMGROUPS_VALUES_FILE, "w") as f:
        phi.json.dump(roomgroups_values, f)

    return roomgroup_updating_results


async def get_roomgroup_values(roomgroup_id: str) -> [phi.Dict, None]:
    """
    Recoge el valor de 'attribute' de un determinado roomgroup almacenado en ROOMGROUPS_VALUES_FILE
    Returns: diccionario con los valores del roomgroup
    """
    if not path.isfile(phi.ROOMGROUPS_VALUES_FILE):
        return
    try:
        with open(phi.ROOMGROUPS_VALUES_FILE, "r") as f:
            roomgroups_values = phi.json.load(f)
    except FileNotFoundError as e:
        print(f"ERROR {__file__}. No se puede abrir el archivo {phi.ROOMGROUPS_VALUES_FILE}\n{e}")
        return

    roomgroup_info = roomgroups_values.get(roomgroup_id)
    if roomgroup_info is None:
        print(f"ERROR {__file__}. No se encuentra el grupo de habitaciones {roomgroup_id:}")
        return

    return roomgroup_info


async def update_all_buses():
    """
    Actualiza los datos en todos los dispositivos en función de los valores calculados para los grupos de
    habitaciones
    Returns: 1
    """
    webcheck = await check_changes_from_web()
    for idbus, bus in phi.buses.items():
        for iddevice, device in bus.items():
            print(f"\nActualizando valores del dispositivo {device.name}")
            update = await device.update()
            print(repr(device))
    return 1


# async def update_device_exch_files(device:[*phi.system_classes]):
async def update_xch_files_from_devices(device):
    """
    Actualiza los archivos de intercambio de 'device' con los últimos valores leídos en los dispositivos
    Param:
        device: Dispositivo ModBus
    :return:
    """
    if not device:
        return

    device_class_names = [c().__class__.__name__ for c in phi.SYSTEM_CLASSES.values() if c != phi.ModbusRegisterMap]
    cls = device.__class__.__name__  # Tipo de dispositivo UFHCController, Generator, Fancoil, Split,
    print(f"\n\n\nDEBUGGING - {device_class_names}\nActualizando ficheros de la clase {cls}\n\n\n")
    if cls not in device_class_names:
        print(f"ERROR {__file__} - La clase {cls} no corresponde a ninguna de las clases del "
              f"proyecto:\n{device_class_names}")
        return
    bus_id = device.bus_id  # el atributo bus_id pertenece en realidad a los dispositivos creados con herencias de
    # MBDevice, pero no pertenece a MBDevice
    slave = str(device.slave)  # Los archivos de intercambio van asociados a los números de esclavos de cada bus,
    # no al device_id definido en la base de datos del proyecto

    # HeatRecoveryUnit, AirZoneManager, TempFluidController
    attrs_to_update = phi.EXCHANGE_R_FILES.get(cls)  # Tupla con los archivos a actualizar (son los nombres
    # de los atributos)
    for attr in attrs_to_update:
        attr_file = phi.EXCHANGE_FOLDER + r"/" + bus_id + r"/" + slave + r"/" + attr
        if not path.isfile(attr_file):
            print(f"ERROR {__file__}\nNo se encuentra el archivo {attr_file}")
            continue
        attr_value = device.__getattribute__(attr)
        if attr_value is not None:
            with open(attr_file, "w") as f:
                f.write(str(attr_value))


async def update_devices_from_xch_files(device):
    """
    Actualiza el dispositivo 'device' con los valores leídos en los archivos de intercambio
    Param:
        device: Dispositivo ModBus
    :return:
    """
    if not device:
        return

    device_class_names = [c().__class__.__name__ for c in phi.SYSTEM_CLASSES.values() if c != phi.ModbusRegisterMap]
    cls = device.__class__.__name__  # Tipo de dispositivo UFHCController, Generator, Fancoil, Split,
    print(f"\n\n\nDEBUGGING - {device_class_names}\nActualizando el dispositivo {device.name}, de la clase {cls} "
          f"con la configuración de sus ficheros de intercambio.\n\n\n")
    if cls not in device_class_names:
        print(f"ERROR {__file__} - La clase {cls} no corresponde a ninguna de las clases del "
              f"proyecto:\n{device_class_names}")
        return
    bus_id = device.bus_id  # el atributo bus_id pertenece en realidad a los dispositivos creados con herencias de
    # MBDevice, pero no pertenece a MBDevice
    slave = str(device.slave)  # Los archivos de intercambio van asociados a los números de esclavos de cada bus,
    # no al device_id definido en la base de datos del proyecto

    # HeatRecoveryUnit, AirZoneManager, TempFluidController
    attrs_to_update = phi.EXCHANGE_R_FILES.get(cls)  # Tupla con los archivos a actualizar (son los nombres
    # de los atributos)
    for attr in attrs_to_update:
        attr_file = phi.EXCHANGE_FOLDER + r"/" + bus_id + r"/" + slave + r"/" + attr
        if not path.isfile(attr_file):
            print(f"ERROR {__file__}\nNo se encuentra el archivo {attr_file}")
            continue
        with open(attr_file, "r") as f:
            attr_value_in_file = f.read()
            attr_value_in_device = getattr(device, attr)
            print(f"DEBUGGING {__file__}: \n\tfichero intercambio: {attr_file}\n\tAtributo: {attr_value_in_file}")
            if isinstance(attr_value_in_device, int):  # Atributo tipo integer
                if attr_value_in_file:
                    attr_value_in_file = int(attr_value_in_file)
                else:
                    attr_value_in_file = attr_value_in_device
            elif isinstance(attr_value_in_device, float):  # Atributo tipo float
                if attr_value_in_file:
                    attr_value_in_file = float(attr_value_in_file)
                else:
                    attr_value_in_file = attr_value_in_device
            if attr_value_in_file is not None:
                setattr(device, attr, attr_value_in_file)






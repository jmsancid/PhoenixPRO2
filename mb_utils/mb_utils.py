#!/usr/bin/env python3
from asyncio import create_task, gather
# from phoenix_init import *
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
            # lectura_actual["buses"][idbus][iddevice]["data"] = {}
            for regtype_readings in device_readings:
                for regtype, dev_response in regtype_readings.items():
                    lectura_actual["buses"][idbus][iddevice]["data"][regtype] = dev_response

    # Guardo en el disco la última lectura
    with open(phi.READINGS_FILE, "w") as f:  # El fichero se reescribe en cada bucle. No acumula históricos
        phi.json.dump(lectura_actual, f)
    return lectura_actual


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
        roomgroups_values[roomgroup_id]["demanda"] = roomgroup.demanda
        roomgroups_values[roomgroup_id]["water_sp"] = roomgroup.water_sp
        roomgroups_values[roomgroup_id]["air_sp"] = roomgroup.air_sp
        roomgroups_values[roomgroup_id]["air_rt"] = roomgroup.air_rt
    # Actualizo el fichero con la información de los grupos de habitaciones para actualizar los dispositivos del
    # proyecto vinculados a los mismos
    with open(phi.ROOMGROUPS_VALUES_FILE, "w") as f:
        phi.json.dump(roomgroups_values, f)

    return roomgroup_updating_results


async def update_all_buses():
    """
    Actualiza los datos en todos los dispositivos en función de los valores calculados para los grupos de
    habitaciones
    Returns: 1
    """
    for idbus, bus in phi.buses.items():
        for iddevice, device in bus.items():
            print(f"\nActualizando valores del dispositivo {device.name}")
            update = await device.update()
            print(repr(device))
    return 1

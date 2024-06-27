#!/usr/bin/env python3

# import sys
from asyncio import create_task, gather
from os import path
import phoenix_init as phi
from regops.regops import group_adrs, recursive_conv_f, get_hb_lb
from file_utils import get_f_modif_timestamp, save_devices_instances_file


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


def save_value(value_target: [dict, None], new_value: [int, float, bool, phi.Tuple]) -> [int, float, bool, phi.Tuple]:
    """
    Actualiza el valor de un determinado registro ModBus almacenado en "datadb"
    Params value_target: diccionario que indica el bus, id del dispositivo en el bus (no confundir con la
    dirección del esclavo en el ModBus), el tipo de registro, el registro a actualizar y su valor
    Returns: valor almacenado en la base de datos (diccionario) datadb
    None si el valor que se quiere leer no existe en la base de datos
    """
    # print(f"get_value value_source: {value_source}")
    if value_target is None:
        return
    bus_id = str(value_target.get("bus"))  # En el JSON, el bus_id que conecta la habitación con el dispositivo
    # se introduce como un entero, pero la clave del diccionario con los datos leídos son str
    device_id = str(value_target.get("device"))  # OJO, es el ID del Device en la base de datos, NO EL SLAVE
    datatype = value_target.get("datatype")
    adr = str(value_target.get("adr"))  # Sucede lo mismo que con el bus_id
    if any([bus_id is None, device_id is None, datatype is None, adr is None]):
        print(f"ERROR - No se ha podido leer el valor del {datatype} {adr} en esclavo {device_id}/bus{bus_id}")
        return
    if phi.datadb is not None:
        buses_data = phi.datadb.get("buses")
        if buses_data is not None:
            bus = buses_data.get(bus_id)
            if bus is not None:
                # Busco bus_id del dispositivo con device_id
                device_data = {}
                device = None
                for device in bus:
                    if device == device_id:
                        device_data = bus[device]
                        break
                if device_data not in [None, {}]:
                    regs = device_data["data"].get(datatype)
                    if regs is not None:
                        old_value = regs.get(adr)
                        if old_value is not None:
                            # print("Device: ", device, "bus: ",
                            #       phi.datadb["buses"][bus_id][device_id]["data"][datatype][adr] )
                            # sys.exit()
                            if isinstance(old_value, float):
                                phi.datadb["buses"][bus_id][device_id]["data"][datatype][adr] = float(new_value)
                            elif isinstance(old_value, int):
                                phi.datadb["buses"][bus_id][device_id]["data"][datatype][adr] = int(new_value)
                            elif isinstance(old_value, tuple):  # El registro separa bytes alto y bajo
                                phi.datadb["buses"][bus_id][device_id]["data"][datatype][adr] = get_hb_lb(new_value)
                            else:
                                phi.datadb["buses"][bus_id][device]["data"][datatype][adr] = new_value
                            print(f"\nsave_value. Valor anterior {old_value}/{type(old_value)} "
                                  f"actualizado a {new_value}/{type(new_value)}")
                            check_new_value = get_value(value_target)
                            print(f"save_value. Comprobando actualización. "
                                  f"Nuevo valor leído en db: {check_new_value}\n")
                            return check_new_value
                else:
                    print(f"save_value - No se han encontrado datos del dispositivo {device_id} en el bus {bus_id}")
                    print(f"save_value\n{phi.datadb}")


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
    print(f"Operación Modbus, adr, valor a escribir, resultado {modbus_operation}, {int(adr)}, "
          f"{modbus_value}/{type(modbus_value)}, {res}")

    return res


async def get_h(temp: [int, float], rel_hum: [int, float], altitud=phi.ALTITUD) -> [float, None]:
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


async def get_dp(temp: [int, float], rel_hum: [int, float]) -> [float, None]:
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
            return
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
    print(f"\nNombre del dispositivo: {name}")
    reading_tasks = [create_task(read_device_datatype(device, rmap, datatype))
                     for datatype in tuple(phi.MODBUS_DATATYPES.keys())]

    readings = await gather(*reading_tasks)

    return readings


async def read_all_buses(id_lectura: int = 0):
    """
    Recorre todos los buses y guarda en el json READINGS_FILE el diccionario con los valores leídos en los registros
    ModBus de todos los dispositivos.
    Returns: diccionario con la última lectura: hora y buses con los valores de cada tipo de registro leído en cada
    dispositivo de cada bus.
    """
    # print(f"mb_utils - Variable buses al llamar read_all_buses:\n{phi.buses}\n\n{id(phi.buses)}\n\n")

    hora_lectura = phi.datetime.now()  # Hora actual en formato datetime

    # Se lee el id de la última lectura si existe. Si no, vale 0
    id_lectura_anterior = phi.lectura_anterior.get("id") if phi.lectura_anterior else 0
    id_lectura = id_lectura_anterior + 1

    # Se reinicia cada día el id de lectura
    if id_lectura > 1:
        # si hay lectura anterior, extraigo la fecha y si no, le asigno el día de hoy

        fecha_lectura_anterior = phi.datetime.strptime(phi.lectura_anterior.get("hora"),
                                                       "%Y-%m-%d %H:%M:%S.%f") \
            if phi.lectura_anterior else hora_lectura
        # si la fecha de la lectura anterior es más antigua que la actual y los días son distintos, se asume que el
        # día ha cambiado y hay que reiniciar el contador de lecturas
        if fecha_lectura_anterior < hora_lectura and fecha_lectura_anterior.day != hora_lectura.day:
            id_lectura = 1

    lectura_actual = {
        "id": id_lectura,
        "hora": str(hora_lectura),  # Los objetos datetime no se pueden pasar a JSON
        "buses": {}
    }
    print(f"(read_all_buses) {hora_lectura}: LEYENDO TODOS LOS BUSES\n"
          f"La lectura anterior tuvo lugar a las {phi.lectura_anterior.get('hora')}\n")
    for idbus, bus in phi.buses.items():
        lectura_actual["buses"][idbus] = {}
        for iddevice, device in bus.items():
            lectura_actual["buses"][idbus][iddevice] = {"slave": device.slave, "data": {}}
            # lectura_actual["buses"][idbus][iddevice]["slave"] = device.slave
            # Lee el dispositivo completo y almacena la información en un fichero en memoria StringIO?
            device_readings = await read_project_device(device)  # Lectura ModBus
            print(f"\n\tLECTURA DISPOSITIVO\t{device.name}\n\t\t{device_readings}")
            print(f"\n{str(phi.datetime.now())}\nDuración:\t{str(phi.datetime.now() - hora_lectura)}")
            if all([x is None for x in device_readings]):
                print(f"No hay lecturas del dispositivo {device.name}")
                continue
            # lectura_actual["buses"][idbus][iddevice]["data"] = {}
            for idx, regtype_readings in enumerate(device_readings):
                regtypename = phi.MODBUS_DATATYPES.get(idx + 1)
                if regtype_readings is None:
                    print(f"DEBBUGGING {__file__}: El dispositivo no ha devuelto lecturas de "
                          f"registros del tipo: {regtypename}")
                    continue  # JSC Modification on SETUP
                if isinstance(regtype_readings, dict) and \
                        len(regtype_readings.values()) == 1 and \
                        list(regtype_readings.values())[0] is None:
                    print(f"El dispositivo no tiene registros del tipo {regtypename}")
                    continue  # JSC Modification on SETUP
                for regtype, dev_response in regtype_readings.items():
                    lectura_actual["buses"][idbus][iddevice]["data"][regtype] = dev_response

    # Guardo en el disco la última lectura
    with open(phi.READINGS_FILE, "w") as f:  # El fichero se reescribe en cada bucle. No acumula históricos
        phi.json.dump(lectura_actual, f)
    return lectura_actual

# async def check_changes_from_web() -> int:
#     """
#     Módulo para intercambiar información con la web a través de los archivos almacenados en /home/pi/var/tmp/reg
#     Habrá un directorio por cada esclavo y dentro de cada directorio un archivo con el último valor de cada
#     atributo: consignas, modos, temperaturas, etc.
#     Algunos de los archivos se pueden escribir tanto desde la web como desde el código. En función de la fecha
#     de la última modificación del archivo, se actualizará la web o el atributo correspondiente.
#     Las consignas de temperatura compartidas se almacenan en ficheros con el nombre spx donde x es el nombre del
#     canal de la centralita X148 y, paralelamente, las consignas leídas de cada X148 se almacenan en los archivos
#     spx_bus.
#     Cuando se ejecuta este módulo, ya existe un archivo con las lecturas almacenadas.
#     Returns:
#          1 si se ha hecho alguna modificación desde la web
#          0 si no hay que modificar nada desde la web
#     """
#     # first_time = False
#     # Obtengo la fecha de la última lectura guardada:
#     if not path.isfile(phi.READINGS_FILE):
#         # No se ha generado el archivo con las últimas lecturas ModBus.
#         # Se recogen los valores almacenados en los ficheros de intercambio.
#         # first_time = True
#         # last_reading_time = None
#         emsg = f"{phi.datetime.now}/ {__file__} (check_changes_from_web) ERROR - No se ha generado fichero de lecturas"
#         raise FileNotFoundError(emsg)
#         # return
#     else:
#         # with open(phi.READINGS_FILE, "r") as rf:
#         #     last_reading = phi.json.load(rf)
#         # last_reading_time = last_reading.get("hora")
#         last_reading_time = phi.lectura_anterior.get("hora")
#         print(f"\nComprobando cambios desde la WEB:\n\tHora de la última lectura: {last_reading_time}")
#         # last_exec_time = get_f_modif_timestamp(phi.LAST_EXEC_DATE_FILE)
#         last_exec_time =  phi.datetime.strptime(last_reading_time, "%Y-%m-%d %H:%M:%S.%f")
#
#     # Recorro todos los esclavos para ver si hay que actualizar algún valor
#     attr_mod = {}
#     attr_not_mod = {}
#     checked = []
#     for bus_id, bus in phi.buses.items():
#         # devs = phi.buses.get(bus)
#         changes = False
#         for dev_id, dev in bus.items():
#             dev_sl = str(dev.slave)
#             checked_device = (bus_id, dev_sl)
#             if checked_device in checked:  # Si ya he comprobado el dispositivo, no vuelvo a hacerlo (normalmente
#                 # no va a haber dispositivos repetidos, pero por si acaso...
#                 print(f"Ya se han comprobado los cambios del esclavo {dev_sl}: {dev.name} del bus {bus_id}")
#                 continue
#             else:
#                 checked.append(checked_device)
#             dev_class = dev.__class__.__name__
#             if dev_class == "UFHCController":  # Los cambios en la centralita X148 ya se han comprobado
#                 continue
#
#             xch_rw_files = phi.EXCHANGE_RW_FILES.get(dev_class)
#             ex_folder_name = phi.EXCHANGE_FOLDER + r"/" + bus_id + r"/" + dev_sl
#             print(f"Comprobando esclavo {dev_sl}: {dev.name} (clase {dev_class})) del bus {bus_id}")
#             # print(f"\tArchivos\n{xch_rw_files}")
#             for xf in xch_rw_files:
#                 xch_file_to_check = ex_folder_name + r"/" + xf
#                 # file_from_dev_to_check = ex_folder_name + r"/" + xf
#                 last_mod_time = get_f_modif_timestamp(xch_file_to_check)
#                 print(f"check_changes_from_web - Comprobando valores actuales del dispositivo {dev.name}, "
#                       f"atributo {xf}")
#                 # Cambio la siguiente línea porque por algún motivo el atributo no está actualizado NO APLICA
#                 current_value = getattr(dev, xf)  # el nombre del fichero xf coincide con el atributo a comprobar
#
#                 if None in (last_mod_time, last_exec_time):
#                     print(f"ERROR al recuperar las fechas de última modificación y última lectura:\n\t"
#                           f"Última modificación {xch_file_to_check}: {last_mod_time} - tipo {type(last_mod_time)}\n\t"
#                           f"Última ejecución: {last_exec_time} - tipo {type(last_exec_time)}")
#                     continue
#                 print(f"Fechas de última modificación y última lectura:\n\t"
#                       f"Última modificación {xch_file_to_check}: {last_mod_time}\n\t"
#                       f"Última ejecución: {last_exec_time}")
#                 with open(xch_file_to_check, "r") as modf:
#                     print(f"Examinando file_from_web_to_check: {xch_file_to_check}")
#                     web_value = modf.read().strip()
#                 print(f"\nDEBUGGING {__file__}:"
#                       f"\n\tValor leído en la web: {web_value}"
#                       f"\n\tValor actual: {current_value} {type(current_value)}")
#
#                 if last_mod_time > last_exec_time:  # Ha habido modificaciones desde la Web
#                     changes = True
#                     print(f"\nSe ha modificado desde la Web el fichero:\n\t{xch_file_to_check}\n"
#                           f"\tValor anterior:\t{current_value} (tipo {type(getattr(dev, xf))})\n"
#                           f"\tValor desde web:\t{web_value} (tipo {type(web_value)})\n")
#                     attr_mod[xch_file_to_check] = web_value
#                     if not web_value is None:
#                         if '(' in web_value:  # Is Tuple
#                             val_to_write = tuple(map(int, web_value.strip('()').split(', ')))
#                         elif '.' in web_value:  # Is float
#                             val_to_write = float(web_value)
#                         elif web_value.isdecimal():  # Is int
#                             val_to_write = int(web_value)
#                         else:
#                             val_to_write = str(web_value)
#                         print(f"Actualizando el atributo {xf} del dispositivo {dev.name} con el valor {val_to_write}")
#                         setattr(dev, xf, val_to_write)
#                         print(f"Leyendo atributo tras escritura: {getattr(dev, xf)}")
#
#                         with open(xch_file_to_check, "w") as xchf:
#                             xchf.write(str(web_value))
#                         with open(xch_file_to_check, "r") as modf:
#                             web_value = modf.read().strip()
#                             print(f"\nComprobando si se ha escrito {val_to_write} en {xch_file_to_check}. "
#                                   f"Valor leído: {web_value}")
#                 else:
#                     attr_not_mod[xch_file_to_check] = current_value
#             if changes:
#                 changes = False
#                 print(f"{__file__} Subiendo actualización a dispositivo ModBus")
#                 await dev.upload()
#         print(f"Archivos modificados: {attr_mod}")
#         print(f"Archivos NO modificados: {attr_not_mod}")
#
#     return 1

# JSC 19/06/2024
# Cambio la versión de check_changes_from_web introdudiendo como parámetros el dispositivo y el atributo.
# Si el archivo contiene un valor de atributo distinto, actualizo el atributo y si no, el archivo.
# Las consignas de las X147 y X148 se pueden modificar también desde el termostato y hay que ver los valores de sp_bus

async def check_changes_from_web(bus_id: str, dev: phi.MBDevice, attr: str) -> int:
    """
    Módulo para comprobar si se ha cambiado algún atributo desde la web.
    Si el atributo no está en <CLASE>_RW_FILES, se rellena el atributo con la última lectura porque se trata de
    archivos de sólo lectura.
    Si el valor del atributo RW es distinto del contenido del archivo, se interpreta que hay cambios desde la web,
    excepto con los archivos spx_bus de ls UFHCController, en los que se comprueba si lo que ha cambiado es el
    archivo spx o spx_bus en función de la fecha del archivo
    parameters:
    bus_id: bus al que pertenece el dispositivo. Es string
    dev: dispositivo modbus de la clase MBDevice
    attr: atributo del dispositivo a comprobar. Es string
    Cuando se ejecuta este módulo, ya existe un archivo con las lecturas almacenadas.
    Returns:
         1 si se ha hecho alguna modificación desde la web
         0 si no hay que modificar nada desde la web
    """
    # Obtengo la fecha de la última lectura guardada:
    if not path.isfile(phi.READINGS_FILE):
        # No se ha generado el archivo con las últimas lecturas ModBus.
        # Se recogen los valores almacenados en los ficheros de intercambio.
        emsg = f"{phi.datetime.now}/ {__file__} (check_changes_from_web) ERROR - No se ha generado fichero de lecturas"
        raise FileNotFoundError(emsg)
        # return
    else:
        last_reading_time = phi.lectura_anterior.get("hora")
        if last_reading_time:
            last_exec_time =  phi.datetime.strptime(last_reading_time, "%Y-%m-%d %H:%M:%S.%f")
        else:
            last_exec_time = phi.init_time - phi.timedelta(hours=1)

    # Recorro todos los esclavos para ver si hay que actualizar algún valor
    dev_sl = str(dev.slave)
    dev_class = dev.__class__.__name__

    class_rw_files = phi.EXCHANGE_RW_FILES.get(dev_class)  # Si el atributo no está entre los archivos RW, no puede
    # escribirse desde la web y, por tanto, el archivo y el atributo se actualizan con el último valor leído

    is_UFHC_SP = dev_class == "UFHCController" and "sp" in attr  # Para ver si el atributo es una consigna de termostato

    ex_folder_name = phi.EXCHANGE_FOLDER + r"/" + bus_id + r"/" + dev_sl
    print(f"Comprobando esclavo {dev_sl}: {dev.name} (clase {dev_class})) del bus {bus_id}")
    xch_file_to_check = ex_folder_name + r"/" + attr
    with open(xch_file_to_check, "r") as xchf:
        xch_value = xchf.read().strip()  # Valor leído en el archivo de intercambio
    last_mod_time = get_f_modif_timestamp(xch_file_to_check)
    current_value = getattr(dev, attr)  # obtengo el valor del atributo
    print(f"check_changes_from_web - Comprobando valores actuales del dispositivo {dev.name}, "
          f"atributo {attr}.\n"
          f"Valor actual: {current_value}\n"
          f"Valor en web: {xch_value}")


    # Si el atributo a comprobar es la consigna de los X147/8, el procedimiento es distinto al resto de atributos
    if is_UFHC_SP:
        attr_dev_bus_file = f"{xch_file_to_check}_bus"  # Debe comprobarse si hay cambios desde la web
        last_spbus_change_date = get_f_modif_timestamp(attr_dev_bus_file)  # Fecha de la última modif desde tto.
        # if not phi.os.path.isfile(attr_dev_bus_file):
        if not last_spbus_change_date:  # get_f_modif_timestamp devuelve None cuando el archivo no existe
            print(f"ERROR {__file__}\nNo se encuentra el archivo {attr_dev_bus_file}")
            print(f"Se actualiza con el valor leído en {xch_file_to_check}: {current_value}")
            try:
                with open(attr_dev_bus_file, "w") as f:
                    f.write(str(current_value))
            except FileNotFoundError as e:
                print(f"\n\tError guardando valor en spx_bus file\n{e}\n")
            stored_sp_bus_val = current_value
        else:
            with open(attr_dev_bus_file, "r") as f:
                stored_sp_bus_val = f.read().strip()  # Valor leído anteriormente en el dispositivo
        print(f"Valor almacenado en {attr_dev_bus_file} de {dev.name}: {stored_sp_bus_val} / "
              f"\t{type(stored_sp_bus_val)}")
        if not stored_sp_bus_val:
            stored_sp_bus_val = current_value
            with open(attr_dev_bus_file, "w") as f:
                print(f"Escribiendo por primera vez en {attr_dev_bus_file} de {dev.name}: {stored_sp_bus_val} / ")
                f.write(str(stored_sp_bus_val))

        modif_from_web = last_spbus_change_date < last_mod_time  # se ha modificado el archivo con el valor web
        # porque su fecha de modificación es posterior a la del archivo xxx_bus
        if float(stored_sp_bus_val) != current_value and not modif_from_web:  # El usuario ha cambiado la consigna.
            # Se actualizan con el nuevo valor los archivos spx, spx_bus y el dispositivo
            print(f"{dev.name} - Consigna {stored_sp_bus_val} cambiada en termostato a {current_value}")
            with open(attr_dev_bus_file, "w") as attdbf:
                attdbf.write(str(current_value))
            with open(xch_file_to_check, "w") as attdf:
                attdf.write(str(current_value))
            setattr(dev, attr, current_value)  # Se actualiza el atributo
            return 1
        elif float(xch_value) != current_value:  # Se ha cambiado desde la Web.
            # Se actualiza el archivo spx_bus
            print(f"{dev.name} - Consigna {stored_sp_bus_val} cambiada desde la web a {xch_value}")
            setattr(dev, attr, float(xch_value))  # Se actualiza el atributo
            print(f"Atributo {attr} actualizado desde la web a {getattr(dev, attr)} / {type(getattr(dev, attr))}")
            with open(attr_dev_bus_file, "w") as attdbf:
                attdbf.write(str(xch_value))  # Se actualiza el archivo spx_bus
            with open(xch_file_to_check, "w") as attdbf:
                attdbf.write(str(xch_value))  # Se actualiza el archivo de intercambio
            print("\n\tCOMPROBANDO ACTUALIZACIÓN DE ARCHIVO")
            with open(attr_dev_bus_file, "r") as attdbf:
                file_content = attdbf.read()
                print(f"\n\tValor guardado en el archivo spx_bus leído desde el termostato {file_content}")
            return 1
        else:
            print(f"No hay que actualizar {attr} en {dev.name}")
            return 0

    if None in (last_mod_time, last_exec_time):
        print(f"ERROR al recuperar las fechas de última modificación y última lectura:\n\t"
              f"Última modificación {xch_file_to_check}: {last_mod_time} - tipo {type(last_mod_time)}\n\t"
              f"Última ejecución: {last_exec_time} - tipo {type(last_exec_time)}")
        return 0

    print(f"Fechas de última modificación y última lectura:\n\t"
          f"Última modificación {xch_file_to_check}: {last_mod_time}\n\t"
          f"Última ejecución: {last_exec_time}")

    changes = False  # changes se refiere a los cambios por Web
    if attr not in class_rw_files:
        print(f"\n{attr} es de sólo lectura para {dev.name}. Se actualiza directamente el archivo "
              f"con el último valor del atributo leído: {current_value}")
        with open(xch_file_to_check, "w") as xchf:
            xchf.write(str(current_value))
        with open(xch_file_to_check, "r") as modf:
            new_web_value = modf.read().strip()
            print(f"\nComprobando si se ha escrito {current_value} en {xch_file_to_check}. "
                  f"Valor leído: {new_web_value}")

    elif last_mod_time > last_exec_time:  # Ha habido modificaciones desde la Web en atributo RW
        changes = True
        print(f"\nEl fichero:\t{xch_file_to_check}\tse ha modificado desde la última lectura\n")
        if not xch_value is None:
            if '(' in xch_value:  # Is Tuple
                val_to_write = tuple(map(int, xch_value.strip('()').split(', ')))
            elif '.' in xch_value:  # Is float
                val_to_write = float(xch_value)
            elif xch_value.isdecimal():  # Is int
                val_to_write = int(xch_value)
            else:
                val_to_write = str(xch_value)
            print(f"Actualizando el atributo {attr} del dispositivo {dev.name} con el valor {val_to_write}")
            setattr(dev, attr, val_to_write)
            print(f"Leyendo atributo tras escritura: {getattr(dev, attr)}")

            with open(xch_file_to_check, "w") as xchf:
                xchf.write(str(xch_value))
            with open(xch_file_to_check, "r") as modf:
                web_value = modf.read().strip()
                print(f"\nComprobando si se ha escrito {val_to_write} en {xch_file_to_check}. "
                      f"Valor leído: {web_value}")

    else:  # Se propaga el valor del atributo al archivo si ha cambiado
        changes = False
        if current_value != xch_value:
            print(f"No coincide el valor del archivo de intercambio, {xch_value} con el valor actual "
                  f"del atributo, {current_value}")
            print(f"Actualizando archivo de intercambio: {xch_file_to_check}")

            with open(xch_file_to_check, "w") as xchf:
                xchf.write(str(current_value))
            with open(xch_file_to_check, "r") as modf:
                new_web_value = modf.read().strip()
                print(f"\nComprobando si se ha escrito {current_value} en {xch_file_to_check}. "
                    f"Valor leído: {new_web_value}")
        else:
            print(f"No es necesario actualizar nada en {attr}")

    if changes:
        return 1
    return 0


async def update_all_rooms():
    """
    Actualiza los valores asociados a todos los objetos Room del proyecto.
    Returns: resultado de la actualización de las habitaciones
    """
    print(f"\n(update_all_rooms) Actualizando todos los objetos Room:\n")
    print("\n".join([r.name for r in phi.all_rooms.values()]))

    rooms_updating_tasks = [create_task(r.update())
                                for r in tuple(phi.all_rooms.values())]
    rooms_updating_results = await gather(*rooms_updating_tasks)
    print(f"Resultado de la actualización de todas las habitaciones (tupla de 1's): {rooms_updating_results}")
    # Actualizo el fichero con la información de las habitaciones
    phi.save_room_instances_file(phi.all_rooms)
    return rooms_updating_results


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


async def update_all_buses(device_type=None):
    """
    Actualiza los datos en todos los dispositivos en función de los valores calculados para los grupos de
    habitaciones
    Como las centralitas de suelo radiante (UFHCControlLer) ya se habían actualizado, si no se especifica
    "device_type", se actualizan todos los dispositivos excepto los UFHCControler
    Returns: 1
    Args:
        device_type (object): Si se especifica el nombre de un tipo de dispositivo, UFHCController por ejemplo,
        sólo se actualiza ese tipo de dispositivo
    """
    # webcheck = await check_changes_from_web()
    for idbus, bus in phi.buses.items():
        for iddevice, device in bus.items():
            dev_class = device.__class__.__name__
            if device_type and device_type != dev_class or device_type is None and dev_class == "UFHCController":
                continue

            print(f"\nActualizando valores del dispositivo {device.name}")
            update = await device.update()  # El método update toma los valores de las últimas lecturas
            if repr(device) is not None:
                print(repr(device))
            print(f"Finalizada actualización de {device.name} / {device.brand}_{device.model}")

    print(
        f"{__file__} (mbutils) \n\tACTUALIZANDO ARCHIVO buses CON INSTANCIAS DE LOS DISPOSITIVOS")
    save_devices_instances_file(phi.buses)
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
    dev_class = device.__class__.__name__  # Tipo de dispositivo UFHCController, Generator, Fancoil, Split,
    print(f"\n\n\nDEBUGGING - {device_class_names}\nActualizando ficheros de la clase {dev_class}\n\n")
    if dev_class not in device_class_names:
        print(f"ERROR {__file__} - La clase {dev_class} no corresponde a ninguna de las clases del "
              f"proyecto:\n{device_class_names}")
        return
    bus_id = device.bus_id  # el atributo bus_id pertenece en realidad a los dispositivos creados con herencias de
    # MBDevice, pero no pertenece a MBDevice
    slave = str(device.slave)  # Los archivos de intercambio van asociados a los números de esclavos de cada bus,
    # no al device_id definido en la base de datos del proyecto

    # HeatRecoveryUnit, AirZoneManager, TempFluidController
    attrs_to_update = phi.EXCHANGE_R_FILES.get(dev_class)  # Tupla con los archivos a actualizar (son los nombres
    # de los atributos)
    for attr in attrs_to_update:
        # attr_file = phi.EXCHANGE_FOLDER + r"/" + bus_id + r"/" + slave + r"/" + attr
        attr_file = f"{phi.EXCHANGE_FOLDER}/{bus_id}/{slave}/{attr}"
        if not path.isfile(attr_file):
            print(f"ERROR {__file__}\nNo se encuentra el archivo {attr_file}")
            continue
        attr_value = f"{getattr(device, attr)}"
        if attr_value not in (None, "None", ""):
            with open(attr_file, "w") as f:
                f.write(attr_value)
            with open(attr_file, "r") as f:
                read_value = f.read().strip()
            print(f"{device.name} - Intentando escribir {attr_value} en {attr_file}.\nValor guardado: {read_value}")


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
        # attr_file = phi.EXCHANGE_FOLDER + r"/" + bus_id + r"/" + slave + attr + r"/RW"
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

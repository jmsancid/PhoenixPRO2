#!/usr/bin/env python3
import phoenix_config as cfg
import phoenix_constants as cte
from devices.devices import MBDevice
from regops import regops
from asyncio import create_task, gather


async def read_device_datatype(device: MBDevice, regmap: dict, dtype: int) -> [dict, None]:
    """
    Módulo para leer todos los registros de un dispositivo de un determinado tipo
    Param: device: Dispositivo Modbus a leer
    Param: regmap: Mapa de registros del dispositivo
    Param: dtype: Tipo de datos a leer. Coincide con la operación de lectura ModBus
    Returns: diccionario con el número de registro (str) y el valor devuelto por el dispositivo
        None si no hay registros del tipo solicitado
    """
    modbus_operation = dtype
    regs = regmap.get(cte.MODBUS_DATATYPES_KEYS.get(dtype))  # Diccionario con todos los datos de tipo "dtype" del dispositivo
    # modbus_operation = cte.MODBUS_DATATYPES_KEYS.get(dtype)
    # regs = regmap.get(modbus_operation)  # Diccionario con todos los datos de tipo "dtype" del dispositivo
    if regs is not None:  # El dispositivo tiene registros del tipo "dtype"
        addresses = sorted([int(adr) for adr in regs.keys()])  # Lista ordenada de registros a leer
        # print(f"Registros del JSON: {addresses}")
        grouped_addresses = regops.group_adrs(addresses)  # Agrupo las direcciones de registros que van consecutivas
        # print(f"\nRegistros tipo {cte.MODBUS_DATATYPES[dtype]}: {grouped_addresses}")
        read_data = []
        for reggr in grouped_addresses:
            reading = await device.read(modbus_operation, reggr[0], reggr[1])
            if reading is not None:
                read_data += reading[:reggr[1]]  # Ajusto la cantidad de valores devueltos porque con COILS y
                # DISCRETE INPUTS la librería devuelve múltiplos de 8 valores y necesito que la respuesta coincida
                # con el número de registros solicitados
                # print(f"Lectura {cte.MODBUS_DATATYPES[dtype]}: {reading}")
        # print(f"Lectura completa: {read_data}")
        if read_data:
            adr_value_tuples = list(zip(addresses, read_data))
            for idx, result in enumerate(adr_value_tuples):
                regadr = str(result[0])  # En el JSON, los registros son keys y, por tanto, strings
                valor = result[1]
                funciones_de_conversion = regs[regadr].get("conv_f_read")
                if funciones_de_conversion is not None:
                    converted_val = regops.recursive_conv_f(funciones_de_conversion, valor, cte.TYPE_FLOAT, 1)
                    # print(f"El valor {valor} del registro {regadr} de tipo {cte.MODBUS_DATATYPES[dtype]} tiene " +\
                    #       f"un valor convertido de {converted_val}")
                    adr_value_tuples[idx] = (regadr, converted_val)
                else:
                    adr_value_tuples[idx] = (
                        str(regadr), valor)  # Hay que convertir a string la dirección del registro por
                    # ser keys en los JSON con los datos de los dispositivos
            # Convierto la lista de tuplas en un diccionario para facilitar el acceso a los datos
            results = {}
            results[cte.MODBUS_DATATYPES_KEYS.get(dtype)] = {}
            for data_pair in adr_value_tuples:
                results[cte.MODBUS_DATATYPES_KEYS.get(dtype)][data_pair[0]] = data_pair[1]
            cfg.collect()
            return results
        else:
            return  # Si el dispositivo no ha devuelto nada, se devuelve None
    else:
        return  # Si no hay registros del tipo "dtype" devuelve None


async def read_project_device(device: MBDevice) -> [str, None]:
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
    read_data = {cte.MODBUS_DATATYPES_KEYS[cte.COIL_ID]: [],
                 cte.MODBUS_DATATYPES_KEYS[cte.DISCRETE_INPUT_ID]: [],
                 cte.MODBUS_DATATYPES_KEYS[cte.HOLDING_REGISTER_ID]: [],
                 cte.MODBUS_DATATYPES_KEYS[cte.INPUT_REGISTER_ID]: []
                 }

    dev_regmap_key = f"{device.brand}_{device.model}"
    rmap = [x.rmap for x in cfg.mbregmaps if x.map_id == dev_regmap_key][0]  # Diccionario con el mapa modbus
    # del dispositivo
    # print(f"(read_project_device) - {rmap.keys()}")
    # print(f"(read_project_device) - {dev_regmap_key}")
    name = rmap.get("name")
    print(f"Nombre del dispositivo: {name}")
    rdngtask = [create_task(read_device_datatype(device, rmap, datatype))
                for datatype in tuple(cte.MODBUS_DATATYPES.keys())]

    readings = await gather(*rdngtask)

    # read_coils = read_device_datatype(device, rmap, cte.COIL_ID)
    # # print(f"COILS LEIDOS: {read_coils}")
    # if read_coils is not None:
    #     read_data[cte.MODBUS_DATATYPES_KEYS[cte.COIL_ID]] = read_coils
    #
    # read_discrete_inputs = read_device_datatype(device, rmap, cte.DISCRETE_INPUT_ID)
    # # print(f"DISCRETE_INPUTS LEIDOS: {read_discrete_inputs}")
    # if read_discrete_inputs is not None:
    #     read_data[cte.MODBUS_DATATYPES_KEYS[cte.DISCRETE_INPUT_ID]] = read_discrete_inputs
    #
    # read_holding_registers = read_device_datatype(device, rmap, cte.HOLDING_REGISTER_ID)
    # # print(f"HOLDING REGISTERS LEIDOS: {read_holding_registers}")
    # if read_holding_registers is not None:
    #     read_data[cte.MODBUS_DATATYPES_KEYS[cte.HOLDING_REGISTER_ID]] = read_holding_registers
    #
    # read_input_registers = read_device_datatype(device, rmap, cte.INPUT_REGISTER_ID)
    # # print(f"INPUT REGISTERS LEIDOS: {read_input_registers}")
    # if read_input_registers is not None:
    #     read_data[cte.MODBUS_DATATYPES_KEYS[cte.INPUT_REGISTER_ID]] = read_input_registers

    return readings
    # return cfg.json.dumps(read_data)

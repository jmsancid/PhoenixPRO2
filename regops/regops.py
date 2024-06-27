#!/usr/bin/env python3

"""
Operaciones a realizar con los registros modbus al leerlos o escribirlos para convertirlos
en sus valores reales
"""
from phoenix_constants import *
from typing import List, Tuple

# Diccionario con built-in functions para convertir los valores convertidos
# al formato deseado
ret_val = {TYPE_INT: int, TYPE_FLOAT: float, TYPE_STR: str}


# FUNCIONES DE CONVERSIÓN DE VALORES MODBUS A LEER O ESCRIBIR
def x10(val: [int, float, str], dtype=TYPE_INT, prec=1) -> [int, float, str]:
    """
    Multiplica por 10 el valor "val" y lo devuelve con el formato especificado
    en dtype. Por defecto devuelve un entero multiplicado por 10
    Params: val: valor a convertir. Puede ser int, float o str
            dtype: tipo de dato a devolver. 0=int, 1=float, 2=str
            prec: precisión del valor devuelto cuando es tipo float
    Returns: valx10
    """
    val_dtype = type(val).__name__
    if val_dtype in ["int", "float"]:
        val_to_ret = round(float(val) * 10, prec)
    elif val_dtype == "str":
        try:
            val_to_ret = round(float(val) * 10, prec)
        except ValueError:
            print(f"regops(función x10):{val} no es una cadena válida")
            return  # devuelve None
    else:
        print(f"regops(función x10):{val} no es un valor válido")
        return  # devuelve None

    return ret_val[dtype](val_to_ret)


def x10_1(val: [int, float, str], dtype=TYPE_INT, prec=1) -> [int, float, str]:
    """
    Divide entre 10 el valor "val" y lo devuelve con el formato especificado
    en dtype. Por defecto devuelve un entero dividido entre 10
    Params: val: valor a convertir. Puede ser int, float o str
            dtype: tipo de dato a devolver. 0=int, 1=float, 2=str
            prec: precisión del valor devuelto cuando es tipo float
    Returns: val/10
    """
    val_dtype = type(val).__name__
    if val_dtype in ["int", "float"]:
        val_to_ret = round(float(val) / 10, prec)
    elif val_dtype == "str":
        try:
            val_to_ret = round(float(val) / 10, prec)
        except ValueError:
            print(f"regops(función x10_1):{val} no es una cadena válida")
            return  # devuelve None
    else:
        print(f"regops(función x10_1):{val} no es un valor válido")
        return  # devuelve None

    # print("x10_1", ret_val[dtype](val_to_ret))
    return ret_val[dtype](val_to_ret)


def x100(val: [int, float, str], dtype=TYPE_INT, prec=1) -> [int, float, str]:
    """
    Multiplica por 100 el valor "val" y lo devuelve con el formato especificado
    en dtype. Por defecto devuelve un entero multiplicado por 100
    Params: val: valor a convertir. Puede ser int, float o str
            dtype: tipo de dato a devolver. 0=int, 1=float, 2=str
            prec: precisión del valor devuelto cuando es tipo float
    Returns: valx100
    """
    val_dtype = type(val).__name__
    if val_dtype in ["int", "float"]:
        val_to_ret = round(float(val) * 100, prec)
    elif val_dtype == "str":
        try:
            val_to_ret = round(float(val) * 100, prec)
        except ValueError:
            print(f"regops(función x100):{val} no es una cadena válida")
            return  # devuelve None
    else:
        print(f"regops(función x100):{val} no es un valor válido")
        return  # devuelve None

    # print("x100", ret_val[dtype](val_to_ret))
    return ret_val[dtype](val_to_ret)


def x10_2(val: [int, float, str], dtype=TYPE_INT, prec=1) -> [int, float, str]:
    """
    Divide entre 100 el valor "val" y lo devuelve con el formato especificado
    en dtype. Por defecto devuelve un entero dividido entre 100
    Params: val: valor a convertir. Puede ser int, float o str
            dtype: tipo de dato a devolver. 0=int, 1=float, 2=str
            prec: precisión del valor devuelto cuando es tipo float
    Returns: val/100
    """
    val_dtype = type(val).__name__
    if val_dtype in ["int", "float"]:
        val_to_ret = round(float(val) / 100, prec)
    elif val_dtype == "str":
        try:
            val_to_ret = round(float(val) / 100, prec)
        except ValueError:
            print(f"regops(función x10_2):{val} no es una cadena válida")
            return  # devuelve None
    else:
        print(f"regops(función x10_2):{val} no es un valor válido")
        return  # devuelve None

    # print("x10_2", ret_val[dtype](val_to_ret))
    return ret_val[dtype](val_to_ret)


def c_to_f(val: [int, float, str], dtype=TYPE_INT, prec=1) -> [int, float, str]:
    """
    Convierte a ºF el valor del argumento "val" expresado en ºC
    Params: val: valor a convertir. Puede ser int, float o str
            dtype: tipo de dato a devolver. 0=int, 1=float, 2=str
            prec: precisión del valor devuelto cuando es tipo float
    Returns: temperatura expresada en ºF
    """
    val_dtype = type(val).__name__
    if val_dtype in ["int", "float"]:
        val_to_ret = round(float(val) * 9 / 5, prec) + 32
    elif val_dtype == "str":
        try:
            val_to_ret = round(float(val) * 9 / 5, prec) + 32
        except ValueError:
            print(f"regops(función c_to_f):{val} no es una cadena válida")
            return  # devuelve None
    else:
        print(f"regops(función c_to_f):{val} no es un valor válido")
        return  # devuelve None

    # print("c_to_f", ret_val[dtype](val_to_ret))
    return ret_val[dtype](val_to_ret)


def f_to_c(val: [int, float, str], dtype=TYPE_INT, prec=1) -> [int, float, str]:
    """
    Convierte a ºC el valor del argumento "val" expresado en ºF
    Params: val: valor a convertir. Puede ser int, float o str
            dtype: tipo de dato a devolver. 0=int, 1=float, 2=str
            prec: precisión del valor devuelto cuando es tipo float
    Returns: temperatura expresada en ºC
    """
    val_dtype = type(val).__name__
    if val_dtype in ["int", "float"]:
        val_to_ret = round((float(val) - 32) * 5 / 9, prec)
    elif val_dtype == "str":
        try:
            val_to_ret = round((float(val) - 32) * 5 / 9, prec)
        except ValueError:
            print(f"regops(función f_to_c):{val} no es una cadena válida")
            return  # devuelve None
    else:
        print(f"regops(función f_to_c):{val} no es un valor válido")
        return  # devuelve None

    # print("f_to_c", ret_val[dtype](val_to_ret), "precision", prec)
    return ret_val[dtype](val_to_ret)


def get_hb_lb(val: int, *args) -> Tuple[int, int]:
    """
    Separa el valor 'val' en sus bytes alto y bajo
    Params: val: valor del que se van a obtener los bytes alto y bajo
    args: por compatibilidad con el resto de funciones a aplicar.
    Returns: tupla con los bytes alto y bajo de 'val'
    """
    hb, lb = val >> 8, val & 255
    return hb, lb


def set_hb(val: int, hb_new_val: int) -> int:
    """
    Escribe hb_new_val en el byte alto y devuelve el nuevo valor de 'val'
    Params: val: valor cuyo byte alto se va a actualizar
        hb_new_val: valor a escribir en el byte alto de 'val'
    Returns: valor 'val' actualizado
    """
    lb = val & 255
    val_to_ret = hb_new_val * 256 + lb
    return val_to_ret


def set_lb(val: int, lb_new_val: int) -> int:
    """
    Escribe lb_new_val en el byte bajo y devuelve el nuevo valor de 'val'
    Params: val: valor cuyo byte bajo se va a actualizar
        lb_new_val: valor a escribir en el byte bajo de 'val'
    Returns: valor 'val' actualizado
    """
    hb = val >> 8
    val_to_ret = hb * 256 + lb_new_val
    return val_to_ret


def get_bits(val: int) -> Tuple[int, ...]:
    """
    Devuelve una Tupla con los valores de los 16 bits de 'val'
    Param:
        val:
    Returns: Tupla con los valores de los 16 bits de 'val'
    """
    bin_val = bin(val)[2:]  # Elimino los 2 primeros caracteres que devuelve la función bin: '0b'
    # Completo con 0 hasta 16 bits, del 0 al 15
    bin_val = '0' * (16 - len(bin_val)) + bin_val
    # Inverto el orden de los bits y los separo en una lista
    bits = [int(bit) for bit in bin_val[::-1]]
    return tuple(bits)


def signed_integer(val: int, bits: int = 16) -> int:
    """
    Convierte un valor entero con signo en su valor correspondiente, positivo o negativo
    Param:
        val: entero con signo leído desde el dispositivo ModBus
    Returns: entero positivo o negativo en función del valor de val
    """
    if (val & (1 << (bits - 1))) != 0:
        val = val - (1 << bits)
    return val


# DICCIONARIO con las FUNCIONES DE CONVERSIÓN a aplicar a los registros
regops = {0: x10,  # Multiplica por 10 el valor
          1: x10_1,  # Divide entre 10 el valor
          2: x100,  # Multiplica por 100 el valor
          3: x10_2,  # Divide entre 100 el valor
          4: c_to_f,  # Convierte el valor de Celsius a Farenheit
          5: f_to_c,  # Convierte el valor de Farenheit a Celsius
          6: get_hb_lb,  # Obtiene los bytes alto y bajo del valor
          7: set_hb,  # Escribe un valor en el byte alto
          8: set_lb,  # Escribe un valor en el byte bajo
          9: get_bits,  # Devuelve una tupla con los valores de los 16 bits
          10: signed_integer  # Devuelve el valor positivo o negativo de un signed integer
          }


def recursive_conv_f(ops, val, dtype=TYPE_INT, prec=1):
    """
    Función a aplicar cuando a un determinado registro ModBus hay que
    aplicarle más de una modificación, por ejemplo, dividir por 10 y convertir de
    °F a °C
    Params: ops: lista o tupla con las operaciones a realizar sobre el registro
            val: valor leído por ModBus
            dtype: tipo de dato que se requiere devolver
            prec: precisión cuando el dato a devolver es de tipo float.
    Returns: Valor calculado tras aplicar todas las funciones
    """
    if type(ops).__name__ == 'int':
        val_to_ret = regops[ops](val, dtype, prec)
        # print(regops[ops], val_to_ret)
        return regops[ops](val, dtype, prec)
    val_to_ret = val
    for idx, op in enumerate(ops):
        if idx == len(ops) - 1:
            # print("última operación: ", op, dtype, prec)
            val_to_ret = regops[op](val_to_ret, dtype, prec)
            # print(regops[op], val_to_ret)
            return val_to_ret
        else:
            val_to_ret = regops[op](val_to_ret, 1, 2)  # Se devuelve float hasta la última conversion
            # print(f"valor tras conversion {idx+1}: {val_to_ret}")
            # print(regops[op], val_to_ret)


# ops = [1, 5]

# a = recursive_conv_f(ops, 698, 1, 3)
# print(a, type(a))

def group_adrs(regadrs: List) -> List[Tuple]:
    """
    Módulo para agrupar la lista de registros disponibles en un dispositivo ModBus de manera que
    se facilite la lectura del mismo.
    La lista de registros se convierte en una lista de tuplas en la que se indica cuántos registros van consecutivos.
    La tupla tiene 2 valores, el primer registro a leer y los que van consecutivos.
    Por ejemplo, la lista de registros [2, 3, 4, 12, 13, 17] se convertirá en [(2,3), (12,2) y (17,1)]
    Params: regadrs: Lista ordenada de menor a mayor con las direcciones de los registros a leer
    Returns: Lista de tuplas de 2 elementos en las que se separan los registros que van consecutivos.
    """
    # print(f"regops - regadrs: {regadrs}")

    adrgroups = [(reg, idx - reg) for idx, reg in enumerate(regadrs)]
    # print(f"regops - groupadrs: {adrgroups}")
    indexes = list(reversed(sorted(set([x[1] for x in adrgroups]))))
    index_count = [(x, [val[1] for val in adrgroups].count(x)) for x in indexes]
    # print(index_count)
    newgroups = []
    prev_idx = 0
    for idx, val in enumerate(index_count):
        if idx == 0:
            quan = val[1]
            newgroups.append((regadrs[idx], quan))
            prev_idx = quan
        else:
            # print(f"reg_idx: {prev_idx}")
            newgroups.append((regadrs[prev_idx], val[1]))
            prev_idx += val[1]

    # print(newgroups)
    return newgroups

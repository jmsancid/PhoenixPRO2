#!/usr/bin/env python3

"""
Operaciones a realizar con los registros modbus al leerlos o escribirlos para convertirlos
en sus valores reales
"""
import math

import phoenix_constants as cte
from typing import List, Tuple

# Diccionario con built-in functions para convertir los valores convertidos
# al formato deseado
ret_val = {cte.TYPE_INT: int, cte.TYPE_FLOAT: float, cte.TYPE_STR: str}


# FUNCIONES DE CONVERSIÓN DE VALORES MODBUS A LEER O ESCRIBIR
def x10(val: [int, float, str], dtype=cte.TYPE_INT, prec=1) -> [int, float, str]:
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


def x10_1(val: [int, float, str], dtype=cte.TYPE_INT, prec=1) -> [int, float, str]:
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


def x100(val: [int, float, str], dtype=cte.TYPE_INT, prec=1) -> [int, float, str]:
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


def x10_2(val: [int, float, str], dtype=cte.TYPE_INT, prec=1) -> [int, float, str]:
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


def c_to_f(val: [int, float, str], dtype=cte.TYPE_INT, prec=1) -> [int, float, str]:
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


def f_to_c(val: [int, float, str], dtype=cte.TYPE_INT, prec=1) -> [int, float, str]:
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


# DICCIONARIO con las FUNCIONES DE CONVERSIÓN a aplicar a los registros
regops = {0: x10,  # Multiplica por 10 el valor
          1: x10_1,  # Divide entre 10 el valor
          2: x100,  # Multiplica por 100 el valor
          3: x10_2,  # Divide entre 100 el valor
          4: c_to_f,  # Convierte el valor de Celsius a Farenheit
          5: f_to_c  # Convierte el valor de Farenheit a Celsius
          }


def recursive_conv_f(ops, val, dtype=cte.TYPE_INT, prec=1):
    """
    Función a aplicar cuando a un determinado registro ModBus hay que
    aplicarle más de una modificación, por ejemplo, dividir por 10 y convertir de
    ºF a ºC
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

    adrgroups = [(reg, id - reg) for id, reg in enumerate(regadrs)]
    # print(adrgroups)
    indexes = list(reversed(sorted(set([x[1] for x in adrgroups]))))
    index_count = [(x, [val[1] for val in adrgroups].count(x)) for x in indexes]
    # print(index_count)
    newgroups = []
    for idx, val in enumerate(index_count):
        if idx == 0:
            newgroups.append((regadrs[idx], val[1]))
        else:
            newgroups.append((regadrs[idx + index_count[idx - 1][1] - 1], val[1]))

    # print(newgroups)
    return newgroups

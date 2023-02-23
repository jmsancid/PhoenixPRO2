#!/usr/bin/env python3
"""
Lista de constantes del sistema
"""
import os

# SERIAL COMMUNICATION PORT
SERIAL_PORT = "/dev/ttySC0"

#   CONVERSION FUNCTION CONSTANTS

TYPE_INT = 0
TYPE_FLOAT = 1
TYPE_STR = 2

#   MODBUS CONSTANTS
COIL_ID = 1
DISCRETE_INPUT_ID = 2
HOLDING_REGISTER_ID = 3
INPUT_REGISTER_ID = 4
# Tipos de dato ModBus para las operaciones de lectura y escritura
MODBUS_DATATYPES = {1: "COILS", 2: "DISCRETE_INPUTS", 3: "HOLDING REGISTERS", 4: "INPUT REGISTERS"}
MODBUS_READ_OPERATIONS = {"COILS": 1, "DISCRETE_INPUTS": 2, "HOLDING_REGISTERS": 3, "INPUT_REGISTERS": 4}
MODBUS_WRITE_OPERATIONS = {"SINGLE_COIL": 5, "SINGLE_REGISTER": 6, "MULTIPLE_COILS": 15, "MULTIPLE_REGISTERS": 16}
# Tipos de dato ModBus utilizados como claves en los JSON con los mapas de registros de los dispositivos
MODBUS_DATATYPES_KEYS = {COIL_ID: "co",
                         DISCRETE_INPUT_ID: "di",
                         HOLDING_REGISTER_ID: "hr",
                         INPUT_REGISTER_ID: "ir"}
PARITY_NONE = None if "esp32" in os.uname().sysname else "N"
PARITY_EVEN = 0 if "esp32" in os.uname().sysname else "E"
PARITY_ODD = 1 if "esp32" in os.uname().sysname else "O"
PARITY = {"N": PARITY_NONE, "E": PARITY_EVEN, "O": PARITY_ODD}  # Hace falta el diccionario para utilizar el
# formato correcto de paridad cuando se trabaja con la ESP32 (main.load_devices)
READING_TRIES = 5  # Nº máximo de intentos de lectura de un dispositivo

# JSON DE CONFIGURACIÓN DEL PROYECTO
CONFIG_FILE = "./temp_project.json"
DEVICES_FOLDER = "./devices/"
TEMP_DIR = "/home/pi/var/tmp/phoenix/"
READINGS_FILE = TEMP_DIR + "modbus_readings.json"
ROOMGROUPS_VALUES_FILE = TEMP_DIR + "roomgroups_values.json"


# CONFIG_FILE = "./project.json"

# JSON CON LOS OBJETOS DEL PROYECTO
SENSORDB = "./project_elements/sensors.json"
GENERATORDB = "./project_elements/generators.json"
FANCOILDB = "./project_elements/fancoils.json"
SPLITDB = "./project_elements/splits.json"
HEATRECOVERYUNITDB = "./project_elements/heatrecoveryunits.json"
AIRZONEMANAGERDB = "./project_elements/airzonemanagers.json"
TEMPFLUIDCONTROLLERDB = "./project_elements/tempfluidcontrollers.json"

# DICCIONARIO PARA ACCEDER A LOS JSON CON LOS OBJETOS DEL PROYECTO
PRJ_DEVICES_DB = {
    "RoomSensor": SENSORDB,
    "Generator": GENERATORDB,
    "Fancoil": FANCOILDB,
    "Split": SPLITDB,
    "HeatRecoveryUnit": HEATRECOVERYUNITDB,
    "AirZoneManager": AIRZONEMANAGERDB,
    "TempFluidController": TEMPFLUIDCONTROLLERDB
}

# VARIABLES PARA CÁLCULO DE TEMPERATURA DE IMPULSIÓN DE AGUA
TMIN_HAB_CALEF = 29  # Temperatura mínima para habilitar bombas en calefacción
TMAX_HAB_REFR = 19  # Temperatura maxima para habilitar bombas en refrigeracion
OFFSET_DEMANDA_CALEFACCION = 2  # Con más de 2 °C de diferencia entre consigna y t_actual, t_impul más alta
OFFSET_DEMANDA_REFRIGERACION = 1  # Con más de 1 °C de diferencia entre t_actual y consigna, t_impul más baja
OFFSET_AGUA_CALEFACCION = 10  # Diferencia entre consigna ambiente y agua en calefaccion
OFFSET_AGUA_REFRIGERACION = 8  # Diferencia entre consigna agua y ambiente en refrigeracion
OFFSET_AGUA_T_ROCIO = -1.5  # Limitacion t impulsion respecto pto de rocio en modo refrigeracion
TMAX_IMPUL_CALEF = 45  # Temperatura máxima de impulsión en calefacción
TMIN_IMPUL_REFR = 13  # Temperatura mínima de impulsión en refrigeración
RT_LIM_CALEF = 26
RT_LIM_REFR = 20
ALTITUD = 696

DEFAULT_TEMP_EXTERIOR_VERANO = 35  # Valor entre junio y septiembre
DEFAULT_TEMP_EXTERIOR_INVIERNO = 3  # Valor resto del año

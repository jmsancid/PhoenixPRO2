#!/usr/bin/env python3
"""
Lista de constantes del sistema
"""
import os

# SERIAL COMMUNICATION PORT
# SERIAL_PORTS = {1: "/dev/ttyUSB0"}
SERIAL_PORTS = {1: "/dev/ttySC0", 2: "/dev/ttySC0"}

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

# VALORES PARA LAS SALIDAS DE RELÉ DE LOS CONTROLADORES DE SISTENA
ON = 1
OFF = 0
OPEN = 1
CLOSED = 0

# VALORES PARA LOS MODOS CALEFACCIÓN (HEATING) / REFRIGERACIÓN (COOLING)
COOLING = 1
HEATING = 0
IV = "iv"  # Archivo para almacenar el modo de funcionamiento calefacción/refrigeración bajo home/pi/var/tmp/reg/<dev>

# JSON DE CONFIGURACIÓN DEL PROYECTO
MODULE_PATH = os.path.realpath(os.path.dirname(__file__))
CONFIG_FILE = MODULE_PATH + r"/project.json"
DEVICES_FOLDER = MODULE_PATH + r"/devices/"
TEMP_FOLDER = "/home/pi/var/tmp/phoenix/"
READINGS_FILE = TEMP_FOLDER + "modbus_readings.json"
ROOMGROUPS_VALUES_FILE = TEMP_FOLDER + "roomgroups_values.json"
ROOMGROUPS_INSTANCES_FILE = TEMP_FOLDER + "roomgroups.pickle"
BUSES_INSTANCES_FILE = TEMP_FOLDER + "buses.pickle"
REGMAP_INSTANCES_FILE = TEMP_FOLDER + "regmaps.pickle"

# CONFIG_FILE = "./project.json"

# JSON CON LOS OBJETOS DEL PROYECTO
UFHCCONTROLLERDB = MODULE_PATH + r"/project_elements/ufhccontrollers.json"
GENERATORDB = MODULE_PATH + r"/project_elements/generators.json"
FANCOILDB = MODULE_PATH + r"/project_elements/fancoils.json"
SPLITDB = MODULE_PATH + r"/project_elements/splits.json"
HEATRECOVERYUNITDB = MODULE_PATH + r"/project_elements/heatrecoveryunits.json"
AIRZONEMANAGERDB = MODULE_PATH + r"/project_elements/airzonemanagers.json"
TEMPFLUIDCONTROLLERDB = MODULE_PATH + r"/project_elements/tempfluidcontrollers.json"

# DICCIONARIO PARA ACCEDER A LOS JSON CON LOS OBJETOS DEL PROYECTO
PRJ_DEVICES_DB = {
    "UFHCController": UFHCCONTROLLERDB,
    "Generator": GENERATORDB,
    "Fancoil": FANCOILDB,
    "Split": SPLITDB,
    "HeatRecoveryUnit": HEATRECOVERYUNITDB,
    "AirZoneManager": AIRZONEMANAGERDB,
    "TempFluidController": TEMPFLUIDCONTROLLERDB
}

# VARIABLES PARA CÁLCULO DE TEMPERATURA DE IMPULSIÓN DE AGUA
TMAX_ACS = 60  # Temperatura máxima para la consigna de ACS
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

# VARIABLES PARA CÁLCULO DE CONSIGNA DE FANCOILS
OFFSET_COOLING = 0.5
OFFSET_HEATING = -1.5

# DIFERENCIA MÍNIMA ENTRE EL VALOR DE TEMPERATURA DEL GRUPO DE HABITACIONES Y PUNTO DE ROCÍO DEL GRUPO
# SI TEMP_GRUPO + OFFSET_ACTIVACION_DESHUMIDIFICACON < TEMP_ROCIO_GRUPO ==> SE ACTIVA DESHUMIDIFICACION
OFFSET_ACTIVACION_DESHUMIDIFICACION = 1
TEMP_ACTIVACION_DESHUMIDIFICACION = 14.5
MAX_HRU_SPEED = 3
HRU_VENTILATION_SPEED = 2  # Velocidad por defecto en modo ventilación
HRU_VENTILATION_AFLOWPCT = 50  # Porcentaje del caudal máximo del recuperador a aplicar por defecto en ventilación
AIR_QUALITY_DEFAULT_SETPOINT = 500

# MODO OFF = 0
DESHUMIDIFICACION = 1
FANCOIL = 2
FREE_COOLING = 4
DH_FREEC = 5  # Deshumidificación más freecooling
FC_FREEC = 6  # Fancoil más freecooling
VENTILACION = 8

# DIRECTORIO PARA ALMACENAR LOS ARCHIVOS DE INTERCAMBIO CON LA WEB DE SIGEEN:
EXCHANGE_FOLDER = r"/home/pi/var/tmp/reg"
TEMP_EXT_FILE = EXCHANGE_FOLDER + "/1/1000/temp"
HR_EXT_FILE = EXCHANGE_FOLDER + "/1/2000/humd"

UFHCCONTROLLER_R_FILES = ('iv', 'pump',
                          'sp1', 'sp2', 'sp3', 'sp4', 'sp5', 'sp6', 'sp7', 'sp8', 'sp9', 'sp10', 'sp11', 'sp12',
                          'rt1', 'rt2', 'rt3', 'rt4', 'rt5', 'rt6', 'rt7', 'rt8', 'rt9', 'rt10', 'rt11', 'rt12',
                          'rh1', 'rh2', 'rh3', 'rh4', 'rh5', 'rh6', 'rh7', 'rh8', 'rh9', 'rh10', 'rh11', 'rh12',
                          'ft1', 'ft2', 'ft3', 'ft4', 'ft5', 'ft6', 'ft7', 'ft8', 'ft9', 'ft10', 'ft11', 'ft12',
                          'st1', 'st2', 'st3', 'st4', 'st5', 'st6', 'st7', 'st8', 'st9', 'st10', 'st11', 'st12',
                          'coff1', 'coff2', 'coff3', 'coff4', 'coff5', 'coff6', 'coff7', 'coff8', 'coff9',
                          'coff10', 'coff11', 'coff12',
                          'dp1', 'dp2', 'dp3', 'dp4', 'dp5', 'dp6', 'dp7', 'dp8', 'dp9', 'dp10', 'dp11', 'dp12',
                          'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9', 'h10', 'h11', 'h12')
UFHCCONTROLLER_RW_FILES = ('iv', 'sp1', 'sp2', 'sp3', 'sp4', 'sp5', 'sp6', 'sp7', 'sp8', 'sp9', 'sp10', 'sp11', 'sp12',
                           'coff1', 'coff2', 'coff3', 'coff4', 'coff5', 'coff6', 'coff7', 'coff8', 'coff9',
                           'coff10', 'coff11', 'coff12')
GENERATOR_R_FILES = ("onoff_st", "manual_onoff_mode", "manual_onoff", "sp", "manual_sp_mode", "manual_sp",
                     "dhwsp", "iv", "manual_iv_mode", "manual_iv", "alarm", "t_ext", "supply_water_temp",
                     "return_water_temp", "t_inercia", "water_flow",
                     "eelectrica_consumida", "ecooling_consumida", "eheating_consumida", "edhw_consumida",
                     "cop", "eer")
GENERATOR_RW_FILES = ("manual_onoff_mode", "manual_onoff", "manual_sp_mode", "manual_sp", "dhwsp",
                      "manual_iv_mode", "manual_iv")

FANCOIL_R_FILES = ('onoff_st', 'demand', 'iv', 'sp', 'rt',
                   'fan_auto_cont', 'fan_speed', 'actmanual_fan', 'manual_speed', 'speed_limit',
                   'valv_st', 'manual_valv_st', 'manual_valv_pos', 'remote_onoff', 'sd_aux', 'floor_temp')
FANCOIL_RW_FILES = ('fan_auto_cont', 'actmanual_fan', 'manual_speed', 'speed_limit', 'manual_valv_st',
                    'manual_valv_pos', 'remote_onoff', 'sd_aux')
SPLIT_R_FILES = ()
SPLIT_RW_FILES = ()
HEATRECOVERYUNIT_R_FILES = ("onoff", "manual", "manual_speed", "hru_mode", "man_hru_mode_st", "man_hru_mode", "speed",
                            "manual_airflow", "supply_flow", "exhaust_flow", "valv_st", "bypass_st", "dampers_st",
                            "remote_onoff", "aux_ed2_st", "aux_ed3_st")
HEATRECOVERYUNIT_RW_FILES = ("onoff", "manual", "manual_speed", "manual_airflow", "man_hru_mode_st", "man_hru_mode")

AIRZONEMANAGER_R_FILES = ("iv", "sp", "rt", "sp1", "rt1", "sp2", "rt2",
                          "fan_auto_cont", "fan_speed", "damper1_st", "damper2_st",
                          "demand", "remote_onoff",
                          "ed1_aux", "ed2_aux", "ed3_aux")
AIRZONEMANAGER_RW_FILES = ("fan_auto_cont", "fan_speed", "remote_onoff")
TEMPFLUIDCONTROLLER_R_FILES = ('iv1', 'st1', 'act_man_st1', 'man_st1', 'sp1', 'act_man_sp1', 'man_sp1', 'ti1', 'v1',
                               'iv2', 'st2', 'act_man_st2', 'man_st2', 'sp2', 'act_man_sp2', 'man_sp2', 'ti2', 'v2',
                               'iv3', 'st3', 'act_man_st3', 'man_st3', 'sp3', 'act_man_sp3', 'man_sp3', 'ti3', 'v3',
                               'st4')
TEMPFLUIDCONTROLLER_RW_FILES = ('iv1', 'act_man_st1', 'man_st1', 'act_man_sp1', 'man_sp1',
                                'iv2', 'act_man_st2', 'man_st2', 'act_man_sp2', 'man_sp2',
                                'iv3', 'act_man_st3', 'man_st3', 'act_man_sp3', 'man_sp3',
                                'st4')
DATASOURCE_R_FILES = ('dato1', 'dato2', 'dato3', 'dato4', 'dato5', 'dato6', 'dato7', 'dato8', 'dato9', 'dato10')
DATASOURCE_RW_FILES = ()
# ARCHIVOS DE INTERCAMBIO DE INFORMACIÓN CON LA WEB
EXCHANGE_R_FILES = {
    "UFHCController": UFHCCONTROLLER_R_FILES,
    "Generator": GENERATOR_R_FILES,
    "Fancoil": FANCOIL_R_FILES,
    "Split": SPLIT_R_FILES,
    "HeatRecoveryUnit": HEATRECOVERYUNIT_R_FILES,
    "AirZoneManager": AIRZONEMANAGER_R_FILES,
    "TempFluidController": TEMPFLUIDCONTROLLER_R_FILES,
    "DataSource": DATASOURCE_R_FILES
}
EXCHANGE_RW_FILES = {
    "UFHCController": UFHCCONTROLLER_RW_FILES,
    "Generator": GENERATOR_RW_FILES,
    "Fancoil": FANCOIL_RW_FILES,
    "Split": SPLIT_RW_FILES,
    "HeatRecoveryUnit": HEATRECOVERYUNIT_RW_FILES,
    "AirZoneManager": AIRZONEMANAGER_RW_FILES,
    "TempFluidController": TEMPFLUIDCONTROLLER_RW_FILES,
    "DataSource": DATASOURCE_RW_FILES
}

#!/usr/bin/env python3
import asyncio
import sys
import time

# import sys

import phoenix_init as phi

from mb_utils.mb_utils import (read_all_buses, update_roomgroups_values, update_all_buses, update_all_rooms,
                               get_all_fancoils_st, get_all_ufhc_actuators_st)


# from publish.publish_results import publish_results

async def main():
    print(f"\n\t\tAccediendo al controlador {phi.boardsn}\n")

    # changes = await check_changes_from_web()

    id_lectura_actual = 0
    historico_lecturas = {"lecturas": {}}

    phi.collect()

    id_lectura_actual += 1
    print(f"\n************\t INICIANDO LECTURA {id_lectura_actual}\t************\n")
    # Actualizo el diccionario con las lecturas modbus, para recalcular los grupos de habitaciones y otras variables
    phi.datadb = await read_all_buses(id_lectura_actual)  # Diccionario READING_FILE con la última lectura de
    # todos los registros
    print(f"\n************\t LECTURA MODBUS FINALIZADA {id_lectura_actual}\t************\n")


    phi.system_iv = await phi.get_modo_iv()  # Variable global con el modo de funcionamiento del sistema
    print("==========================================================\n")
    print(f"\n\tMODO de funcionamiento del sistema: {phi.system_iv}\n")
    print("==========================================================\n")


    print(f"\n************\t ACTUALIZANDO CENTRALITAS X148 {str(phi.datetime.now())}\t************\n")
    # Actualizo las instancias de los Controladores de suelo radiante con las últimas lecturas
    bus_updating_results = await update_all_buses("UFHCController")
    print(f"\n************\t FINALIZADA ACTUALIZACIÓN CENTRALITAS X148 {str(phi.datetime.now())}\t************\n")

    print(f"\n************\t COMPROBANDO CAMBIOS EN LA WEB {str(phi.datetime.now())}\t************\n")

    # Tras leer los buses y actualizar las centralitas de suelo radiante "UFHCController",
    # compruebo si ha habido algún cambio desde la web: modos manuales, etc.
    print("\t\t Se ha cambiado la forma de comprobar los cambios por web JSC 19/06/2024")
    # changes = await check_changes_from_web()

    # Se sustituye por la nueva versión de check_changes_from_web con el
    # bus, dispositivo y atributo como parámetros. Se comprueba por separado para cada dispositivo

    print(f"\n************\t FINALIZADA COMPROBACIÓN CAMBIOS EN LA WEB {str(phi.datetime.now())}\t************\n")

    print(f"\n************\t ACTUALIZANDO TODAS LAS HABITACIONES {str(phi.datetime.now())}\t************\n")
    # Actualizo las lecturas de todas las habitaciones y grupos de habitaciones del proyecto
    rooms_updating_results = await update_all_rooms()

    print(f"\n************\t "
          f"FINALIZADA ACTUALIZACIÓN DE TODAS LAS HABITACIONES {str(phi.datetime.now())}"
          f"\t************\n")

    print(f"\n************\t ACTUALIZANDO GRUPOS DE HABITACIONES {str(phi.datetime.now())}\t************\n")
    # Actualizo las lecturas de todas las habitaciones y grupos de habitaciones del proyecto
    roomgroup_updating_results = await update_roomgroups_values()

    print(f"\n************\t FINALIZADA ACTUALIZACIÓN GRUPOS DE HABITACIONES {str(phi.datetime.now())}\t************\n")

    # Propago los valores calculados a los dispositivos del proyecto
    bus_updating_results = await update_all_buses()

    algun_actuador_abierto = await get_all_ufhc_actuators_st()
    msg = "Hay algun actuador abierto" if algun_actuador_abierto else "Todos los actuadores están cerrados"
    print(f"\n\n{msg}\n\n")

    algun_fancoil_activo = await get_all_fancoils_st()
    msg = "Hay algun fancoil activo" if algun_fancoil_activo else "Ningún fancoil activo"
    print(f"\n\n{msg}\n\n")


    # print(f"Free Memory: {micropython.mem_info(1)}")
    phi.collect()

if __name__ == "__main__":
    asyncio.run(main())
    end_time = phi.datetime.now()
    print(f"Hora finalización: {str(end_time)}\nDuración: {str(end_time - phi.init_time)}")

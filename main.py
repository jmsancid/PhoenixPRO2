#!/usr/bin/env python3
import asyncio

import phoenix_init as phi

from mb_utils.mb_utils import read_all_buses, update_roomgroups_values, update_all_buses, check_changes_from_web


# from publish.publish_results import publish_results

async def main():
    print(f"\n\t\tAccediendo al controlador {phi.boardsn}\n")

    changes = await check_changes_from_web()

    id_lectura_actual = 0
    historico_lecturas = {"lecturas": {}}

    phi.collect()
    id_lectura_actual += 1
    print(f"\n************\t INICIANDO LECTURA {id_lectura_actual}\t************\n")

    # Actualizo el diccionario con las lecturas modbus, para recalcular los grupos de habitaciones y otras variables
    phi.datadb = await read_all_buses(id_lectura_actual)  # Diccionario READING_FILE con la última lectura de
    # todos los registros

    # Actualizo las lecturas de todas las habitaciones y grupos de habitaciones del proyecto
    roomgroup_updating_results = await update_roomgroups_values()

    # Propago los valores calculados a los dispositivos del proyecto
    bus_updating_results = await update_all_buses()

    # print(f"Free Memory: {micropython.mem_info(1)}")
    phi.collect()



if __name__ == "__main__":
    asyncio.run(main())
    end_time = phi.datetime.now()
    print(f"Hora finalización: {str(end_time)}")

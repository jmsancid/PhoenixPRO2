#!/usr/bin/env python3
import asyncio
import sys
import time
from datetime import datetime

import json
import phoenix_config as cfg

from mb_utils.mb_utils import read_project_device

from publish.publish_results import publish_results


async def main():
    init_time = datetime.now()
    print(f"Hora inicio: {str(init_time)}")
    print(f"\n\t\tAccediendo al controlador {cfg.boardsn}\n")

    id_lectura_actual = 0
    historico_lecturas = {"lecturas": {}}

    while True:
        cfg.collect()
        id_lectura_actual += 1
        print(f"\n************\t INICIANDO LECTURA {id_lectura_actual}\t************\n")
        hora_lectura = datetime.now()  # Hora actual en formato datetime

        # historico_lecturas["lecturas"][id_lectura_actual] = {}
        lectura_actual = {
            "id": id_lectura_actual,
            "hora": str(hora_lectura),
            "buses": {}
        }
        for idbus, bus in cfg.buses.items():
            lectura_actual["buses"][idbus] = {}
            for iddevice, device in bus.items():
                lectura_actual["buses"][idbus][iddevice] = {}
                lectura_actual["buses"][idbus][iddevice]["slave"]= device.slave
                # Lee el dispositivo completo y almacena la información en un fichero en memoria StringIO?
                device_readings = await read_project_device(device)
                print(f"\n{str(datetime.now())}\nDuración:\t{str(datetime.now() - hora_lectura)}\n")
                lectura_actual["buses"][idbus][iddevice]["data"]= {}
                for regtype_readings in device_readings:
                    for regtype, dev_response in regtype_readings.items():
                        lectura_actual["buses"][idbus][iddevice]["data"][regtype] = dev_response
                print(lectura_actual)
        cfg.datadb = lectura_actual  # Diccionario con todas las lecturas
        results = repr(cfg.all_rooms.get("1"))
        # publica(results)
        print(results)
        # print(f"Free Memory: {micropython.mem_info(1)}")
        cfg.collect()
        time.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())

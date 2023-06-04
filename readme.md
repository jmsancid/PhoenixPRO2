# ESPECIFICACIÓN DE DISEÑO DE SOFTWARE
<p>
El JSON con la configuración del proyecto tendrá la información dividida en 2 grupos:
</p>
<ul>
<li>Edificio(s)</li>
<li>Buses</li>
</ul>
<p>
<strong>No puede haber 2 buses con la misma "id" aunque pertenezcan a edificios 
distintos.</strong>
</p>
<p>
A nivel de programa, la unidad en torno a la que gira todo es la Room (habitación).
Cada Room pertenece como mínimo a 3 grupos:
</p>
<ul>
<li>El del edificio al que pertenece la vivienda. El "id" del grupo de habitaciones asociado al edificio es 
el "id" del edificio.</li>
<li>El de la vivienda a la que pertenece. El "id" del grupo de habitaciones asociado a la vivienda es el 
"id" del edificio multiplicado por 100.000 y sumándole el "id" de la vivienda multiplicado por 100.</li>
<li>El formado por ella misma. El "id" del grupo que constituye la propia habitación es el de la 
vivienda, sumándole el "id" de la habitación.</li>
</ul>
<p>Al instanciar las Rooms en el momento de cargar la configuración del proyecto, el objeto generado 
se añade como elemento a una lista y dicha lista es el valor del diccionario que contiene todas las 
habitaciones del edificio y en el que las claves son los "id"'s de cada grupo.</p>
<p>Adicionalmente puede haber grupos de habitaciones dentro de una misma vivienda o grupos formados 
por varias viviendas.</p>
<p>En definitiva, una vivienda y un edificio son un grupo de habitaciones.</p>
<p>El nexo entre las viviendas y los dispositivos ModBus es el grupo al que están asociados</p>
<p>Todos y cada uno de los dispositivos se definen dentro de la clave "buses" y un atributo de cada 
dispositivo es el grupo de habitaciones que lleva asociado</p>
<p>El objeto RoomGroup (grupo de habitaciones) dispone de métodos que permiten calcular la temperatura 
de impulsión de agua para la instalación de suelo radiante de ese grupo de habitaciones, o la consigna 
y el valor de la temperatura de aire a propagar a un fancoil asociado a más de una habitación, o la 
demanda térmica del grupo, etc.</p>
<p>
Habrá 2 grupos de ficheros JSON con datos:
</p>
<li>
En el paquete <strong>devices</strong> se almacenan los JSON de cada dispositivo 
del sistema del que se tiene el mapa de registros ModBus. 
<strong>Es imprescindible que los dispositivos ModBus estén definidos dentro del paquete de 
dispositivos: devices.</strong> 
Se importarán al proyecto aquellos dispositivos que aparezcan definidos en el JSON 
del proyecto.
Los JSON de los dispositivos modbus incluyen información como las operaciones de 
escritura admitidas ("wop"), el máximo número de registros a leer ("qregmax"), que en algunos dispositivos está limitado
y el mapa de registros separados por tipo de registro: 
"co"=coils/1, "di"=discrete inputs/2, "hr"=holding registers/3 y "ir"=input registers/4.
Por ejemplo, en la centralita Uponor X148, el máximo número de registros que se pueden leer es 24.
Cada registro será la clave de otro subnivel que incluirá la descripción del registro 
en español, portugués e inglés y la operación a realizar con el registro al leer (conv_f_read) y 
al escribir (conv_f_write), por ejemplo, dividir por 10 o multiplicar por 10, convertir de °C a °F o 
viceversa, etc. 
Las operaciones estarán definidas por una lista (array) de números enteros y almacenadas 
en un diccionario y fichero aparte dentro del fichero <strong>regops.py</strong>. 
Las operaciones contenidas en la lista se ejecutan secuencialmente, e.g., si conv_f_read de un
determinado registro tiene el valor [1, 5] quiere decir que el registro leído hay que dividirlo primero por 10,
operación 1, y luego pasarlo a grados Farenheit, operación 5.
La función que realiza esa secuencia se denomina <strong>recursive_conv_f</strong> y se 
llama desde la función <strong>mb_utils.read_device_datatype,</strong> que extrae de "datadb" 
los valores leídos en el dispositivo ModBus.</li>
<li>
Proyecto propiamente dicho, con los objetos Proyecto, Edificio, Vivienda, Habitacion, 
Grupo de Habitaciones, Generador, Fancoil, Split, Recuperador, Zonificador, Contador...
A efectos de programación, Edificios y Viviendas son grupos de habitaciones (RoomGroup) identificados 
por un número que permite hacer cálculos sobre ellos.
El JSON de proyecto está estructurado en forma de árbol con 2 grupos de datos:
<ul>
<dl>
<dt >Edificio</dt>
<dd>
<p>En los datos asociados al edificio se definen las viviendas que lo componen y las habitaciones que 
hay en cada vivienda.</p>
<p>También estarán asociadas a cada edificio magnitudes físicas del ambiente exterior bajo la clave 
"o_data":</p>
<ul>
<li>Temperatura exterior</li>
<li>Humedad relativa exterior</li>
<li>Calidad del aire exterior</li>
</ul>
<p>Dichas magnitudes se expresan en función del origen de los datos, "magnitud_source". </p>
<p>Como dicho origen puede ser variado: dispositivo modbus, internet, etc., "magnitud_source" será a 
su vez la clave de otro documento que tendrá como clave el tipo de origen del dato: mbdev, web, ... y 
como valor la información necesaria para obtener el dato. Será necesario crear funciones en phoenix_config.py 
que permitan acceder a esa información cuando no proceda de un dispositivo ModBus.</p>
<p>Cada habitación a su vez contiene un identificador, "id", una descripción, "name", una lista con 
los grupos de habitaciones a los que pertenece y la información relativa a los dispositivos desde los 
que obtener el modo de funcionamiento frío/calor, "iv", la temperatura exterior, "te", la consigna, "sp", 
la temperatura ambiente, "rt", el estado del actuador, "st", el caudal de aire asociado a la habitación 
en los sistemas de zonificación, "af", el valor de la calidad de aire "aq" y la consigna de calidad de 
aire "aqsp".</p>
<p>La lista que define los grupos de habitaciones a los que pertenece una determinada habitación tendrá 
como mínimo 3 valores: grupo edificio, grupo vivienda y grupo habitación específica. </p></dd>
</dl>
Los grupos se utilizan para calcular los siguientes datos asociados:
<dl><dt>"wsp"</dt><dd>Consigna de impulsión de agua</dd>
<dt>"asp"</dt><dd>Consigna de impulsión de aire</dd> 
<dt>"art"</dt><dd>Valor de la temperatura de aire para el grupo</dd> 
<dt>"afg"</dt><dd>Valor del caudal de aire para el grupo</dd>
<dt>"aqg"</dt><dd>Valor de la calidad de aire para el grupo</dd>
<dt>"aqspg"</dt><dd>Valor de la consigna de calidad de aire para el grupo</dd></dl>


<li>Buses</li>
La información asociada a los buses de comunicaciones es la siguiente:
<dl><dt>"id"</dt><dd>Identificación del bus</dd>
<dt>"name"</dt><dd>Descripción que permita conocer el bus</dd> 
<dt>"ip"</dt><dd>Dirección ip del bus (no utilizada por ahora)</dd> 
<dt>"port"</dt><dd>Puerto serie al que está conectado el Bus. No es necesario en la ESP32 porque los 
pines de comunicación de la placa se definen en el fichero con las constantes del sistema</dd>
<dt>"devices"</dt><dd>De esta clave descienden todos los dispositivos ModBus del proyecto y está formado 
a su vez por los siguientes campos:
<ul>
<il type="circle"><p>"id", número de orden identificativo del dispositivo ModBus. <strong>Debe ser único</strong></p></il>
<il type="circle"><p>"name", descripción del dispositivo: ubicación, uso...</p></il>
<il type="circle"><p>"groups", lista con la identificación de los grupos de habitaciones asociados al dispositivo</p></il>
<il type="circle"><p>"sl", dirección ModBus del dispositivo</p></il>
<il type="circle"><p>"baudrate", velocidad de transmisión</p></il>
<il type="circle"><p>"databits", bits de datos</p></il>
<il type="circle"><p>"parity". Este campo varía dependiendo de si el programa corre en Linux/Windows o en
una ESP32. En una ESP32 los valores Sin Paridad/Paridad Par/Paridad Impar son None/0/1, pero en Linux o 
Windows los valores son "N"/"E"/"O". El programa lo tendrá en cuenta a la hora de realizar las operaciones 
de lectura y escritura ModBus, actualizando el valor de la paridad en función del sistema operativo.
Para ello, en el script con la configuración se definirán los valores de las constantes PARITY_NONE, 
PARITY_EVEN y PARITY_ODD</p></il>
<il type="circle"><p>"stopbits", son los bits de parada de la comunicación ModBus</p></il>
<il type="circle"><p>"class", campo para identificar la Python Class en la que se va a instanciar el dispositivo</p></il>
<il type="circle"><p>"brand", permite identificar la marca del dispositivo en el JSON con el mapa de registros de 
los dispositivos de la clase "class"</p></il>
<il type="circle"><p>"model", modelo concreto de dispositivo ModBus con cuyos datos definidos en el paquete "devices"
se instanciará la clase de dispositivo.</p></il>
</ul>
</dd></dl>
</ul>

<h1>OBTENCIÓN DE DATOS DE LAS HABITACIONES</h1>
En el fichero JSON con los datos del proyecto es donde se definen las habitaciones.
La definición de las habitaciones, además de contar con un <strong>id</strong> y un 
<strong>name/descripción</strong>, contiene la localización de los buses, dispositivos 
y registros en los que se pueden leer los atributos que las definen:
<ul>
<li>sp, consigna/setpoint</li>
<li>rt, temperatura ambiente</li>
<li>st, estado del actuador</li>
<li>aq, nivel de calidad de aire</li>
<li>aqsp, consigna de nivel de calidad de aire</li>
</ul>
Cada uno de esos atributos vienen definidos por un diccionario formado por los siguientes campos:
<ul>
<li>"bus", bus/uart, entero con la identificación del puerto serie en el que se establece la comunicación</li>
<li>"sl", esclavo, entero con la dirección en el modbus del dispositivo en el que se realiza la lectura</li>
<li>"datatype", tipo_registro, tipo de registro modbus a leer. Puede ser "co" para las coils, "di" para 
las discrete inputs, "hr" para los holding registers e "ir" para los input registers</li>
<li>"adr", registro, entero con la dirección del registro a leer</li>
</ul>
Si el diccionario está <vacío></vacío>, se ignora el atributo.

1. **FASES DEL PROYECTO**
   * FASE I <br>
<p style="margin:1.5cm">

Leer todos los dispositivos ModBus definidos en el JSON 
del edificio
</p>
<p style="margin:2cm">
Necesidades
</p>
<ul>
<li style="margin:1.5cm">JSON con todos los dispositivos ModBus, y la descripción de sus registros</li>
<li style="margin:1.5cm">.</li>
</ul>

DESPLIEGUE DEL SOFTWARE
Ejecutar en la centralita de destino:
chema@techbase:~/PhoenixPRO $ python3 -m pip install --upgrade pip  # Actualizo pip
# Editar .bashrc y añadir al PATH la ubicación de pip3.xx con el comando
# export PATH="/home/chema/.local/bin:$PATH"
chema@techbase:~/PhoenixPRO $ pip3 install virtualenv  # Instala virtualenv
chema@techbase:~/PhoenixPRO $ virtualenv venv  # creal el virtualenvironment "venv"
chema@techbase:~/PhoenixPRO $ source venv/bin/activate
(venv) chema@techbase:~/PhoenixPRO $ pip install -r requirements.txt 

ACTUALIZACIÓN DEL SOFTWARE
Ejecutar desde mi portátil linux:
chema@upolnx: $ sudo rsync -ravz -e ssh PhoenixPRO chema@10.6.1.10:/home/chema/
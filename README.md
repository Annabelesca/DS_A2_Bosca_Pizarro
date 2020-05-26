<h1><p align="center">Mutual Exclusion</p></h1>
<h2><p align="center">Práctica 2. Sistemas Distribuidos</p></h1>

## 1. Introducción

En este proyecto se nos ha pedido que implementemos un algoritmo distribuido simple para asegurar la exclusión mutua, es decir, que exactamente una función en la nube pueda entrar en una sección crítica en un momento dado. En este programa, la exclusión mutua se realizará para proteger el acceso a un archivo de resultados compartidos por las funciones y que se encuentra almacenado en el IBM COS

Para la implementación de este programa, se nos ha pedido que utilicemos el IBM-PyWren. [PyWren](https://github.com/pywren/pywren) es un proyecto de código abierto que permite la ejecución de código Python a escala sobre las funciones de la nube de IBM, es decir, la plataforma de funciones como servicio (FaaS) de IBM, basada en Apache OpenWhisk. PyWren entrega el código del usuario en la plataforma sin servidores sin necesidad de conocer cómo se invocan y ejecutan las funciones. Soporta una API básica de MapReduce.
Para llevar el control de versiones del programa se nos ha pedido que usemos GitHub. El repositorio que contiene los ficheros de esta práctica es el siguiente: https://github.com/Annabelesca/DS_A2_Bosca_Pizarro


## 2. Estructura de la práctica

En este apartado, discutiremos el principal elemento estructural de la práctica, que básicamente recae en un único fichero: MutualExclusion.py. Dicho fichero se encargará tanto de ejecutar el programa principal como de contener las funciones que se ejecutarán ya sea para realizar la escritura en el fichero de resultados “result.txt” almacenado en el COS (slave) como una función coordinadora que no permitirá que dos ficheros intenten escribir en el fichero resultado a la vez, garantizando una exclusión mutua en la zona crítica del código. 

Después también cabe mencionar el fichero .pywren_config, este archivo permite configurar pywren y da acceso a las Cloud Function y al Cloud Storage de IBM. Por cuestiones de privacidad, no se sube el archivo con los datos de IBM que se han estado utilizando para realizar la práctica.

La práctica tiene 3 secciones diferentes, cuyas funciones las veremos un poco más a fondo en los siguientes apartados. Éstas son:
1. Llamada asíncrona a la función máster, que creará el fichero de resultados “result.txt” vacío y lo subirá al COS. Después se encargará de conceder permisos de escritura a los diferentes slaves de uno en uno y según el orden en el que hayan hecho la petición, para garantizar la exclusión mutua, es decir, que exactamente sólo un slave pueda estar accediendo al archivo en un momento dado. Al acabar de gestionar las peticiones, devolverá una lista ordenada con los ID de los slaves a los que ha dado permiso de escritura
1. Llamada a los diferentes slaves de forma concurrente. Se generarán slaves que subirán un archivo de petición de escritura al COS y esperarán hasta que le den permiso para poder editar el archivo de resultados.
1. Al finalizar la ejecución tanto de los slaves como del máster, se obtendrá del COS el fichero de resultados “result.txt” para comprarlo con la lista que retorna la función master para garantizar si se ha garantizado la exclusión mutua, ya que la lista de IDs retornada por el máster debería coincidir con la que se encuentra almacenada en el fichero de resultados del COS.

Cabe mencionar que no se ha implementado una función de vaciado del bucket ya que realmente el único fichero que se genera como resultado es el propio fichero de resultados “resul.txt” ya que los ficheros temporales de petición y concesión de escritura son manejados por la función master. Hemos decido no hacer un reset del bucket ya que él usuario podría  llegar a tener interés en el contenido de éste. 
Otro asunto que no está de más mencionar es que nuestro COS está compuesto por un bucket, llamado “sdmutualexclusion”. En el momento de la ejecución, dicho Buket puede contener ficheros o estar vacío, realmente no importa ya que es la propia función master la que se encarga de generar un fichero “result.txt” vacío y, en caso de que ya exista, sobreescribirlo. También hace un control a partir de prefijos (p_write o write) para obtener la lista de peticiones/concesiones a procesar.   Una vez finalizada la ejecución de nuestro programa, el bucket contendrá el fichero de resultados con la lista ordenada de IDs de los slaves además de, en caso que hubiera algún otro archivo ajeno al programa, cualquier archivo que ya se encontrase en el bucket.

### 2.1	Función slave
Como hemos dicho antes, se trata de la función que se encargará de pedir permiso de escritura para poder editar el fichero de resultados “result.txt” que se encuentra en el COS. Recibe como parámetros el id de la ejecución y un cliente de IBM ready to use.
El esquema que sigue su ejecución ello es muy simple:
1. Se crea archivo vacío de petición de escritura “p_write_{id}” en el COS.
1.	Se monitoriza el bucket del COS cada X segundos para  buscar el permiso de escritura “write_{id}”.
1.	Si se ha concedido el permiso, descargamos fichero “result.txt”, le añadimos el identificador del slave y lo actualizamos en el bucket del COS
![Ilustración 1. Esquema general de funcionamiento del slave](https://github.com/Annabelesca/DS_A2_Bosca_Pizarro/blob/master/Ilustraciones/Slave.png)

### 2.2	Función master
Como hemos dicho antes, se trata de la función que se encargará de coordinar la escritura del fichero “result.txt” por parte de los slaves de manera que únicamente uno a la vez pueda escribir. Recibe como parámetros el id de la ejecución y un cliente de IBM ready to use.
Antes de empezar a coordinar la escritura del fichero, crea el fichero “result.txt” vacío y lo sube al COS. Además, inicializa una lista vacía donde ira apuntando en orden los slaves que se van ejecutando.
El esquema que sigue su ejecución ello es muy simple:
1. Monitorizamos el bucket del COS cada X segundos.
1. Listamos todos los ficheros de petición de escritura “p_write_{id}” dónde {id} hace referencia al identificador único de cada uno de los slaves.
1. Se ordena la lista de peticiones según orden de llegada. Los que antes llegaron son los que ocupan las primeras posiciones de la lista.
1. Se obtiene  el identificador del slave que más tiempo lleva esperando que se le conceda permiso de escritura.
1. Se borra la petición de escritura del slave al que se concederá el permiso borrando del COS el fichero vacío “p_ write_{id}”. 
1. Se concede el permiso de escritura a través de la creación de un fichero vacío en el COS, “write_{id}” dónde {id} hace referencia al identificador del slave al cual se está dando permiso.
1. Se monitoriza el fichero de resultados “result.txt” hasta que éste es actualizado en el COS.
1. Una vez el slave ha escrito en el fichero de resultados, se deniega permiso de escritura borrando del COS el fichero “write_{id}” creado en el paso 6.
1. Se comprueba si aún hay slaves que tienen pendiente su ejecución revisando si queda algún fichero vacío “p_ write_{id}” en el bucket. En caso que sí, se vuelve al paso 1.
![Ilustración 2. Esquema general de funcionamiento del master](https://github.com/Annabelesca/DS_A2_Bosca_Pizarro/blob/master/Ilustraciones/Master.png)


### 2.3	Función main
El programa revisará si el usuario le pasa como parámetro el número de slaves a utilizar. En caso que el usuario no pase ningún parámetro extra, el programa se ejecutará con un número determinado de slaves, 10. Por otro lado, si el usuario pasa un valor, se comprobará que sea un valor válido (0 < N_SLAVES < 100) y cambiará el número de slaves para la ejecución. Si este valor no es válido, el programa se ejecutará con el valor por defecto. 
El programa principal ejecutara la llamada tanto a la función de master como a la de los slaves y esperará a que acaben. Una vez haya acabado esta ejecución, se procederá a comprobar el correcto funcionamiento de la exclusión mutua comparando la lista resultado obtenida de la ejecución del master con la lista que se encuentra almacenada en el fichero “result.txt” del COS. En caso que las dos listas se correspondan, significara que se ha garantizado la exclusión mutua mientras que si las dos listas no se corresponden, habrá habido algún error a la hora de conceder los permisos de escritura. 
Se puede ejecutar este programa de dos formas distintas, en función de si quieremos cambiar el número de slaves que utilizamos o si queremos el número por defecto. 
<p align="center">>python MutualExclusion.oy N</p>
Dónde N es un parámetro opcional, que tiene que estar entre 1 y 100 (ambos incluidos.)

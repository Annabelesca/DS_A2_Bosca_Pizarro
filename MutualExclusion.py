import pywren_ibm_cloud as pywren
import json
import time
from datetime import datetime
import sys

N_SLAVES = 10
bucketName = 'sdmutualexclusion'
resultFile = 'result.txt'
timeSleep = 1


"""Funcion que se encarga de coordinar los diferentes slaves a la hora de escribir en el fichero
Parametros de entrada:
    id - Parametro reservado que permite la obtencion del iD de la llamada
    x - 
    ibm-cos - Cliente de COS ready-to-use
Retorna:
    Una lista indicando en que orden se ha dado permiso de escritura a los slaves que lo han solicitado
"""
def master(id, x, ibm_cos):
    write_permission_list = []
    ibm_cos.put_object(Bucket=bucketName, Key=resultFile)   #Creamos fichero vacio de resultados, en caso que ya haya uno, lo sobreescribimos
    lastUpdate = ibm_cos.head_object(Bucket=bucketName, Key=resultFile)['LastModified']

    ibm_cos.put_object(Bucket=bucketName, Key="log.txt")

    finished = False; updated = False; hasItems = False
    time.sleep(timeSleep)

    while (finished == False):  #Mientras aun no hayamos acabado de procesar todas las peticiones de escritura
        #lastUpdate = ibm_cos.head_object(Bucket=bucketName, Key=resultFile)['LastModified'] #Cogemos ultima fecha de modificacion del fichero de resultados

        # 1. Monitorizamos bucket cada X segundos
        while(hasItems == False):
            try:
                objects = ibm_cos.list_objects(Bucket=bucketName, Prefix='p_write_')['Contents']   # 2. Obtenemos lista de peticiones de escritura "p_write_{id}"
                objects = sorted(objects, key = lambda i: i['LastModified'])    # 3. Ordenamos lista por fecha de modificacion (de más a menos antiguos)
                hasItems=True   
            except: 
                time.sleep(timeSleep)   #En caso que no haya ficheros, esperamos X segundos

        hasItems=False

        firstItem = objects.pop(0)   # 4. Obtenemos primer elemento de la lista -> Slavve al que le daremos permiso de escritura
        toWrite=firstItem['Key'][2:]; toDelete = firstItem['Key']; slaveID=firstItem['Key'][8:]   #Obtenemos nombres del elemento a borrar, añadir y el id del esclavo

        log = "Empezamos a procesar el slave: "+slaveID

        ibm_cos.put_object(Bucket=bucketName, Key=toWrite)      # 5.Escribimos permiso de escritura write_{id} en el COS
        log=log+"\nEscribimos permiso de escritura "+toWrite

        ibm_cos.delete_object(Bucket=bucketName,Key=toDelete) # 6.1 Borramos peticion de escritura p_write_{id}
        write_permission_list.append(slaveID) # 6.2 Guardamos ID del esclavo que escribe en la variable que devolveremos
        log=log+"\nBorramos peticion escritura "+toDelete

        time.sleep(0.5)

        # 7. Monitorizamos "result.txt" cada X segundos hasta que vemos que se ha actualizado
        while (updated == False):   
            #time.sleep(0.25)
            newDate = ibm_cos.head_object(Bucket=bucketName, Key=resultFile)['LastModified']
            if (lastUpdate != newDate): updated=True; log=log+"\nSlave "+slaveID+" ha actualizado el archivo"
            else: time.sleep(timeSleep); log=log+"\nArchivo de resultados no updateado. Entramos al else"  #PETA AQUI
        
        lastUpdate=newDate

        updated=False
        
        ibm_cos.delete_object(Bucket=bucketName,Key=toWrite) # 7. Borramos permiso de escritura write_{id}
        log=log+"\nBoramos archivo "+toWrite+"\n\n\n"
        
        logFile = ibm_cos.get_object(Bucket=bucketName,Key="log.txt")['Body'].read().decode()
        logFile = logFile+log
        ibm_cos.put_object(Bucket=bucketName, Key="log.txt",Body=logFile)

        try:
            objects = ibm_cos.list_objects(Bucket=bucketName, Prefix='p_write_')['Contents'] # 7. Comprobamos si hay algun otro objeto en el bucket. Si lo hay -> Paso 1
        except:
            finished = True

    
    return write_permission_list


"""Funcion que se encarga de actualizar un fichero del COS, pidiendo permiso de escritura y esperandolo antes de poder actualizarlo
Parametros de entrada:
    id - Parametro reservado que permite la obtencion del iD de la llamada
    x - 
    ibm-cos - Cliente de COS ready-to-use
"""
def slave(id, x, ibm_cos):
    canWrite = False
    nFitxer = 'p_write_'+str(id)
    i=0    

    # 1. Escribimos peticion de escritura para el slave creando ficher "p_write_{id}" en el COS
    ibm_cos.put_object(Bucket=bucketName, Key=nFitxer)

    # 2. Monitorizamos el bucket del COS cada X segundos hasta encontrar el fichero de permiso de escritura "write_{id}"
    time.sleep(timeSleep)
    while(canWrite == False):
        try:    # 3. Si write_{id} esta en el COS: Bajamos fichero "result.txt", lo actualizamos y lo volvemos a subir al COS
            res = ibm_cos.get_object(Bucket=bucketName,Key=nFitxer[2:])
            canWrite = True
        except:
            time.sleep(timeSleep)   #Mientras este fichero no esté, nos esperamos

    res = ibm_cos.get_object(Bucket=bucketName,Key=resultFile)['Body'].read()
    res = (res.decode())+str(id)+'\n'

    ibm_cos.put_object(Bucket=bucketName, Key=resultFile,Body=res)
    

if __name__ == '__main__':
    
    #Comprobamos si usuario nos ha dado parametro extra
    if (len(sys.argv)>2): print('Error, como parametro opcional se permite el numero de slaves N (<100). >python MutualExclusion.py N'); exit(1)

    #Si nos ha dado parametro extra y es un valor valido (entre 1 y 100 y es numerico), actualizamos el numero de slaves
    if (len(sys.argv)>1):
        try: n=int(sys.argv[1])
        except: print("Error de formato en el número de slaves. Revisalos"); exit(1)
        if(n>0 and n<=100): print('Numero de slaves cambiado a '+str(n)+ '\n'); N_SLAVES = n
        else: print('Valor de slaves no valido, se dejan los slaves por defecto.\n')
   
    timeSleep = 1 + (0.005 * N_SLAVES)
    print ('Se ejecuta programa con '+str(N_SLAVES)+ ' slaves.\n')
    print ('El timeSleep que usaremos es de '+str(timeSleep)+"\n")

    i_time=datetime.now()   #Empezamos a cronometrar
    try:
        pw = pywren.ibm_cf_executor()
        pw.call_async(master, 0)    #Llamamos a la funcion master
        pw.map(slave, range(N_SLAVES))  #Llamamos a las funciones slave
        write_permission_list = pw.get_result() #Esperamos resultado de las ejecuciones
    except:
        print("Credenciales no validas o nombre de bucket incorrecto. Revisalos. \n"); exit(1)
    
    f_time=datetime.now()
    print('Tiempo de ejecucion de los slaves = '+str(f_time-i_time)+"\n")   #Printamos tiempo de ejecucion

    print(str(write_permission_list)+"\n")   #Printamos lista que devuelve el master

    ibm_cos = pw.internal_storage.get_client()  #Instanciamos objeto de COS
    result = ibm_cos.get_object(Bucket=bucketName,Key=resultFile)['Body'].read().decode()   #Obtenemos lista contenida en el fichero "result.txt" del COS

    #Como ahora mismo tenemos un string, hacemos un split para obtener una lista con los id de los slaves
    result = result.split("\n")
    result.remove("")       
    print(result)

    #Comparamos listas para ver si la exclusion mutua se cumple
    if (write_permission_list[0] == result):    print("Las dos listas se corresponden. Exclusion mutua correcta.\n")
    else: print("ERROR. Exclusion mutua incorrecta.\n")
   
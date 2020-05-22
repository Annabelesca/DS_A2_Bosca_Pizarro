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
    finished = False
    updated = False
    hasItems = False
    i=0

    time.sleep(timeSleep)

    while (finished == False):  #Mientras aun no hayamos acabado de procesar todas las peticiones de escritura
        # 1. Monitorizamos bucket cada X segundos
        while(hasItems == False):
            try:
                objects = ibm_cos.list_objects(Bucket=bucketName, Prefix='p_write_')['Contents']   # 2. Obtenemos lista de peticiones de escritura "p_write_{id}"
                objects = sorted(objects, key = lambda i: i['LastModified'])    # 3. Ordenamos lista por fecha de modificacion (de más a menos antiguos)
                hasItems=True   
            except: 
                time.sleep(timeSleep)   #En caso que no haya ficheros, esperamos X segundos

        hasItems=False
        lastUpdate = ibm_cos.head_object(Bucket=bucketName, Key=resultFile)['LastModified'] #Cogemos ultima fecha de modificacion del fichero de resultados

        firstItem = objects.pop(0)   # 4. Obtenemos primer elemento de la lista -> Slavve al que le daremos permiso de escritura
        toWrite=firstItem['Key'][2:]; toDelete = firstItem['Key']; slaveID=firstItem['Key'][8:]   #Obtenemos nombres del elemento a borrar, añadir y el id del esclavo

        ibm_cos.put_object(Bucket=bucketName, Key=toWrite)      # 5.Escribimos permiso de escritura write_{id} en el COS
        
        ibm_cos.delete_object(Bucket=bucketName,Key=toDelete) # 6.1 Borramos peticion de escritura p_write_{id}
        write_permission_list.append(slaveID) # 6.2 Guardamos ID del esclavo que escribe en la variable que devolveremos

        #time.sleep(timeSleep)

        # 7. Monitorizamos "result.txt" cada X segundos hasta que vemos que se ha actualizado
        while (updated == False):   
            try:
                newDate = ibm_cos.head_object(Bucket=bucketName, Key=resultFile)['LastModified']
            except:
                time.sleep(timeSleep)

            if (lastUpdate != newDate): updated=True
            else: time.sleep(timeSleep)

        updated=False

        ibm_cos.delete_object(Bucket=bucketName,Key=toWrite) # 7. Borramos permiso de escritura write_{id}

        
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

    # 1. Escribimos peticion de escritura para el slave creando ficher "p_write_{id}" en el COS
    ibm_cos.put_object(Bucket=bucketName, Key=nFitxer)

    # 2. Monitorizamos el bucket del COS cada X segundos hasta encontrar el fichero de permiso de escritura "write_{id}"
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
    if (len(sys.argv)>2):       
        print('Error, como parametro opcional se permite el numero de slaves N (<100). >python MutualExclusion.py N')
        exit(1)

    #Si nos ha dado parametro extra y es un valor valido (entre 1 y 100), actualizamos el numero de slaves
    if (len(sys.argv)>1):
        if(int(sys.argv[1])>0 and int(sys.argv[1])<=100): 
            print('Numero de slaves cambiado a '+sys.argv[1]+ '\n')
            N_SLAVES = int(sys.argv[1])
        else:
            print('Valor de slaves no valido, se dejan los slaves por defecto.\n')

    print ('Se ejecuta programa con '+str(N_SLAVES)+ ' slaves.\n')

    pw = pywren.ibm_cf_executor()

    i_time=datetime.now()   #Empezamos a cronometrar

    pw.call_async(master, 0)    #Llamamos a la funcion master
    pw.map(slave, range(N_SLAVES))  #Llamamos a las funciones slave
    write_permission_list = pw.get_result() #Esperamos resultado de las ejecuciones

    f_time=datetime.now()
    print('Tiempo de ejecucion de los slaves = '+str(f_time-i_time)+"\n")   #Printamos tiempo de ejecucion

    print(write_permission_list+"\n")   #Printamos lista que devuelve el master

    ibm_cos = pw.internal_storage.get_client()  #Instanciamos objeto de COS
    result = ibm_cos.get_object(Bucket=bucketName,Key=resultFile)['Body'].read().decode()   #Obtenemos lista contenida en el fichero "result.txt" del COS

    #Como ahora mismo tenemos un string, hacemos un split para obtener una lista con los id de los slaves
    result = result.split("\n")
    result.remove("")       
    print(result)

    #Comparamos listas para ver si la exclusion mutua se cumple
    if (write_permission_list[0] == result):    print("Las dos listas se corresponden. Exclusion mutua correcta.\n")
    else: print("ERROR. Exclusion mutua incorrecta.\n")
import pywren_ibm_cloud as pywren
import json
import time


N_SLAVES = 1
bucketName = 'sdmutualexclusion'
resultFile = 'result.txt'

def master(id, x, ibm_cos):
    write_permission_list = []
    ibm_cos.put_object(Bucket=bucketName, Key=resultFile)
    finished = False
    updated = False

    # 1. Monitor COS bucket each X seconds
    while (finished == False):
        try:
            objects = ibm_cos.list_objects(Bucket=bucketName, Prefix='p_write_')['Contents']   # 2. List all "p_write_{id}" files - Obtenemos lista ficheros del bucket
            objects = sorted(objects, key = lambda i: i['LastModified'])    # 3. Order objects by time of creation - Lista ordenada por fecha de modificacion
            
            firstItem =objects.pop(0)   # 4. Pop first object of the list "p_write_{id}" - Obtenemos primer elemento de la lista
            toWrite=firstItem['Key'][2:]; toDelete = firstItem['Key']; slaveID=firstItem['Key'][8:]   #Obtenemos nombres del elemento a borrar, añadir y el id del esclavo

            ibm_cos.put_object(Bucket=bucketName, Key=toWrite)      # 5. Write empty "write_{id}" object into COS - Escribimos permiso de escritura
            ibm_cos.delete_object(Bucket=bucketName,Key=toDelete) # 6.1 Delete from COS "p_write_{id}" - Borramos peticion de escritura
            write_permission_list.append('Escribe el esclavo '+slaveID) # 6.2 Save {id} in write_permission_list - Guardamos ID del esclavo que escribe
            
            # 7. Monitor "result.json" object each X seconds until it is updated
            lastUpdate = ibm_cos.head_object(Bucket=bucketName, Key='SX_SSL_GrupL3-D.pcapng')['LastModified']
            while (updated == False):
                if (lastUpdate != ibm_cos.head_object(Bucket=bucketName, Key='SX_SSL_GrupL3-D.pcapng')['LastModified']): updated=True
                else: time.sleep(2)

            # 8. Delete from COS “write_{id}”
            ibm_cos.delete_object(Bucket=bucketName,Key=toWrite)

            if (len(objects)==0): finished = True # 9. Back to step 1 until no "p_write_{id}" objects in the bucket
        
        except:
            time.sleep(1) 

    return write_permission_list

def slave(id, x, ibm_cos):
    canWrite = False
    nFitxer = 'p_write_'+str(id)

    # 1. Write empty "p_write_{id}" object into COS
    ibm_cos.put_object(Bucket=bucketName, Key=nFitxer)

    # 2. Monitor COS bucket each X seconds until it finds a file called "write_{id}"
    while(canWrite == False):
        try: # 3. If write_{id} is in COS: get result.txt, append {id}, and put back to COS result.txt
            objetu = ibm_cos.get_object(Bucket=bucketName,Key=nFitxer[2:])
            res = ibm_cos.get_object(Bucket=bucketName,Key=resultFile)['Body'].read()
            
            #REVISAR. A PARTIR DE AQUI NO FUNCIONA
            
            res=res.append(id)
            ibm_cos.put_object(Bucket=bucketName, Key=resultFile,Body=json.dumps(res))
            canWrite=True
        except:
            time.sleep(2)

    # 4. Finish
    # No need to return anything
    

if __name__ == '__main__':
    pw = pywren.ibm_cf_executor()
    pw.call_async(master, 0)
    pw.map(slave, range(N_SLAVES))
    write_permission_list = pw.get_result()
    print(write_permission_list)

    # Get result.txt
    # check if content of result.txt == write_permission_list
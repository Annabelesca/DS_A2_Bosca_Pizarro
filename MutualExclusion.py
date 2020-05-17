import pywren_ibm_cloud as pywren
import json

N_SLAVES = 10
bucketName = 'sdmutualexclusion'
resultFile = 'result.txt'

def master(id, x, ibm_cos):
    write_permission_list = []
    # 1. Monitor COS bucket each X seconds
    # 2. List all "p_write_{id}" files
    # 3. Order objects by time of creation
    # 4. Pop first object of the list "p_write_{id}"
    # 5. Write empty "write_{id}" object into COS
    # 6. Delete from COS "p_write_{id}", save {id} in write_permission_list
    # 7. Monitor "result.json" object each X seconds until it is updated
    # 8. Delete from COS “write_{id}”
    # 8. Back to step 1 until no "p_write_{id}" objects in the bucket

    return write_permission_list

def slave(id, x, ibm_cos):
    # 1. Write empty "p_write_{id}" object into COS    
    # 2. Monitor COS bucket each X seconds until it finds a file called "write_{id}"
	# 3. If write_{id} is in COS: get result.txt, append {id}, and put back to COS result.txt
    # 4. Finish
    # No need to return anything

if __name__ == '__main__':
    pw = pywren.ibm_cf_executor()
    pw.call_async(master, 0)
    pw.map(slave, range(N_SLAVES))
    write_permission_list = pw.get_result()

    # Get result.txt
    # check if content of result.txt == write_permission_list
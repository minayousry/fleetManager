    
from multiprocessing import Process, Queue
import argparse
import subprocess
import os

import Kafka_GreenPlum.greenplum_create_db as gp_db


import Kafka_GreenPlum.fleet_kafka_GP_run as kafka_gp
import mqtt_Influx.fleet_mqtt_influx_run as mqtt_influx
import qpid_cassandra.fleet_qpid_cassandra_run as qpid_cassandra
import webSockets_Postgresql.fleet_ws_postpresql_run as websocket_postgresql
import webSockets_Redis.fleet_ws_redis_run as websocket_redis

#import utilities
import server_utilities as server_utilities


#For kafka configurations
kafka_server_address = "34.90.73.165:9092"



def runServers(bash_script_path):
    
    result = subprocess.run(f". {bash_script_path}",shell=True,check=True)

    # Check if the script ran successfully
    if result.returncode == 0:
        print("Bash script executed successfully")
        print("Output:")
        print(result.stdout)
        result = True
    else:
        print("Error executing Bash script")
        print("Error message:")
        print(result.stderr)
        result = False
        
    return result

#runServers("./Kafka_GreenPlum/run_kafka_GP_servers.sh")

def runProcesses(comm_process, database_process):
    
    try:
        # Create a multiprocessing Queue for IPC
        data_queue = Queue()

        # Create and start the communication process
        comm_proc = Process(target=comm_process, args=(data_queue,))
        comm_proc.start()

        # Create and start the database process
        db_proc = Process(target=database_process, args=(data_queue,))
        db_proc.start()

        # Wait for both processes to finish
        comm_proc.join()

        # Signal the database process to stop
        data_queue.put("STOP")

        db_proc.join()
        
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def setKafkaIpAddress(file_path,search_text,new_text):
    lines = []
    found_line = None
    print(file_path)
    
    file1 = open(file_path, 'r+')
    lines = file1.readlines()
    file_content = ''.join(lines)  
        
    for line in lines:
        if line.find(search_text) != -1: 
            found_line = line.strip()
            break
        
    if found_line is not None:
        modified_content = file_content.replace(found_line, new_text)

        file1.seek(0)
        file1.write(modified_content)
    file1.close()


def createReport(database_extract_func,generation_path):
    
    extracted_df = database_extract_func()
    
    if extracted_df is not None:
        server_utilities.createExcelFile(extracted_df,generation_path)
    


   
if __name__ == '__main__':
    
    # Create the argument parser
    parser = argparse.ArgumentParser()

    # Add a string argument
    parser.add_argument('serevr_technology', type=str, help='select which technology to use for the server.')

    # Parse the arguments
    args = parser.parse_args()

    # Access the parsed argument
    server_tech = args.serevr_technology
    

    bash_script_path = None
    database_create_func = None
    comm_process = None
    database_process = None
    database_extract_func = None
    generation_path = "fleetManager/server/Kafka_GreenPlum/"
    
    
    if server_tech == "kafka_greenplum":
        bash_script_path = "./Kafka_GreenPlum/run_kafka_GP_servers.sh"
        database_create_func = gp_db.createDatabase
        comm_process = kafka_gp.kafkaConsumer
        database_process = kafka_gp.storeInDatabase
        database_extract_func = kafka_gp.extractFromDatabase
        generation_path = "./Kafka_GreenPlum/"
        
        kafka_cfg_path = "/home/mina_yousry_iti/kafka/config/server.properties"
        text_to_search = "advertised.listeners=PLAINTEXT:"
        new_kafka_server = text_to_search + """//"""+kafka_server_address
        
        server_utilities.set_file_mode(kafka_cfg_path, 'r')
        setKafkaIpAddress(kafka_cfg_path,text_to_search,new_kafka_server)
        
    elif server_tech == "mqtt_influx":
        comm_process = mqtt_influx.mqtt_process
        database_process = mqtt_influx.influx_process
    elif server_tech == "qpid_cassandra":
        comm_process = qpid_cassandra.receiverProcess
        database_process = qpid_cassandra.extractFromDatabase
    elif server_tech == "websocket_postgresql":
        comm_process = websocket_postgresql.websocket_process
        database_process = websocket_postgresql.postgresql_process
    elif server_tech == "websocket_redis":
        comm_process = websocket_redis.websocket_process
        database_process = websocket_redis.redis_process
    else:
        print("Invalid server technology. Please select one of the following: mqtt_influx, kafka_greenplum, qpid_cassandra, websocket_postgresql ot websocket_redis")
        exit(1)
 
    try:
        result = runServers(bash_script_path)
        
        if result:
            print("Servers are running.")
            status = database_create_func()
            
            if status:
                print("Database is created")
            else:
                print("Failed to create database.")
                exit(1)
        else:
            print("Failed to run servers.")
            exit(1)
            
        
        process_status = runProcesses(comm_process, database_process)
        
        if process_status:
            print("Processes have finished successfully.")
            
            createReport(database_extract_func,generation_path)
            

        else:
            print("Failed to create a report")
        
        
    except Exception as e:
        print(f"An error occurred: {e}")
        exit(1)



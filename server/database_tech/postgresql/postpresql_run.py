import psycopg2.extras
import pandas as pd
from datetime import datetime,timezone
import psycopg2


# Configuration for postgresql Database
user = 'guest'
password = 'guest'
host = 'localhost'
port = '5432'
default_dbname = "postgres"
dbname = "obd2_content_database"
database_table = "obd2_data_table"
db_batch_size = 100

def stringToFloatTimestamp(timestamp_str, format='%Y-%m-%d %H:%M:%S.%f'):
    dt = datetime.strptime(timestamp_str, format)
    float_timestamp = dt.replace(tzinfo=timezone.utc).timestamp()
    return float_timestamp

def getcurrentTimestamp():
    now = datetime.now()
    formatted_date_time = now.strftime("%Y-%m-%d %H:%M:%S.%f")
    return formatted_date_time


def connectToDatabase():
    conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
    conn.autocommit = False  
    cursor = conn.cursor()

    return conn,cursor

def closeDatabaseConnection(cursor,conn):
    # Close the cursor and connection
    cursor.close()
    conn.close()




def preprocessData(data,use_database_timestamp,current_timestamp):
    
    record = ()

    if use_database_timestamp:
        record = (
                    data[0],                # vehicle_id
                    data[1],            # tx_time
                    data[2],         # x_pos
                    data[3],         # y_pos
                    data[4],         # gps_lon
                    data[5],         # gps_lat
                    data[6],         # speed
                    data[7],                # road_id
                    data[8],                # lane_id
                    data[9],         # displacement
                    data[10],        # turn_angle
                    data[11],        # acceleration
                    data[12],        # fuel_consumption
                    data[13],        # co2_consumption
                    data[14],        # deceleration
                    data[15]                # rx_time
                    )
    else:
        record = (
                    data[0],                # vehicle_id
                    data[1],            # tx_time
                    data[2],         # x_pos
                    data[3],         # y_pos
                    data[4],         # gps_lon
                    data[5],         # gps_lat
                    data[6],         # speed
                    data[7],                # road_id
                    data[8],                # lane_id
                    data[9],         # displacement
                    data[10],        # turn_angle
                    data[11],        # acceleration
                    data[12],        # fuel_consumption
                    data[13],        # co2_consumption
                    data[14],        # deceleration
                    data[15],               # rx_time
                    current_timestamp       # storage_time
                )

    return record

def getInsertionSqlQuery(use_database_timestamp):
    
    insertion_sql_query = ""
    
    if use_database_timestamp:
        insertion_sql_query =f"""INSERT INTO {database_table} (
                            vehicle_id, tx_time, x_pos, y_pos, gps_lon, gps_lat, speed, road_id, 
                            lane_id, displacement, turn_angle, acceleration, fuel_consumption, 
                            co2_consumption, deceleration,rx_time)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"""
    else:
        insertion_sql_query =f"""INSERT INTO {database_table} (
                            vehicle_id, tx_time, x_pos, y_pos, gps_lon, gps_lat, speed, road_id, 
                            lane_id, displacement, turn_angle, acceleration, fuel_consumption, 
                            co2_consumption, deceleration, rx_time, storage_time) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"""
    
    
    return insertion_sql_query

def insertRecord(conn, record,insert_query):

    try:
        with conn.cursor() as cursor:
            cursor.execute(insert_query,record)
        conn.commit()

    except Exception as e:
        print(f"Failed to insert record {record} because of error {e}")
        conn.rollback()  


def storeInDatabaseProcess(queue, last_storage_timestamp_obj,use_database_timestamp):
    
    conn,cursor = connectToDatabase()

    insert_query = getInsertionSqlQuery(use_database_timestamp)

    last_storage_timestamp = "None"

    try:
        while True:
            data = queue.get()
            if data == "STOP":
                print("Stopping the database process...")
                break
            
            if not use_database_timestamp:
                data.append(last_storage_timestamp)
            insertRecord(conn,data,insert_query)
            last_storage_timestamp = getcurrentTimestamp()

            
    except Exception as e:
        print(f"Failed to insert record because of error {e}")
    finally:
        with last_storage_timestamp_obj.get_lock():
            last_storage_timestamp_obj.value = stringToFloatTimestamp(last_storage_timestamp)
        closeDatabaseConnection(conn,cursor)


def insertRecords(conn, records,insert_query):
    cursor = conn.cursor()
    try:
        psycopg2.extras.execute_batch(cursor, insert_query, records)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Failed to insert batch: {e}")

def storeInDatabaseBatchProcess(queue, last_storage_timestamp_obj,use_database_timestamp):

    

    last_storage_timestamp = "None"

    
    conn,cursor = connectToDatabase()

    # Turn autocommit off for batching
    conn.autocommit = False
    
    records_to_insert = []
    
    insert_query = getInsertionSqlQuery(use_database_timestamp)
    
    try:
        while True:
            data = queue.get()
            
            if data == "STOP":
                if len(records_to_insert) > 0:
                    insertRecords(conn, records_to_insert,insert_query)
                    last_storage_timestamp = getcurrentTimestamp()
                break
            else:
                records_to_insert.append(preprocessData(data,use_database_timestamp,last_storage_timestamp))
            
                if len(records_to_insert) >= db_batch_size:
                    insertRecords(conn, records_to_insert,insert_query)
                    last_storage_timestamp = getcurrentTimestamp()
                    records_to_insert = []

    finally:
        with last_storage_timestamp_obj.get_lock():
            last_storage_timestamp_obj.value = stringToFloatTimestamp(last_storage_timestamp)
        closeDatabaseConnection(conn,cursor)


    
def extractFromDatabase(use_database_timestamp):

    conn,cursor = connectToDatabase()

    # Define your SQL query
    query = f"""
            SELECT vehicle_id, tx_time, x_pos, y_pos, gps_lon, gps_lat, speed, road_id, 
            lane_id, displacement, turn_angle, acceleration, fuel_consumption, 
            co2_consumption, deceleration,rx_time, storage_time 
            FROM {database_table};
            """

    # Execute the query and fetch all data
    df = pd.read_sql_query(query, conn)
    
    # Close the database connection
    closeDatabaseConnection(conn,cursor)
    
    return df,db_batch_size
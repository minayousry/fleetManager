import traci
import time
import traci.constants as tc
import pytz
import datetime
from kafka import KafkaProducer
import json

# Configuration for connecting to Kafka server
kafka_server = '34.90.73.165:9092'  # this to the Kafka server address
topic_name = 'OBD2_data'

# Confiurations for SUMO
sumoCmd = ["sumo", "-c", "osm.sumocfg"]

def getdatetime():
    utc_now = pytz.utc.localize(datetime.datetime.utcnow())
    currentDT = utc_now.astimezone(pytz.timezone("Atlantic/Reykjavik"))
    DATIME = currentDT.strftime("%Y-%m-%d %H:%M:%S")
    return DATIME

def runScenario(producer):
    
    try:    
        traci.start(sumoCmd)
        while traci.simulation.getMinExpectedNumber() > 0:

            traci.simulationStep()
            vehicles = traci.vehicle.getIDList()

            for i in range(0,len(vehicles)):
                #Function descriptions
                #https://sumo.dlr.de/docs/TraCI/Vehicle_Value_Retrieval.html
                #https://sumo.dlr.de/pydoc/traci._vehicle.html
                vehid = vehicles[i]
                x_pos, y_pos = traci.vehicle.getPosition(vehicles[i])
                gps_lon, gps_lat = traci.simulation.convertGeo(x_pos, y_pos)
                spd = round(traci.vehicle.getSpeed(vehicles[i])*3.6,2) #Convert m/s to km/h
                edge = traci.vehicle.getRoadID(vehicles[i])
                lane = traci.vehicle.getLaneID(vehicles[i])
                displacement = round(traci.vehicle.getDistance(vehicles[i]),2) #distance to starting point
                turnAngle = round(traci.vehicle.getAngle(vehicles[i]),2) #degree within last step
                acc = round(traci.vehicle.getAcceleration(vehicles[i]),2)
                fuel_cons = round(traci.vehicle.getFuelConsumption(vehicles[i]),2)
                co2_cons = round(traci.vehicle.getCO2Emission(vehicles[i]),2)
                dece = round(traci.vehicle.getDecel(vehicles[i]),2)

                #Packing the vehicle data
                veh_data = [vehid,getdatetime(),x_pos,y_pos,
                            gps_lon,gps_lat,spd,edge,lane, 
                            displacement,turnAngle,acc,
                            fuel_cons,co2_cons,dece]
                     
                producer.send(topic_name, value=veh_data)
                        
        traci.close()
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    # Initialize a Kafka producer
    producer = KafkaProducer(bootstrap_servers=[kafka_server],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'))

    runScenario(producer)
        
    # Ensure all messages are sent and then close the producer
    producer.flush()
    producer.close()

    print(f"Messages sent to topic '{topic_name}' on Kafka server at {kafka_server}")









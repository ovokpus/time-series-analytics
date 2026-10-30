from email import message
from numpy import float64, int32, string_
import requests
import json
import pandas as pd
from pandas import json_normalize
import datetime as dt

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS


# load the configuration from the json file
with open('src/config.json', 'r') as f:
    config = json.load(f)
    

url = config['api_url']
payload = {'Key': config['Key'], 'q': 'Toronto', 'aqi': 'no', 'format': 'json'}
res = requests.get(url, params=payload)

# convert the response to a json object
res_json = res.json()
print(res_json)

# normalize the json object
normalized = json_normalize(res_json)

normalized['Timestamp'] = normalized['location.localtime_epoch'].apply(lambda x: dt.datetime.fromtimestamp(x).strftime('%Y-%m-%dT%H:%M:%S+12:00'))

# rename the columns
normalized.rename(columns={
    'location.name': 'location',
    'location.region': 'region',
    'current.temp_c': 'temp_c',
    'current.wind_kph': 'wind_kph'
    }, inplace=True)

# set the index to the timestamp
normalized.set_index('Timestamp', inplace=True)

# filter  for just temperature and wind speed
ex_df = normalized.filter(['temp_c', 'wind_kph'])

print(ex_df)
print(ex_df.dtypes)

client = influxdb_client.InfluxDBClient(
    url=config['url'],
    token = config['token'],
    org=config['org']
)

# write the test data into measurement 'air_quality'
write_api = client.write_api(write_options=SYNCHRONOUS)
message = write_api.write(bucket=config['bucket'], 
                          record=ex_df, 
                          org=config['org'],
                          data_frame_measurement_name='api', 
                          data_frame_tag_columns=['location', 'region'], 
                          data_frame_field_columns=['temp_c', 'wind_kph']
                          )

write_api.flush()
print(message)
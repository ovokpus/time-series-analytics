import pandas as pd
import datetime as dt
import os

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

my_token = os.getenv('MY_TOKEN')

def run():

    df = pd.read_csv('data/PRSA_Data_20130301-20170228/PRSA_Data_Wanliu_20130301-20170228.csv')

    # Create a timestamp out of the year, month, day, and hour columns
    # Needed for InfluxDB
    df['Timestamp'] = df[['year', 'month', 'day', 'hour']].apply(lambda row: dt.datetime(*row).strftime('%Y-%m-%dT%H:%M:%SZ'), axis=1)

    # Set the timestamp as the index and drop the unneeded columns
    df.set_index('Timestamp', inplace=True)
    ex_df = df.drop(columns=['No', 'year', 'month', 'day', 'hour'], axis=1)

    print(ex_df.head())

    fields =  ['PM2.5','PM10','SO2','NO2','CO','O3','TEMP','PRES','DEWP','RAIN','wd','WSPM']

    # define the tags
    datatags = ['station', 'wd']

    client = influxdb_client.InfluxDBClient(url="http://localhost:8086", token=my_token, org="my-org")

    # write the test data into measurement 'air_quality'
    write_api = client.write_api(write_options=SYNCHRONOUS)
    message = write_api.write(bucket="air-quality", record=ex_df, data_frame_measurement_name='test', data_frame_tag_columns=datatags, data_frame_field_columns=datatags)

    print(message)

    write_api.flush()
    
    #Write the data with two tags
    write_api = client.write_api(write_options=SYNCHRONOUS)
    message = write_api.write(bucket='air-quality',org='my-org',record = ex_df, data_frame_measurement_name = 'full-tags', data_frame_tag_columns=['station','wd'])
    print(message)

    write_api.flush()

    #Write the data only with one tag
    write_api = client.write_api(write_options=SYNCHRONOUS)
    message = write_api.write(bucket='air-quality',org='my-org',record = ex_df, data_frame_measurement_name = 'location-tag-only', data_frame_tag_columns=['station'])
    print(message)

    write_api.flush()

if __name__ == '__main__':
    run()
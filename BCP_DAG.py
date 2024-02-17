import requests
import json
import datetime
from requests.exceptions import ConnectionError
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow import AirflowException
from elasticsearch import Elasticsearch

es = Elasticsearch([{'host': '10.47.246.97', 'port': 9200}])

def CloseOldTicket():
# query to TICKET_STATUS_CODE not closed and filter for last DB change(timestamp) which is older than 2 minute
# scrit is updating the status code to closed = E0006
    query = {
	"script": {
		"inline": "ctx._source.STATUS_KEY= 'E0006'", # E0006 code is equal to Closed
		"lang": "painless"
 	 },
  	"query": {
            'bool': {
               'should': [
                   { "match" : { "STATUS_KEY" : "E0001"  }},
		   { "match" : { "STATUS_KEY" : "E0002"  }}
                ],
             'filter': {
                 'range': {
                     '@timestamp': 
                         {'lt': 'now-2m'}                  
                     }
                 }
             }
         }
    }

    es.update_by_query(index='bcp', doc_type='doc', body=query)


def BcpCollector(url):
    data = requests.get(url, cert=("/usr/local/airflow/dags/c5258185_private.pem", "/usr/local/airflow/dags/c5258185_private.key"), verify=False)
    data_string = data.content
    data_string = data_string.replace(b"encoding='utf-16'",b"encoding='utf-8'")  # python 3.6
    istring = json.loads(data_string)    
    
    for x in istring['DATA']:
        
        # python recognize this dates as integer, not string
        # Converting to string

        x['CREATE_DATE'] = str(x['CREATE_DATE'])
        x['CHANGE_DATE'] = str(x['CHANGE_DATE'])
        x['LAST_CHANGED_AT_SAP'] = str(x['LAST_CHANGED_AT_SAP'])

        # making a date format what is good to elasticsearch
        x['CREATE_DATE'] = dateTimeFormatter (x['CREATE_DATE'])
        x['CHANGE_DATE'] = dateTimeFormatter (x['CHANGE_DATE'])
        x['LAST_CHANGED_AT_SAP'] = dateTimeFormatter (x['LAST_CHANGED_AT_SAP'])

        #send data to logstash
        
        send_data = json.dumps(x)
        r=requests.post("http://10.47.246.97:5045", send_data, None)
        if r.status_code != 200:
            raise AirflowException(r.status_code + ': Sending data to Logstash failed!')

def dateTimeFormatter(bad_Format):
    # original format is yyyymmddhhmmss
    # expected format is yyyy-mm-dd hh:mm:ss
    good_Format = ''
    i = 0
    while i < len(bad_Format):
        good_Format += bad_Format[i]
        if i == 3 or i == 5:
            good_Format += '-'
        if i == 7:
            good_Format += ' '
        if i == 9 or i == 11:
            good_Format += ':'
        i += 1
    return good_Format

def CheckURL(url):
     try:
        r = requests.get(url, cert=("/usr/local/airflow/dags/c5258185_private.pem", "/usr/local/airflow/dags/c5258185_private.key"), verify=False)
        if r.status_code != 200:
             raise AirflowException('Some of the BCP url is not available! Task name helps!')  
     except ConnectionError as e:
         raise AirflowException('The BCP url is not available!')
     
     try:
         r = requests.get("http://10.47.246.97:5045")  
         if r.status_code != 200:
              raise AirflowException('Logstash is not available!')
     except ConnectionError as e:
         raise AirflowException('Logstash is not available!')

     try:
         r = requests.get("http://10.47.246.97:9200")
         if r.status_code != 200:
              raise AirflowException('Elasticsearch is not available!')
     except ConnectionError as e:
         raise AirflowException('Elasticsearch is not available!')

default_args = {
    'owner': 'SAP',
    'start_date': datetime.datetime(2019, 3, 21, 10, 00, 00),
    'concurrency': 1,
    'retries': 0,
     }

with DAG('BCP_data_collector_dag',
	 catchup = False,
         default_args=default_args,
         schedule_interval='*/1 * * * *',
         ) as dag:

    Check_URL_xxfioopr = PythonOperator(task_id ='Check_URL_xxfioopr',
                               python_callable = CheckURL, 
				op_kwargs={'url': "BCP_URL_1" } )
    
    Check_URL_devcdpsops = PythonOperator(task_id ='Check_URL_devcdpsops',
                               python_callable = CheckURL, 
				op_kwargs={'url': "BCP_URL_2" } )

    CloseOldTicket = PythonOperator(task_id ='CloseOldTicket',
                               python_callable = CloseOldTicket )

    opr_bcp_xxfioopr = PythonOperator(task_id ='bcp_xxfioopr',
                               python_callable = BcpCollector, 
				op_kwargs={'url': "BCP_URL_1" } )

    opr_bcp_devcdpsops = PythonOperator(task_id = 'bcp_devcdpsops',
                               python_callable = BcpCollector, 
				op_kwargs={'url': "BCP_URL_2" } )

[Check_URL_xxfioopr, Check_URL_devcdpsops] >> CloseOldTicket >> [opr_bcp_xxfioopr, opr_bcp_devcdpsops]
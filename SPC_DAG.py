import requests
import json
import datetime
from requests.exceptions import ConnectionError
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow import AirflowException
from elasticsearch import Elasticsearch

spc_url = "SPC_API_URL"
es = Elasticsearch([{'host': '10.47.246.97', 'port': 9200}])

def CloseOldTicket():
# query to TICKET_STATUS_CODE not closed and filter for last DB change(timestamp) which is older than 2 minute
# scrit is updating the status code to closed = 08
    query = {
  "script": {
    "inline": "ctx._source.TICKET_STATUS_CODE= '08'", # 08 code is equal to Closed
    "lang": "painless"
  },
  "query": {
        'bool': {
          'must': {
              "range" : {
                "TICKET_STATUS_CODE" : { "gte" : '00', "lte" : '07' }
                }
              },
          'filter': {
            'range': {
              '@timestamp': 
                     {'lt': 'now-2m'}                  
            }
          }
        }
      }
    }

    es.update_by_query(index='spc', doc_type='doc', body=query)

def SpcCollector(url):    
    data = requests.get(url, auth=('UESR_NAME', 'USER_PASSWORD'), cert=("/usr/local/airflow/dags/c5258185_private.pem", "/usr/local/airflow/dags/c5258185_private.key"), verify=False)
    data_string = data.content
    data_string = data_string.replace(b"encoding='utf-16'",b"encoding='utf-8'")  # python 3.6
    istring = json.loads(data_string)

    if 'd' in istring:
      for x in istring['d']['results']: 
          # delete the miliseconds from report date and last change date
         x['REPORTED_AT'] = dateTimeNormalizer(x['REPORTED_AT'])
         x['LAST_CHANGE_DATE_TIME_T'] = dateTimeNormalizer(x['LAST_CHANGE_DATE_TIME_T'])

         # making a date format what is good to elasticsearch
         x['REPORTED_AT'] = dateTimeFormatter (x['REPORTED_AT'])
         x['LAST_CHANGE_DATE_TIME_T'] = dateTimeFormatter(x['LAST_CHANGE_DATE_TIME_T'])

         #send data to logstash
         
         send_data = json.dumps(x)
         r = requests.post("http://10.47.246.97:5046", send_data, None)
         if r.status_code != 200:
            raise AirflowException('Sending data to Logstash failed!')

def dateTimeNormalizer(bad_DateTime):
    i = 0
    good_DateTime = ''
    while i < len(bad_DateTime) and bad_DateTime[i] != '.' :
       good_DateTime += bad_DateTime[i]
       i += 1
    return good_DateTime

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
           r = requests.get(url, auth=('UESR_NAME', 'USER_PASSWORD'), cert=("/usr/local/airflow/dags/c5258185_private.pem", "/usr/local/airflow/dags/c5258185_private.key"), verify=False)
           if r.status_code != 200:
                raise AirflowException('The SPC url is not available!')
     except ConnectionError as e:
           raise AirflowException('The SPC url is not available!')
     
     try:
           r = requests.get("http://10.47.246.97:5046")  
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

with DAG('SPC_data_collector_dag',
	 catchup = False,
         default_args=default_args,
         schedule_interval='*/1 * * * *',
         ) as dag:

    Check_URL_SPC = PythonOperator(task_id ='Check_URL_SPC',
                                python_callable = CheckURL, 
		       		op_kwargs = {'url': spc_url } )

    CloseOldTicket = PythonOperator(task_id ='CloseOldTicket',
                                python_callable = CloseOldTicket )

    opr_spc = PythonOperator(task_id = 'spc',
                                python_callable = SpcCollector,
			        op_kwargs = {'url': spc_url } )
    
Check_URL_SPC >> CloseOldTicket >> opr_spc
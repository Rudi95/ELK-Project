# ELK-Project

Alert monitoring running on a virtual machine. The airflow has 3 jobs to feed the Elasticsearch DB using Logstash pipelines. The Grafana dashboars are connected to the elasticsearch DB.

Components:
- ELK
- Airflow
- Grafana
- Nginx

Logstash has 3 pipelines configured for:
- SPC tickets :5046
- Incoming BCP tickets :5045
- Outgoing BCP tickets :5044

Airflow has 3 python jobs configured to feed data to the ports above.


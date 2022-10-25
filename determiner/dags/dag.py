import json
from airflow.decorators import dag, task
from airflow.utils.dates import days_ago
from airflow.operators.bash_operator import BashOperator
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import (
    KubernetesPodOperator,
)
from airflow.operators.python import PythonOperator
from airflow.kubernetes.volume import Volume
from airflow.kubernetes.volume_mount import VolumeMount
from kubernetes.client import models as k8s

#import ray
#from ray_provider.decorators.ray_decorators import ray_task
from datetime import datetime, timedelta
import os
import re

#기본 설정
ray_port = "10001"
s3_port = "9000"

#크롤링 설정
comment_count = "100000"
comment_minlike = "40"
comment_minlength = "40"
comment_mintimestamp = "1514732400"

#학습 파라미터 설정
train_epoch = "20"

default_args = {
    "owner": "airflow",
}

dag_id = 'train-and-deploy'

vol1 = k8s.V1VolumeMount(
    name='airflow-ml-ray', mount_path='/tmp'
)

volume = k8s.V1Volume(
    name='airflow-ml-ray',
    persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(claim_name='airflow-ml-ray'),
)

@dag(
    dag_id=dag_id,
    default_args=default_args,
    schedule_interval=None,
    start_date=datetime.utcnow(),
    tags=["ray_worker"],
)
def train_and_deploy_dag():
    get_env = KubernetesPodOperator(
        task_id='get_env',
        name='get_env',
        namespace='airflow-cluster',
        image='python:3.7.13-alpine',
        cmds=["python3", "/tmp/loadEnv.py"],
        volumes=[volume],
        volume_mounts=[vol1],
        hostnetwork=True,
        in_cluster=True,
        is_delete_operator_pod=True,
        startup_timeout_seconds=300,
        execution_timeout=timedelta(minutes=3600),
        retries=2,
        retry_delay=timedelta(minutes=2),
        image_pull_policy='IfNotPresent',
        get_logs=True,
        do_xcom_push=True,
    )
    
    train = KubernetesPodOperator(
        task_id='train',
        name='train',
        namespace='airflow-cluster',
        image='alsruf36/airflow-kobert-modeler:py37-cu111',
        cmds=["python3", "/tmp/bertModeler.py"],
        arguments=[
            "--ray_address", "{{ task_instance.xcom_pull('get_env')['RAY_ADDRESS'] }}",
            "--ray_port", ray_port,
            "--comment_count", comment_count,
            "--comment_minlike", comment_minlike,
            "--comment_minlength", comment_minlength,
            "--comment_mintimestamp", comment_mintimestamp,
            "--train_epoch", train_epoch,
            "--s3_end_point", "{{ task_instance.xcom_pull('get_env')['S3_ADDRESS'] }}",
            "--s3_port", s3_port,
            "--s3_access_key", "{{ task_instance.xcom_pull('get_env')['S3_ACCESS_KEY'] }}",
            "--s3_secret_key", "{{ task_instance.xcom_pull('get_env')['S3_SECRET_KEY'] }}"
        ],
        volumes=[volume],
        volume_mounts=[vol1],
        hostnetwork=True,
        in_cluster=True,
        is_delete_operator_pod=True,
        startup_timeout_seconds=300,
        execution_timeout=timedelta(minutes=3600),
        retries=2,
        retry_delay=timedelta(minutes=2),
        image_pull_policy='IfNotPresent',
        get_logs=True,
        do_xcom_push=True,
    )

    deploy = KubernetesPodOperator(
        task_id='deploy',
        name='deploy',
        namespace='airflow-cluster',
        image='alsruf36/airflow-kobert-modeler:py37-cu111',
        cmds=["python3", "/tmp/bertEveluator.py"],
        arguments=[
            "--ray_address", "{{ task_instance.xcom_pull('get_env')['RAY_ADDRESS'] }}",
            "--ray_port", ray_port,
            "--file_name", "{{ task_instance.xcom_pull('train')['file_name'] }}",
            "--s3_end_point", "{{ task_instance.xcom_pull('get_env')['S3_ADDRESS'] }}",
            "--s3_port", s3_port,
            "--s3_access_key", "{{ task_instance.xcom_pull('get_env')['S3_ACCESS_KEY'] }}",
            "--s3_secret_key", "{{ task_instance.xcom_pull('get_env')['S3_SECRET_KEY'] }}",
            "--api_name", "analyze"
        ],
        volumes=[volume],
        volume_mounts=[vol1],
        hostnetwork=True,
        in_cluster=True,
        is_delete_operator_pod=True,
        startup_timeout_seconds=300,
        execution_timeout=timedelta(minutes=3600),
        retries=2,
        retry_delay=timedelta(minutes=2),
        image_pull_policy='IfNotPresent',
        get_logs=True,
        do_xcom_push=True,
    )

    get_env >> train >> deploy

train_and_deploy_dag = train_and_deploy_dag()
DATA_FOLDER=/projects/political-disposition-determiner-data/data
DAG_FOLDER=/projects/political-disposition-determiner-data/dags

cp scripts/*.py ${DATA_FOLDER}
cp dags/*.py ${DAG_FOLDER}
cp .env ${DATA_FOLDER}/.env

RAY_ADDRESS=`kubectl get svc -A | awk '/raycluster-kube-head-svc/{print $4}'`
S3_ADDRESS=`kubectl get pods -A -o=wide | awk '/minio/{print $7}'`

echo -e "\n" | tee -a ${DATA_FOLDER}/.env > '/dev/null'
echo "RAY_ADDRESS="${RAY_ADDRESS} | tee -a ${DATA_FOLDER}/.env > '/dev/null'
echo "S3_ADDRESS="${S3_ADDRESS} | tee -a ${DATA_FOLDER}/.env > '/dev/null'

sed -i 's/^ *//; s/ *$//; /^$/d; /^\s*$/d' ${DATA_FOLDER}/.env
source ../.venv/bin/activate
source <(cat .env | sed -e '/^#/d;/^\s*$/d' -e "s/'/'\\\''/g" -e "s/=\(.*\)/='\1'/g")

RAY_ADDRESS=`kubectl get svc -A | awk '/raycluster-kube-head-svc/{print $4}'`
S3_ADDRESS=`kubectl get svc -A | awk '/minio/{print $4}'`

python3 scripts/bertModeler.py      --ray_address ${RAY_ADDRESS} \
                                    --ray_port 10001 \
                                    --comment_count 100000 \
                                    --comment_minlike 10 \
                                    --comment_minlength 20 \
                                    --comment_mintimestamp 1577836800 \
                                    --comment_maxtimestamp 1646751600 \
                                    --train_epoch 10 \
                                    --s3_end_point ${S3_ADDRESS} \
                                    --s3_port 9000 \
                                    --s3_access_key ${S3_ACCESS_KEY} \
                                    --s3_secret_key ${S3_SECRET_KEY}
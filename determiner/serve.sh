source <(cat .env | sed -e '/^#/d;/^\s*$/d' -e "s/'/'\\\''/g" -e "s/=\(.*\)/='\1'/g")

RAY_ADDRESS=`kubectl get svc -A | awk '/raycluster-kube-head-svc/{print $4}'`
S3_ADDRESS=`kubectl get svc -A | awk '/minio/{print $4}'`

python3 scripts/bertEveluator.py    --ray_address ${RAY_ADDRESS} \
                                    --ray_port 10001 \
                                    --file_name "\"kobert/model-1641102602.pt\"" \
                                    --s3_end_point ${S3_ADDRESS} \
                                    --s3_port 9000 \
                                    --s3_access_key ${S3_ACCESS_KEY} \
                                    --s3_secret_key ${S3_SECRET_KEY} \
                                    --api_name analyze \
                                    --num_replicas 10
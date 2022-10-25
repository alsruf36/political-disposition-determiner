source <(cat .env | sed -e '/^#/d;/^\s*$/d' -e "s/'/'\\\''/g" -e "s/=\(.*\)/='\1'/g")

RAY_ADDRESS=`kubectl get svc -A | awk '/raycluster-kube-head-svc/{print $4}'`

python3 api/news/main.py    --ray_address ${RAY_ADDRESS} \
                                    --ray_port 10001 \
                                    --api_name news
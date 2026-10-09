set -e
REPO=/mnt/d/ml-autoscaling-project
W=$HOME/repro_gke2
mkdir -p $W/bin $W/results/week8 $W/logs/week8
cd $W
for d in scripts loadtest infra; do ln -sfn $REPO/$d $d; done
printf '#!/bin/bash\nexec %s/venv/bin/python -m locust "$@"\n' "$REPO" > bin/locust
chmod +x bin/locust
ls $W; PATH=$W/bin:$PATH locust --version 2>&1 | tail -1

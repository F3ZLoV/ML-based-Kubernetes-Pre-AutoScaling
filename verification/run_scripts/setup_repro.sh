set -e
REPO=/mnt/d/ml-autoscaling-project
W=$HOME/repro_gke
mkdir -p $W/bin $W/results/week8 $W/logs/week8
cd $W
for d in scripts loadtest infra; do ln -sfn $REPO/$d $d; done
cat > bin/locust <<EOF
#!/bin/bash
exec $REPO/venv/bin/python -m locust "\$@"
EOF
chmod +x bin/locust
ls -la $W | tail -6
PATH=$W/bin:$PATH locust --version 2>&1 | tail -1

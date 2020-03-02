#!/bin/bash
pod=$(kubectl get pod -l app=foldy-operator-find-good -o jsonpath="{.items[-1].metadata.name}" --sort-by=.metadata.creationTimestamp)
kubectl exec $pod cat /data/definitely-good.txt | wc
kubectl exec $pod -- aws --endpoint=https://sfo2.digitaloceanspaces.com s3 cp /data/definitely-good.txt s3://pdb/definitely-good.txt
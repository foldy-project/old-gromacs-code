#!/bin/bash
pod=$(kubectl get pod -l app=foldy-operator-find-good -o jsonpath="{.items[-1].metadata.name}" --sort-by=.metadata.creationTimestamp)
kubectl exec $pod cat /data/definitely-good.txt | wc

#!/bin/bash
cd $(dirname "$0")
manifest=../produce-video.yaml
thing() {
    argo submit $manifest --watch --parameter-file $1.yaml
    aws --endpoint=https://sfo2.digitaloceanspaces.com s3 cp s3://pdb/$1.mp4 .
}
argo submit $manifest --watch --parameter-file 2hm6.yaml
argo submit $manifest --watch --parameter-file 3hty.yaml
argo submit $manifest --watch --parameter-file 1ete.yaml
argo submit $manifest --watch --parameter-file 3imh.yaml
argo submit $manifest --watch --parameter-file 3fg2.yaml
argo submit $manifest --watch --parameter-file 2iay.yaml
argo submit $manifest --watch --parameter-file 1gyx.yaml
argo submit $manifest --watch --parameter-file 2lzj.yaml
argo submit $manifest --watch --parameter-file 4mbs.yaml
argo submit $manifest --watch --parameter-file 2scp.yaml
argo submit $manifest --watch --parameter-file 3hn5.yaml
argo submit $manifest --watch --parameter-file 4fz2.yaml
argo submit $manifest --watch --parameter-file 4a5u.yaml


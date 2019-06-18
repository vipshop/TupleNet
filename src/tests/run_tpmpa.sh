#!/usr/bin/env bash


if [ "$1" == "-use-vendor" ];then
    USE_VENDOR="-mod=vendor"
fi

cd $(dirname $0)

COMMIT=$(git rev-parse HEAD)
TAGGING=$(git name-rev --tags --name-only ${COMMIT})

cd ../control
GOBIN=$(pwd)/bin GOOS=linux GOARCH=amd64 go install ${USE_VENDOR} -ldflags "-X main.commit=${COMMIT} -X main.tag=${TAGGING}" ./tpmpa || exit 1

pid=`ps axu|grep tpmpa|awk '/bin/{print $2}'`
if [ $pid != "" ]
then
   kill -9 $pid
fi
$(pwd)/bin/tpmpa &

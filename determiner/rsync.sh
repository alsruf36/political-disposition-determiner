#!/bin/bash

SOURCE_FOLDER="/projects/political-disposition-determiner/determiner/scripts/"
TARGET_FOLDER="/projects/political-disposition-determiner-data/data"

if [ "$1" == "on" ] ; then
    rsync -avu --delete ${SOURCE_FOLDER} ${TARGET_FOLDER}

elif [ "$1" == "off" ] ; then
    echo "종료합니다."
else
    echo "명령어는 rsync.sh <on|off> 형태여야 합니다."
fi
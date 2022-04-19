#!/bin/bash

echo "추가"
git add .

if [ $1 -eq "heroku" ]; then
    git commit -am "heroku"
    git push heroku master --no-verify

elif [ $1 -eq "github" ]; then
    git commit -m "add"
    git push origin master
fi
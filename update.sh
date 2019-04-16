#! /bin/bash

rm -r modules
./venv/bin/python gdoc2ciab.py
git add modules/. index.md _data/course.yml

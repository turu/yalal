#!/bin/bash

conda env export | grep -v "^prefix: " > environment.yml
pip freeze > requirements.txt
#!/bin/bash

# Recreates environment based on conda's environment.yml and pip's requirements.txt

conda env remove env -n yalla
conda env create -f environment.yml --prune
source activate yalla
pip install -r requirements.txt
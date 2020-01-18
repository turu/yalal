#!/bin/bash

# Recreates environment based on conda's environment.yml and pip's requirements.txt

conda env remove -n yalla -y
conda env create -f environment.yml
source activate yalla
pip install -r requirements.txt

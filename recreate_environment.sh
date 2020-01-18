#!/bin/bash

# Recreates environment based on conda's environment.yml and pip's requirements.txt

ENVS=$(conda env list | awk '{print $1}' )
if [[ $ENVS = *"yalla"* ]]; then
   source deactivate
   conda env remove -n yalla -y
fi
conda env create -f environment.yml
source activate yalla
pip install -r requirements.txt

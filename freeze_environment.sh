#!/bin/bash

# USE WITH CARE
# Updates environment.yml and requirements.txt based on the current state of conda and pip envs
# Updated files should be adjusted manually to make sure:
#   1. They always specify exact versions of dependencies
#   2. Any accidental, unnecessary dependencies are removed to avoid bloating the environment

conda env export --from-history | grep -v "^prefix: " > environment.yml
pip freeze -l > requirements.txt
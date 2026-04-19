#!/bin/bash
export PYTHONPATH=/opt/render/project/src/app
uvicorn app.phase_6.main:app --host 0.0.0.0 --port $PORT

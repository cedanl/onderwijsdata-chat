#!/bin/bash
cd /home/site/wwwroot
uvicorn server:app --host 0.0.0.0 --port 8000

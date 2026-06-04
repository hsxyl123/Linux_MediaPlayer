@echo off
call conda activate fw

cd /d "D:\pycharm program\Linux_MediaPlayer"

set HF_HUB_DISABLE_SYMLINKS_WARNING=1
set MODEL_SIZE=large-v3
set DEVICE=cuda
set COMPUTE_TYPE=float16
set BEAM_SIZE=5

uvicorn server:app --host 0.0.0.0 --port 8000

pause
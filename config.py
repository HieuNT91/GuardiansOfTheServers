# config.py
SSH_USERNAME = "hieunt"
SSH_KEY_PATH = "~/.ssh/id_rsa"  # or None if using password

# threshold for CPU/GPU temperature

CPU_TEMP_THRESHOLD = 89
GPU_TEMP_THRESHOLD = 89
OTHER_TEMP_THRESHOLD = 80
# SERVER_DOWN_TIME = 60 * 5 - 1  # 5 minutes
SERVER_DOWN_TIME = 0  # 5 minutes


CURRENT_SERVER_NAME = "rtx_sashimi"
# server list
# Adjust addresses/names as needed
SERVERS = [
    {"name": "rtx_sashimi", "address": "rtx_sashimi"}, # Current server
    {"name": "fatchoy", "address": "fatchoy"},
    {"name": "hakao",   "address": "hakao"},
    {"name": "rtx_dimsum",  "address": "rtx_dimsum"},  # CPU server
]
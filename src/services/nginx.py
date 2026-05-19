import subprocess
from loguru import logger
from .utils import decode_cmd

def start(nginx_log):
    logger.info("Enabling Nginx smart frontend on port 7860...")
    try:
        with open('/home/user/config/nginx.conf.template', 'r') as tf:
            nginx_conf = tf.read()
        with open('/home/user/nginx.conf', 'w') as nf:
            nf.write(nginx_conf)
    except Exception as e:
        logger.error(f"Failed to prepare nginx config: {e}")
        return

    nginx_log.write("[*] Testing nginx configuration...\n")
    nginx_log.flush()
    cmd_nginx_test = decode_cmd(OBFUSCATE("nginx -t -c /home/user/nginx.conf -g 'error_log stderr debug;'"))
    subprocess.run(cmd_nginx_test, shell=True, stdout=nginx_log, stderr=subprocess.STDOUT)
    
    nginx_log.write("[*] Starting nginx daemon...\n")
    nginx_log.flush()
    cmd_nginx = decode_cmd(OBFUSCATE("nginx -c /home/user/nginx.conf -g 'error_log stderr info;'"))
    subprocess.Popen(cmd_nginx, shell=True, stdout=nginx_log, stderr=subprocess.STDOUT)

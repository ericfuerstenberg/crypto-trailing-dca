import os

#settings for running locally
#ROOT_DIR = "/".join(os.path.dirname(os.path.join(__file__))#.split("/")[:-1]) 
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = ROOT_DIR + "/src"
CONF_DIR = ROOT_DIR + "/conf"
LOG_DIR = ROOT_DIR + "/log"
RESOURCES_DIR = ROOT_DIR + "/resources"

# #settings for docker container
# ROOT_DIR = "/aws-user-audit"
# SRC_DIR = ROOT_DIR
# CONF_DIR = ROOT_DIR + "/conf"
# LOG_DIR = ROOT_DIR + "/log"
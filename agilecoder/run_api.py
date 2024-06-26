import logging
import os
import sys

from agilecoder.camel.typing import ModelType

root = os.path.dirname(__file__)
sys.path.append(root)

from agilecoder.components.chat_chain import ChatChain
from agilecoder.online_log.app import send_online_log
from dotenv import load_dotenv
load_dotenv()


class BufferHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET, format=None, datefmt=None, encoding=None):
        logging.Handler.__init__(self)
        self.buffer = []

        if format:
            formatter = logging.Formatter(format, datefmt)
            self.setFormatter(formatter)
        if level:
            self.setLevel(level)
        if encoding:
            self.encoding = encoding

    def emit(self, record):
        self.buffer.append(self.format(record))

def get_config(company):
    """
    return configuration json files for ChatChain
    user can customize only parts of configuration json files, other files will be left for default
    Args:
        company: customized configuration name under CompanyConfig/

    Returns:
        path to three configuration jsons: [config_path, config_phase_path, config_role_path]
    """
    config_dir = os.path.join(root, "CompanyConfig", company)
    default_config_dir = os.path.join(root, "CompanyConfig", "Agile")

    config_files = [
        "ChatChainConfig.json",
        "PhaseConfig.json",
        "RoleConfig.json"
    ]

    config_paths = []

    for config_file in config_files:
        company_config_path = os.path.join(config_dir, config_file)
        default_config_path = os.path.join(default_config_dir, config_file)

        if os.path.exists(company_config_path):
            config_paths.append(company_config_path)
        else:
            config_paths.append(default_config_path)

    return tuple(config_paths)

def run_task(args):
    # Start AgileCoder

    # ----------------------------------------
    #          Init ChatChain
    # ----------------------------------------
    config_path, config_phase_path, config_role_path = get_config(args.config)

    home_path = os.path.expanduser("~")
    warehouse_path = os.path.join(home_path, "AgileCoder", "WareHouse")
    os.makedirs(warehouse_path, exist_ok = True)
    args2type = {'GPT_3_5_TURBO': ModelType.GPT_3_5_TURBO, 'GPT_4': ModelType.GPT_4, 'GPT_4_32K': ModelType.GPT_4_32k, 'GPT_3_5_AZURE': ModelType.GPT_3_5_AZURE,'CLAUDE':ModelType.CLAUDE}
    chat_chain = ChatChain(config_path=config_path,
                        config_phase_path=config_phase_path,
                        config_role_path=config_role_path,
                        task_prompt=args.task,
                        project_name=args.name,
                        org_name=args.org,
                        model_type=args2type[args.model])

    # ----------------------------------------
    #          Init Log
    # ----------------------------------------
    logging.basicConfig(filename=chat_chain.log_filepath, level=logging.INFO,
                        format='[%(asctime)s %(levelname)s] %(message)s',
                        datefmt='%Y-%d-%m %H:%M:%S', encoding="utf-8")
    buffer_handler = BufferHandler(level=logging.INFO,
                        format='[%(asctime)s %(levelname)s] %(message)s',
                        datefmt='%Y-%d-%m %H:%M:%S', encoding="utf-8")
    buffer_handler.setLevel(logging.INFO)  # Set the handler level to DEBUG
    # logger.addHandler(buffer_handler)
    logging.root.addHandler(buffer_handler)

    # ----------------------------------------
    #          Pre Processing
    # ----------------------------------------

    chat_chain.pre_processing()

    # ----------------------------------------
    #          Personnel Recruitment
    # ----------------------------------------

    chat_chain.make_recruitment()

    # ----------------------------------------
    #          Chat Chain
    # ----------------------------------------

    chat_chain.execute_chain()

    # ----------------------------------------
    #          Post Processing
    # ----------------------------------------

    chat_chain.post_processing()
    send_online_log("<FINISH>")
    return chat_chain.chat_env.env_dict['directory']
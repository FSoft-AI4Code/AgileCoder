
from src.project import ProjectManager
from src.state import AgentState
from src.logger import Logger


import json
import time
import platform
import tiktoken
import asyncio

import argparse
import logging
import os
import sys

from agilecoder.camel.typing import ModelType


from agilecoder.components.chat_chain import ChatChain
from dotenv import load_dotenv
current_dir = os.getcwd()
env_path = os.path.join(current_dir, '.env')
load_dotenv(env_path)
def get_log_filename():
    for handler in logging.root.handlers:
        if isinstance(handler, logging.FileHandler):
            return handler.baseFilename
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
root = 'src/AgileCoder/agilecoder'

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


parser = argparse.ArgumentParser(description='argparse')
parser.add_argument('--config', type=str, default="Agile",
                    help="Name of config, which is used to load configuration under CompanyConfig/")
parser.add_argument('--org', type=str, default="DefaultOrganization",
                    help="Name of organization, your software will be generated in WareHouse/name_org_timestamp")
parser.add_argument('--name', type=str, default="Gomoku",
                    help="Name of software, your software will be generated in WareHouse/name_org_timestamp")
parser.add_argument('--model', type=str, default="GPT_3_5_AZURE",
                    help="GPT Model, choose from {'GPT_3_5_TURBO','GPT_4','GPT_4_32K', 'GPT_3_5_AZURE'}")
args = parser.parse_args()

# Start AgileCoder

# ----------------------------------------
#          Init ChatChain
# ----------------------------------------
config_path, config_phase_path, config_role_path = get_config(args.config)
os.makedirs('WareHouse', exist_ok = True)
args2type = {'GPT_3_5_TURBO': ModelType.GPT_3_5_TURBO, 'GPT_4': ModelType.GPT_4, 'GPT_4_32K': ModelType.GPT_4_32k, 'GPT_3_5_AZURE': ModelType.GPT_3_5_AZURE}


class Agent:
    def __init__(self, base_model: str, search_engine: str):
        if not base_model:
            raise ValueError("base_model is required")

        self.logger = Logger()

        """
        Accumulate contextual keywords from chained prompts of all preparation agents
        """
        self.collected_context_keywords = []

        """
        Agents
        """

        self.project_manager = ProjectManager()
        self.agent_state = AgentState()
        self.engine = search_engine
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

 
    def execute(self, prompt: str, project_name_from_user: str = None) -> str:
        """
        Agentic flow of execution
        """
        project_name = project_name_from_user
        if project_name_from_user:
            self.project_manager.add_message_from_user(project_name_from_user, prompt)
        
        with open('project_name.txt' ,'w') as f:
            f.write(project_name.strip())

        # plan = self.planner.execute(prompt, project_name_from_user)
        # print("\nplan :: ", plan, '\n')
        
        # planner_response = self.planner.parse_response(plan)
        # print('*'*1000,'in agent source',planner_response)
        # project_name = planner_response["project"]
        # reply = planner_response["reply"]
        # focus = planner_response["focus"]
        # plans = planner_response["plans"]
        # summary = planner_response["summary"]
        self.agent_state.set_agent_active(project_name, True)
        self.project_manager.add_message_from_devika(project_name, f"I am AgileCoder and i will help you with {prompt}",'AgileCoder')
        chat_chain = ChatChain(config_path=config_path,
                       config_phase_path=config_phase_path,
                       config_role_path=config_role_path,
                       task_prompt=prompt,
                       project_name=args.name,
                       org_name=args.org,
                       model_type=args2type[args.model])
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


        self.project_manager.add_message_from_devika(project_name, "Start processing",'AgileCoder')
        
        # print('a'*100,get_log_filename(),type(get_log_filename()))

        # ----------------------------------------
        #          Chat Chain
        # ----------------------------------------

        chat_chain.execute_chain()

        # ----------------------------------------
        #          Post Processing
        # ----------------------------------------

        chat_chain.post_processing()


        self.agent_state.set_agent_active(project_name, True)

        # self.project_manager.add_message_from_devika(project_name, reply)
        # self.project_manager.add_message_from_devika(project_name, json.dumps(plans, indent=4)) # change here

        
        self.project_manager.add_message_from_devika(project_name, f"Project is stored at {get_log_filename()}",'AgileCoder')
        self.project_manager.add_message_from_devika(project_name,
                                                     "I have completed the my task. \n"
                                                     "if you would like me to do anything else, please let me know. \n",
                                                     'AgileCoder'
                                                     )
        # self.agent_state.set_agent_active(project_name, False)
        # self.agent_state.set_agent_completed(project_name, True)

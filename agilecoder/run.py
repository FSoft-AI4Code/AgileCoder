# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
import argparse
import logging
import os
import sys

from agilecoder.camel.typing import ModelType

root = os.path.dirname(__file__)
sys.path.append(root)

from agilecoder.components.chat_chain import ChatChain
from dotenv import load_dotenv
load_dotenv()

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
parser.add_argument('--task', type=str, default="Develop a basic Gomoku game.",
                    help="Prompt of software")
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

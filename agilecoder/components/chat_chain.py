import importlib
import json
import os
import shutil
from datetime import datetime
import logging
import time

from agilecoder.camel.agents import RolePlaying
from agilecoder.camel.configs import ChatGPTConfig
from agilecoder.camel.typing import TaskType, ModelType
from agilecoder.components.chat_env import ChatEnv, ChatEnvConfig
from agilecoder.components.statistics import get_info
from agilecoder.components.utils import log_and_print_online, now


def check_bool(s):
    return s.lower() == "true"


class ChatChain:

    def __init__(self,
                 config_path: str = None,
                 config_phase_path: str = None,
                 config_role_path: str = None,
                 task_prompt: str = None,
                 project_name: str = None,
                 org_name: str = None,
                 model_type: ModelType = ModelType.GPT_3_5_TURBO) -> None:
        """

        Args:
            config_path: path to the ChatChainConfig.json
            config_phase_path: path to the PhaseConfig.json
            config_role_path: path to the RoleConfig.json
            task_prompt: the user input prompt for software
            project_name: the user input name for software
            org_name: the organization name of the human user
        """

        # load config file
        self.config_path = config_path
        self.config_phase_path = config_phase_path
        self.config_role_path = config_role_path
        self.project_name = project_name
        self.org_name = org_name
        self.model_type = model_type

        with open(self.config_path, 'r', encoding="utf8") as file:
            self.config = json.load(file)
        with open(self.config_phase_path, 'r', encoding="utf8") as file:
            self.config_phase = json.load(file)
        with open(self.config_role_path, 'r', encoding="utf8") as file:
            self.config_role = json.load(file)

        # init chatchain config and recruitments
        self.chain = self.config["chain"]
        self.recruitments = self.config["recruitments"]

        # init default max chat turn
        self.chat_turn_limit_default = 10

        # init ChatEnv
        self.chat_env_config = ChatEnvConfig(clear_structure=check_bool(self.config["clear_structure"]),
                                             brainstorming=check_bool(self.config["brainstorming"]),
                                             gui_design=check_bool(self.config["gui_design"]),
                                             git_management=check_bool(self.config["git_management"]))
        self.chat_env = ChatEnv(self.chat_env_config)

        # the user input prompt will be self-improved (if set "self_improve": "True" in ChatChainConfig.json)
        # the self-improvement is done in self.preprocess
        self.task_prompt_raw = task_prompt
        self.task_prompt = ""

        # init role prompts
        self.role_prompts = dict()
        for role in self.config_role:
            self.role_prompts[role] = "\n".join(self.config_role[role])

        # init log
        self.start_time, self.log_filepath = self.get_logfilepath()

        # init SimplePhase instances
        # import all used phases in PhaseConfig.json from components.phase
        # note that in PhaseConfig.json there only exist SimplePhases
        # ComposedPhases are defined in ChatChainConfig.json and will be imported in self.execute_step
        self.compose_phase_module = importlib.import_module("agilecoder.components.composed_phase")
        self.phase_module = importlib.import_module("agilecoder.components.phase")
        self.phases = dict()
        for phase in self.config_phase:
            assistant_role_name = self.config_phase[phase]['assistant_role_name']
            user_role_name = self.config_phase[phase]['user_role_name']
            phase_prompt = "\n\n".join(self.config_phase[phase]['phase_prompt'])
            phase_class = getattr(self.phase_module, phase)
            phase_instance = phase_class(assistant_role_name=assistant_role_name,
                                         user_role_name=user_role_name,
                                         phase_prompt=phase_prompt,
                                         role_prompts=self.role_prompts,
                                         phase_name=phase,
                                         model_type=self.model_type,
                                         log_filepath=self.log_filepath)
            self.phases[phase] = phase_instance



    def make_recruitment(self):
        """
        recruit all employees
        Returns: None

        """
        for employee in self.recruitments:
            self.chat_env.recruit(agent_name=employee)

    def execute_step(self, phase_item: dict):
        """
        execute single phase in the chain
        Args:
            phase_item: single phase configuration in the ChatChainConfig.json

        Returns: 

        """

        phase = phase_item['phase']
        phase_type = phase_item['phaseType']
        # For SimplePhase, just look it up from self.phases and conduct the "Phase.execute" method
        if phase_type == "SimplePhase":
            max_turn_step = phase_item['max_turn_step']
            need_reflect = check_bool(phase_item['need_reflect'])
            if phase in self.phases:
                self.chat_env = self.phases[phase].execute(self.chat_env,
                                                           self.chat_turn_limit_default if max_turn_step <= 0 else max_turn_step,
                                                           need_reflect)
            else:
                raise RuntimeError(f"Phase '{phase}' is not yet implemented in components.phase")
        # For ComposedPhase, we create instance here then conduct the "ComposedPhase.execute" method
        elif phase_type == "ComposedPhase":
            cycle_num = phase_item['cycleNum']
            composition = phase_item['Composition']
            compose_phase_class = getattr(self.compose_phase_module, phase)
            if not compose_phase_class:
                raise RuntimeError(f"Phase '{phase}' is not yet implemented in components.compose_phase")
            compose_phase_instance = compose_phase_class(phase_name=phase,
                                                         cycle_num=cycle_num,
                                                         composition=composition,
                                                         config_phase=self.config_phase,
                                                         config_role=self.config_role,
                                                         model_type=self.model_type,
                                                         log_filepath=self.log_filepath)
            self.chat_env = compose_phase_instance.execute(self.chat_env)
        else:
            raise RuntimeError(f"PhaseType '{phase_type}' is not yet implemented.")

    def execute_chain(self):
        """
        execute the whole chain based on ChatChainConfig.json
        Returns: None

        """
        for phase_item in self.chain[:5]:
            self.execute_step(phase_item)
        for i in range(10):
            if self.chat_env.env_dict.get('end-sprint', False):
                break
            self.execute_step(self.chain[5])
        for phase_item in self.chain[6:]:
            self.execute_step(phase_item)

    def get_logfilepath(self):
        """
        get the log path (under the software path)
        Returns:
            start_time: time for starting making the software
            log_filepath: path to the log

        """
        start_time = now()
        # root = "/".join(filepath.split("/")[:-1])
        root = os.path.join(os.path.expanduser("~"), "AgileCoder")
        # directory = root + "/WareHouse/"
        directory = os.path.join(root, "WareHouse")
        log_filepath = os.path.join(directory, "{}.log".format("_".join([self.project_name, self.org_name,start_time])))
        return start_time, log_filepath

    def pre_processing(self):
        """
        remove useless files and log some global config settings
        Returns: None

        """
        if self.chat_env.config.clear_structure:
            # root = "/".join(filepath.split("/")[:-1])
            root = os.path.join(os.path.expanduser("~"), "AgileCoder")
            # directory = root + "/WareHouse"
            directory = os.path.join(root, "WareHouse")
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                # logs with error trials are left in WareHouse/
                if os.path.isfile(file_path) and not filename.endswith(".py") and not filename.endswith(".log"):
                    os.remove(file_path)
                    print("{} Removed.".format(file_path))
        software_path = os.path.join(directory, "_".join([self.project_name, self.org_name, self.start_time]))
        self.chat_env.set_directory(software_path)

        # copy config files to software path
        shutil.copy(self.config_path, software_path)
        shutil.copy(self.config_phase_path, software_path)
        shutil.copy(self.config_role_path, software_path)

        # write task prompt to software path
        with open(os.path.join(software_path, self.project_name + ".prompt"), "w") as f:
            f.write(self.task_prompt_raw)

        preprocess_msg = "**[Preprocessing]**\n\n"
        chat_gpt_config = ChatGPTConfig()

        preprocess_msg += "**AgileCoder Starts** ({})\n\n".format(self.start_time)
        preprocess_msg += "**Timestamp**: {}\n\n".format(self.start_time)
        preprocess_msg += "**config_path**: {}\n\n".format(self.config_path)
        preprocess_msg += "**config_phase_path**: {}\n\n".format(self.config_phase_path)
        preprocess_msg += "**config_role_path**: {}\n\n".format(self.config_role_path)
        preprocess_msg += "**task_prompt**: {}\n\n".format(self.task_prompt_raw)
        preprocess_msg += "**project_name**: {}\n\n".format(self.project_name)
        preprocess_msg += "**Log File**: {}\n\n".format(self.log_filepath)
        preprocess_msg += "**AgileCoderConfig**:\n {}\n\n".format(self.chat_env.config.__str__())
        preprocess_msg += "**ChatGPTConfig**:\n {}\n\n".format(chat_gpt_config)
        log_and_print_online(preprocess_msg)

        # init task prompt
        if check_bool(self.config['self_improve']):
            self.chat_env.env_dict['task_prompt'] = self.self_task_improve(self.task_prompt_raw)
        else:
            self.chat_env.env_dict['task_prompt'] = self.task_prompt_raw
        return software_path

    def post_processing(self):
        """
        summarize the production and move log files to the software directory
        Returns: None

        """

        self.chat_env.write_meta()
        filepath = os.path.dirname(__file__)
        # root = "/".join(filepath.split("/")[:-1])
        root = os.path.dirname(filepath)

        post_info = "**[Post Info]**\n\n"
        now_time = now()
        time_format = "%Y%m%d%H%M%S"
        datetime1 = datetime.strptime(self.start_time, time_format)
        datetime2 = datetime.strptime(now_time, time_format)
        duration = (datetime2 - datetime1).total_seconds()

        post_info += "Software Info: {}".format(
            get_info(self.chat_env.env_dict['directory'], self.log_filepath) + "\n\n🕑**duration**={:.2f}s\n\n".format(duration))

        post_info += "AgileCoder Starts ({})".format(self.start_time) + "\n\n"
        post_info += "AgileCoder Ends ({})".format(now_time) + "\n\n"

        if self.chat_env.config.clear_structure:
            directory = self.chat_env.env_dict['directory']
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isdir(file_path) and file_path.endswith("__pycache__"):
                    shutil.rmtree(file_path, ignore_errors=True)
                    post_info += "{} Removed.".format(file_path) + "\n\n"

        log_and_print_online(post_info)

        logging.shutdown()
        time.sleep(1)

        shutil.move(self.log_filepath,
                    os.path.join(os.path.expanduser("~"), "AgileCoder","WareHouse", "_".join([self.project_name, self.org_name, self.start_time]),
                                 os.path.basename(self.log_filepath)))

    # @staticmethod
    def self_task_improve(self, task_prompt):
        """
        ask agent to improve the user query prompt
        Args:
            task_prompt: original user query prompt

        Returns:
            revised_task_prompt: revised prompt from the prompt engineer agent

        """
        self_task_improve_prompt = """I will give you a short description of a software design requirement, 
please rewrite it into a detailed prompt that can make large language model know how to make this software better based this prompt,
the prompt should ensure LLMs build a software that can be run correctly, which is the most import part you need to consider.
remember that the revised prompt should not contain more than 200 words, 
here is the short description:\"{}\". 
If the revised prompt is revised_version_of_the_description, 
then you should return a message in a format like \"<INFO> revised_version_of_the_description\", do not return messages in other formats.""".format(
            task_prompt)
        role_play_session = RolePlaying(
            assistant_role_name="Prompt Engineer",
            assistant_role_prompt="You are an professional prompt engineer that can improve user input prompt to make LLM better understand these prompts.",
            user_role_prompt="You are an user that want to use LLM to build software.",
            user_role_name="User",
            task_type=TaskType.CHATDEV,
            task_prompt="Do prompt engineering on user query",
            with_task_specify=False,
            model_type=self.model_type,
        )

        # log_and_print_online("System", role_play_session.assistant_sys_msg)
        # log_and_print_online("System", role_play_session.user_sys_msg)

        _, input_user_msg = role_play_session.init_chat(None, None, self_task_improve_prompt)
        assistant_response, user_response = role_play_session.step(input_user_msg, True)
        revised_task_prompt = assistant_response.msg.content.split("<INFO>")[-1].lower().strip()
        log_and_print_online(role_play_session.assistant_agent.role_name, assistant_response.msg.content)
        log_and_print_online(
            "**[Task Prompt Self Improvement]**\n**Original Task Prompt**: {}\n**Improved Task Prompt**: {}".format(
                task_prompt, revised_task_prompt))
        return revised_task_prompt

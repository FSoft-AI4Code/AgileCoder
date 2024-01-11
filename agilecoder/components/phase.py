import os
import re
from abc import ABC, abstractmethod

from agilecoder.camel.agents import RolePlaying
from agilecoder.camel.messages import ChatMessage
from agilecoder.camel.typing import TaskType, ModelType
from agilecoder.components.chat_env import ChatEnv
from agilecoder.components.statistics import get_info
from agilecoder.components.utils import log_and_print_online, log_arguments, get_classes_in_folder
import glob

class Phase(ABC):

    def __init__(self,
                 assistant_role_name,
                 user_role_name,
                 phase_prompt,
                 role_prompts,
                 phase_name,
                 model_type,
                 log_filepath):
        """

        Args:
            assistant_role_name: who receives chat in a phase
            user_role_name: who starts the chat in a phase
            phase_prompt: prompt of this phase
            role_prompts: prompts of all roles
            phase_name: name of this phase
        """
        self.seminar_conclusion = None
        self.assistant_role_name = assistant_role_name
        self.user_role_name = user_role_name
        self.phase_prompt = phase_prompt
        self.phase_env = dict()
        self.phase_name = phase_name
        self.assistant_role_prompt = role_prompts[assistant_role_name]
        self.user_role_prompt = role_prompts[user_role_name]
        self.ceo_prompt = role_prompts["Product Owner"]
        self.counselor_prompt = role_prompts["Development Team"]
        self.timeout_seconds = 1.0
        self.max_retries = 3
        self.reflection_prompt = """Here is a conversation between two roles: {conversations} {question}"""
        self.model_type = model_type
        self.log_filepath = log_filepath

    @log_arguments
    def chatting(
            self,
            chat_env,
            task_prompt: str,
            assistant_role_name: str,
            user_role_name: str,
            phase_prompt: str,
            phase_name: str,
            assistant_role_prompt: str,
            user_role_prompt: str,
            model_type: ModelType = None,
            task_type=TaskType.CHATDEV,
            need_reflect=False,
            with_task_specify=False,
            placeholders=None,
            chat_turn_limit=10
    ) -> str:
        """

        Args:
            chat_env: global chatchain environment TODO: only for employee detection, can be deleted
            task_prompt: user query prompt for building the software
            assistant_role_name: who receives the chat
            user_role_name: who starts the chat
            phase_prompt: prompt of the phase
            phase_name: name of the phase
            assistant_role_prompt: prompt of assistant role
            user_role_prompt: prompt of user role
            task_type: task type
            need_reflect: flag for checking reflection
            with_task_specify: with task specify
            model_type: model type
            placeholders: placeholders for phase environment to generate phase prompt
            chat_turn_limit: turn limits in each chat

        Returns:

        """
        log_and_print_online("===========self.phase_prompt", phase_prompt)
        if placeholders is None:
            placeholders = {}
        assert 1 <= chat_turn_limit <= 100

        if not chat_env.exist_employee(assistant_role_name):
            raise ValueError(f"{assistant_role_name} not recruited in ChatEnv.")
        if not chat_env.exist_employee(user_role_name):
            raise ValueError(f"{user_role_name} not recruited in ChatEnv.")
        if model_type is None:
            model_type = self.model_type
        # init role play
        role_play_session = RolePlaying(
            assistant_role_name=assistant_role_name,
            user_role_name=user_role_name,
            assistant_role_prompt=assistant_role_prompt,
            user_role_prompt=user_role_prompt,
            task_prompt=task_prompt,
            task_type=task_type,
            with_task_specify=with_task_specify,
            model_type=self.model_type,
        )

        # log_and_print_online("System", role_play_session.assistant_sys_msg)
        # log_and_print_online("System", role_play_session.user_sys_msg)

        # start the chat
        _, input_user_msg = role_play_session.init_chat(None, placeholders, phase_prompt)
        seminar_conclusion = None

        # handle chats
        # the purpose of the chatting in one phase is to get a seminar conclusion
        # there are two types of conclusion
        # 1. with "<INFO>" mark
        # 1.1 get seminar conclusion flag (ChatAgent.info) from assistant or user role, which means there exist special "<INFO>" mark in the conversation
        # 1.2 add "<INFO>" to the reflected content of the chat (which may be terminated chat without "<INFO>" mark)
        # 2. without "<INFO>" mark, which means the chat is terminated or normally ended without generating a marked conclusion, and there is no need to reflect
        for i in range(chat_turn_limit):
            # start the chat, we represent the user and send msg to assistant
            # 1. so the input_user_msg should be assistant_role_prompt + phase_prompt
            # 2. then input_user_msg send to LLM and get assistant_response
            # 3. now we represent the assistant and send msg to user, so the input_assistant_msg is user_role_prompt + assistant_response
            # 4. then input_assistant_msg send to LLM and get user_response
            # all above are done in role_play_session.step, which contains two interactions with LLM
            # the first interaction is logged in role_play_session.init_chat
            assistant_response, user_response = role_play_session.step(input_user_msg, chat_turn_limit == 1)

            conversation_meta = "**" + assistant_role_name + "<->" + user_role_name + " on : " + str(
                phase_name) + ", turn " + str(i) + "**\n\n"

            # TODO: max_tokens_exceeded errors here
            if isinstance(assistant_response.msg, ChatMessage):
                # we log the second interaction here
                log_and_print_online(role_play_session.assistant_agent.role_name,
                                     conversation_meta + "[" + role_play_session.user_agent.system_message.content + "]\n\n" + assistant_response.msg.content)
                if role_play_session.assistant_agent.info:
                    seminar_conclusion = assistant_response.msg.content
                    role_play_session.assistant_agent.info = False
                    break
                if assistant_response.terminated:
                    break

            if isinstance(user_response.msg, ChatMessage):
                # here is the result of the second interaction, which may be used to start the next chat turn
                log_and_print_online(role_play_session.user_agent.role_name,
                                     conversation_meta + "[" + role_play_session.assistant_agent.system_message.content + "]\n\n" + user_response.msg.content)
                if role_play_session.user_agent.info:
                    seminar_conclusion = user_response.msg.content
                    role_play_session.user_agent.info = False
                    break
                if user_response.terminated:
                    break

            # continue the chat
            if chat_turn_limit > 1 and isinstance(user_response.msg, ChatMessage):
                input_user_msg = user_response.msg
            else:
                break

        # conduct self reflection
        if need_reflect:
            if seminar_conclusion in [None, ""]:
                seminar_conclusion = "<INFO> " + self.self_reflection(task_prompt, role_play_session, phase_name,
                                                                      chat_env)
            if "recruiting" in phase_name:
                if "Yes".lower() not in seminar_conclusion.lower() and "No".lower() not in seminar_conclusion.lower():
                    seminar_conclusion = "<INFO> " + self.self_reflection(task_prompt, role_play_session,
                                                                          phase_name,
                                                                          chat_env)
            elif seminar_conclusion in [None, ""]:
                seminar_conclusion = "<INFO> " + self.self_reflection(task_prompt, role_play_session, phase_name,
                                                                      chat_env)
        else:
            seminar_conclusion = assistant_response.msg.content

        log_and_print_online("**[Seminar Conclusion]**:\n\n {}".format(seminar_conclusion))
        if not hasattr(self, 'force_unsplit'):
            seminar_conclusion = seminar_conclusion.split("<INFO>")[-1]
        return seminar_conclusion

    def self_reflection(self,
                        task_prompt: str,
                        role_play_session: RolePlaying,
                        phase_name: str,
                        chat_env: ChatEnv) -> str:
        """

        Args:
            task_prompt: user query prompt for building the software
            role_play_session: role play session from the chat phase which needs reflection
            phase_name: name of the chat phase which needs reflection
            chat_env: global chatchain environment

        Returns:
            reflected_content: str, reflected results

        """
        messages = role_play_session.assistant_agent.stored_messages if len(
            role_play_session.assistant_agent.stored_messages) >= len(
            role_play_session.user_agent.stored_messages) else role_play_session.user_agent.stored_messages
        messages = ["{}: {}".format(message.role_name, message.content.replace("\n\n", "\n")) for message in messages]
        messages = "\n\n".join(messages)

        if "recruiting" in phase_name:
            question = """Answer their final discussed conclusion (Yes or No) in the discussion without any other words, e.g., "Yes" """
        elif phase_name == "DemandAnalysis":
            question = """Answer their final product modality in the discussion without any other words, e.g., "PowerPoint" """
        # elif phase_name in [PhaseType.BRAINSTORMING]:
        #     question = """Conclude three most creative and imaginative brainstorm ideas from the whole discussion, in the format: "1) *; 2) *; 3) *; where '*' represents a suggestion." """
        elif phase_name == "LanguageChoose":
            question = """Conclude the programming language being discussed for software development, in the format: "*" where '*' represents a programming language." """
        elif phase_name == "EnvironmentDoc":
            question = """According to the codes and file format listed above, write a requirements.txt file to specify the dependencies or packages required for the project to run properly." """
        else:
            raise ValueError(f"Reflection of phase {phase_name}: Not Assigned.")

        # Reflections actually is a special phase between CEO and counselor
        # They read the whole chatting history of this phase and give refined conclusion of this phase
        reflected_content = \
            self.chatting(chat_env=chat_env,
                          task_prompt=task_prompt,
                          assistant_role_name="Product Owner",
                          user_role_name="Development Team",
                          phase_prompt=self.reflection_prompt,
                          phase_name="Reflection",
                          assistant_role_prompt=self.ceo_prompt,
                          user_role_prompt=self.counselor_prompt,
                          placeholders={"conversations": messages, "question": question},
                          need_reflect=False,
                          chat_turn_limit=1,
                          model_type=self.model_type)

        if "recruiting" in phase_name:
            if "Yes".lower() in reflected_content.lower():
                return "Yes"
            return "No"
        else:
            return reflected_content

    @abstractmethod
    def update_phase_env(self, chat_env):
        """
        update self.phase_env (if needed) using chat_env, then the chatting will use self.phase_env to follow the context and fill placeholders in phase prompt
        must be implemented in customized phase
        the usual format is just like:
        ```
            self.phase_env.update({key:chat_env[key]})
        ```
        Args:
            chat_env: global chat chain environment

        Returns: None

        """
        pass

    @abstractmethod
    def update_chat_env(self, chat_env) -> ChatEnv:
        """
        update chan_env based on the results of self.execute, which is self.seminar_conclusion
        must be implemented in customized phase
        the usual format is just like:
        ```
            chat_env.xxx = some_func_for_postprocess(self.seminar_conclusion)
        ```
        Args:
            chat_env:global chat chain environment

        Returns:
            chat_env: updated global chat chain environment

        """
        pass

    def execute(self, chat_env, chat_turn_limit, need_reflect) -> ChatEnv:
        """
        execute the chatting in this phase
        1. receive information from environment: update the phase environment from global environment
        2. execute the chatting
        3. change the environment: update the global environment using the conclusion
        Args:
            chat_env: global chat chain environment
            chat_turn_limit: turn limit in each chat
            need_reflect: flag for reflection

        Returns:
            chat_env: updated global chat chain environment using the conclusion from this phase execution

        """
        self.update_phase_env(chat_env)
        self.seminar_conclusion = \
            self.chatting(chat_env=chat_env,
                          task_prompt=chat_env.env_dict['task_prompt'],
                          need_reflect=need_reflect,
                          assistant_role_name=self.assistant_role_name,
                          user_role_name=self.user_role_name,
                          phase_prompt=self.phase_prompt,
                          phase_name=self.phase_name,
                          assistant_role_prompt=self.assistant_role_prompt,
                          user_role_prompt=self.user_role_prompt,
                          chat_turn_limit=chat_turn_limit,
                          placeholders=self.phase_env,
                          model_type=self.model_type)
        chat_env = self.update_chat_env(chat_env)
        return chat_env


class DemandAnalysis(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        pass

    def update_chat_env(self, chat_env) -> ChatEnv:
        if len(self.seminar_conclusion) > 0:
            chat_env.env_dict['modality'] = self.seminar_conclusion.split("<INFO>")[-1].lower().replace(".", "").strip()
        return chat_env


class LanguageChoose(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas']})

    def update_chat_env(self, chat_env) -> ChatEnv:
        if len(self.seminar_conclusion) > 0 and "<INFO>" in self.seminar_conclusion:
            chat_env.env_dict['language'] = self.seminar_conclusion.split("<INFO>")[-1].lower().replace(".", "").strip()
        elif len(self.seminar_conclusion) > 0:
            chat_env.env_dict['language'] = self.seminar_conclusion.strip()
        else:
            chat_env.env_dict['language'] = "Python"
        return chat_env

import re

def check_if_string_starts_with_number(text):
    pattern = r"^\d"
    if re.search(pattern,  text):
        return True
    elif text.strip().startswith('-'):
        return True
    return False

class ProductBacklogCreating(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               "ideas": chat_env.env_dict['ideas']})

    def update_chat_env(self, chat_env) -> ChatEnv:
        # print('chat_env', self.seminar_conclusion)
        if len(self.seminar_conclusion) > 0 and "<INFO>" in self.seminar_conclusion:
            lists_of_backlog_items = self.seminar_conclusion.split("<INFO>")[-1].splitlines()
            product_backlog = []
            acceptance_criteria = []
            flag = True
            for item in lists_of_backlog_items:
                if check_if_string_starts_with_number(item):
                    if flag:
                        product_backlog.append(item)
                    else:
                        acceptance_criteria.append(item)
                # else: 
                #     flag = False
            chat_env.env_dict['product-backlog'] = product_backlog
            chat_env.env_dict['acceptance-criteria'] = acceptance_criteria
        elif 'product-backlog' not in chat_env.env_dict:
            lists_of_backlog_items = self.seminar_conclusion.splitlines()
            product_backlog = []
            acceptance_criteria = []
            flag = True
            for item in lists_of_backlog_items:
                if check_if_string_starts_with_number(item):
                    if flag:
                        product_backlog.append(item)
                    else:
                        acceptance_criteria.append(item)
                # else: 
                #     flag = False
            chat_env.env_dict['product-backlog'] = product_backlog
            chat_env.env_dict['acceptance-criteria'] = acceptance_criteria
        print("chat_env.env_dict['product-backlog']", chat_env.env_dict['product-backlog'])
        return chat_env
    
class SprintBacklogCreating(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               "ideas": chat_env.env_dict['ideas'],
                               'plain_product_backlog': plain_product_backlog})

    def update_chat_env(self, chat_env) -> ChatEnv:
        # print('chat_env', self.seminar_conclusion)
        sprint_goal = ''
        list_of_sprint_backlog_items = []
        if len(self.seminar_conclusion) > 0 and 'Sprint Backlog:' in self.seminar_conclusion:
            coms = self.seminar_conclusion.split('Sprint Backlog:')
            sprint_goal = coms[0].split('Sprint Goals:')[1].strip()
            sprint_backlog_items = coms[1].strip().splitlines()
            for item in sprint_backlog_items:
                if check_if_string_starts_with_number(item):
                    if '.' in item:
                        list_of_sprint_backlog_items.append(item.split('.')[1].strip())
                    else:
                        list_of_sprint_backlog_items.append(item.strip())
                # else: break
        if 'all-sprints' not in chat_env.env_dict:
            chat_env.env_dict['all-sprints'] = []
        if 'all-sprint-goals' not in chat_env.env_dict:
            chat_env.env_dict['all-sprint-goals'] = []
        chat_env.env_dict['all-sprints'].append(list_of_sprint_backlog_items)
        chat_env.env_dict['all-sprint-goals'].append(sprint_goal)
        chat_env.env_dict['current-sprint-backlog'] = list_of_sprint_backlog_items
        chat_env.env_dict['current-sprint-goals'] = sprint_goal
        current_tasks = []
        
        task_id = 1
        for task in list_of_sprint_backlog_items:
            if len(task.strip()) == 0: continue
            if task.strip().startswith('-'):
                current_tasks.append(task)
            else:
                current_tasks.append(str(task_id) + '. ' + task)
                task_id += 1
        chat_env.env_dict['current-programming-task'] = '\n'.join(current_tasks)
        print("chat_env.env_dict['current-sprint-backlog']", chat_env.env_dict['current-sprint-backlog'])
        print("chat_env.env_dict['current-sprint-goals']", chat_env.env_dict['current-sprint-goals'])
        return chat_env

class NextSprintBacklogCreating(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        all_done_tasks = '\n'.join(chat_env.env_dict['done-works'])
        all_undone_tasks = '\n'.join(chat_env.env_dict['undone-works'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               "ideas": chat_env.env_dict['ideas'],
                               'plain_product_backlog': plain_product_backlog,
                               'all_done_tasks': all_done_tasks,
                               'all_undone_tasks': all_undone_tasks})

    def update_chat_env(self, chat_env) -> ChatEnv:
        # print('chat_env', self.seminar_conclusion)
        sprint_goal = ''
        list_of_sprint_backlog_items = []
        if 'DONE.' in self.seminar_conclusion:
            lines = self.seminar_conclusion.splitlines()
            for line in lines:
                if line.strip() == 'DONE.':
                    chat_env.env_dict['end-sprint'] = True
                    return chat_env

        if self.seminar_conclusion.strip() == 'DONE.':
            chat_env.env_dict['end-sprint'] = True
            return chat_env
        if len(self.seminar_conclusion) > 0 and 'Sprint Backlog:' in self.seminar_conclusion:
            coms = self.seminar_conclusion.split('Sprint Backlog:')
            sprint_goal = coms[0].split('Sprint Goals:')[1].strip()
            sprint_backlog_items = coms[1].strip().splitlines()

            for item in sprint_backlog_items:
                if check_if_string_starts_with_number(item):
                    if '.' in item:
                        list_of_sprint_backlog_items.append(item.split('.')[1].strip())
                    else:
                        list_of_sprint_backlog_items.append(item.strip())
                # else: break
        if 'all-sprints' not in chat_env.env_dict:
            chat_env.env_dict['all-sprints'] = []
        if 'all-sprint-goals' not in chat_env.env_dict:
            chat_env.env_dict['all-sprint-goals'] = []
        chat_env.env_dict['all-sprints'].append(list_of_sprint_backlog_items)
        chat_env.env_dict['all-sprint-goals'].append(sprint_goal)
        chat_env.env_dict['current-sprint-backlog'] = list_of_sprint_backlog_items
        chat_env.env_dict['current-sprint-goals'] = sprint_goal
        current_tasks = []
        
        task_id = 1
        for task in list_of_sprint_backlog_items:
            if len(task.strip()) == 0: continue
            if task.strip().startswith('-'):
                current_tasks.append(task)
            else:
                current_tasks.append(str(task_id) + '. ' + task)
                task_id += 1
        chat_env.env_dict['current-programming-task'] = '\n'.join(current_tasks)
        print("chat_env.env_dict['current-sprint-backlog']", chat_env.env_dict['current-sprint-backlog'])
        print("chat_env.env_dict['current-sprint-goals']", chat_env.env_dict['current-sprint-goals'])
        return chat_env

import re

def extract_information(text):
    pattern = r"Backlog Item: (.*) - Member: (.*)"
    match = re.search(pattern, text)
    if match:
        task = match.group(1)
        member = match.group(2)
        return task, member
    else:
        return None, None
class RolesEngagement(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_sprint_backlog = []
        for i, item in enumerate(chat_env.env_dict['current-sprint-backlog'], start = 1):
            plain_sprint_backlog.append(str(i) + '. ' + item)
        plain_sprint_backlog = '\n'.join(plain_sprint_backlog)
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               "ideas": chat_env.env_dict['ideas'],
                               "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               'plain_sprint_backlog': plain_sprint_backlog})

    def update_chat_env(self, chat_env) -> ChatEnv:
        assigned_tasks = []
        if len(self.seminar_conclusion) > 0:
            lines = self.seminar_conclusion.splitlines()
            for line in lines:
                if len(line.strip()) == 0: continue
                task, member = extract_information(line)
                if task is None or member is None: continue
                assigned_tasks.append((task, member))
        # print('chat_env', self.seminar_conclusion)
        chat_env.env_dict['current-assigned-tasks'] = assigned_tasks
        current_backlogs_tasks = []
        idx = 1
        for task in assigned_tasks:
            if True or task[1].strip() == 'Programmer':
                current_backlogs_tasks.append(str(idx) + '. '+ task[0])
                idx += 1
        current_programming_task = '\n'.join(current_backlogs_tasks)
        chat_env.env_dict['current-programming-task'] = current_programming_task
        print("chat_env.env_dict['current-assigned-tasks']", chat_env.env_dict['current-assigned-tasks'])
        return chat_env

class Coding(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        gui = "" if not chat_env.config.gui_design \
            else "The software should be equipped with graphical user interface (GUI) so that user can visually and graphically use it; so you must choose a GUI framework (e.g., in Python, you can implement GUI via tkinter, Pygame, Flexx, PyGUI, etc,)."
                # print('chat_env', self.seminar_conclusion)
        
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               "current_sprint_backlog": chat_env.env_dict['current-sprint-backlog'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               "gui": gui})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.update_codes(self.seminar_conclusion)
        if hasattr(chat_env.codes, 'has_correct_format') and chat_env.codes.has_correct_format:
            chat_env.rewrite_codes()
            log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
            self.phase_env.update({
                'has_correct_format': True
            })
        else:
            self.phase_env.update({
                'has_correct_format': False
            })
            chat_env.env_dict['raw_code_conclusion'] = self.seminar_conclusion
        # if len(chat_env.codes.codebooks.keys()) == 0:
        #     raise ValueError("No Valid Codes.")
        # chat_env.rewrite_codes()
        # log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        return chat_env
class CodeFormatting(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"code": chat_env.env_dict['raw_code_conclusion']})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.update_codes(self.seminar_conclusion)
        if len(chat_env.codes.codebooks.keys()) == 0:
            raise ValueError("No Valid Codes.")
        chat_env.rewrite_codes()
        log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        return chat_env
class InheritCoding(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        gui = "" if not chat_env.config.gui_design \
            else "The software should be equipped with graphical user interface (GUI) so that user can visually and graphically use it; so you must choose a GUI framework (e.g., in Python, you can implement GUI via tkinter, Pygame, Flexx, PyGUI, etc,)."
                # print('chat_env', self.seminar_conclusion)
        
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                                "codes": chat_env.get_codes(),
                               "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               "current_sprint_backlog": chat_env.env_dict['current-sprint-backlog'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               "gui": gui})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.update_codes(self.seminar_conclusion)
        if hasattr(chat_env.codes, 'has_correct_format') and chat_env.codes.has_correct_format:
            chat_env.rewrite_codes()
            log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
            self.phase_env.update({
                'has_correct_format': True
            })
        else:
            self.phase_env.update({
                'has_correct_format': False
            })
            chat_env.env_dict['raw_code_conclusion'] = self.seminar_conclusion
        # if len(chat_env.codes.codebooks.keys()) == 0:
        #     raise ValueError("No Valid Codes.")
        # chat_env.rewrite_codes()
        # log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        return chat_env


class ArtDesign(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env = {"task": chat_env.env_dict['task_prompt'],
                          "language": chat_env.env_dict['language'],
                          "codes": chat_env.get_codes()}

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.proposed_images = chat_env.get_proposed_images_from_message(self.seminar_conclusion)
        log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        return chat_env


class ArtIntegration(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env = {"task": chat_env.env_dict['task_prompt'],
                          "language": chat_env.env_dict['language'],
                          "codes": chat_env.get_codes(),
                          "images": "\n".join(
                              ["{}: {}".format(filename, chat_env.proposed_images[filename]) for
                               filename in sorted(list(chat_env.proposed_images.keys()))])}

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.update_codes(self.seminar_conclusion)
        chat_env.rewrite_codes()
        # chat_env.generate_images_from_codes()
        log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        return chat_env


class CodeComplete(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes(),
                               "unimplemented_file": ""})
        unimplemented_file = ""
        for filename in self.phase_env['pyfiles']:
            code_content = open(os.path.join(chat_env.env_dict['directory'], filename)).read()
            lines = [line.strip() for line in code_content.split("\n") if line.strip() == "pass"]
            if len(lines) > 0 and self.phase_env['num_tried'][filename] < self.phase_env['max_num_implement']:
                unimplemented_file = filename
                break
        self.phase_env['num_tried'][unimplemented_file] += 1
        self.phase_env['unimplemented_file'] = unimplemented_file 

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.update_codes(self.seminar_conclusion)
        if len(chat_env.codes.codebooks.keys()) == 0:
            raise ValueError("No Valid Codes.")
        chat_env.rewrite_codes()
        log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        return chat_env

class SprintReview(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update(
            {"task": chat_env.env_dict['task_prompt'],
             "modality": chat_env.env_dict['modality'],
             "ideas": chat_env.env_dict['ideas'],
             "language": chat_env.env_dict['language'],
             "codes": chat_env.get_codes(),
              "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
             'current_programming_task': chat_env.env_dict['current-programming-task'],
             "test_reports": chat_env.env_dict['test_reports'],
            "error_summary": chat_env.env_dict['error_summary'],
            "codes": chat_env.get_codes(),
             
             "images": ", ".join(chat_env.incorporated_images)})

    def update_chat_env(self, chat_env) -> ChatEnv:
        # chat_env.env_dict['review_comments'] = self.seminar_conclusion
        if len(self.seminar_conclusion):
            coms = self.seminar_conclusion.split('Undone Work:')
            undone_work = coms[1].strip()
            done_work = coms[0].split('Done Work:')[1].strip()
        else:
            undone_work, done_work = '', ''
        chat_env.env_dict['current-done-work'] = done_work
        chat_env.env_dict['current-undone-work'] = undone_work
        if 'done-works' not in chat_env.env_dict:
            chat_env.env_dict['done-works'] = []
        if 'undone-works' not in chat_env.env_dict:
            chat_env.env_dict['undone-works'] = []

        chat_env.env_dict['done-works'].append(done_work)
        chat_env.env_dict['undone-works'].append(undone_work)
        print('done work:', done_work)
        print('undone work:', undone_work)
        return chat_env
class ProductBacklogReview(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               'plain_product_backlog': plain_product_backlog})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.env_dict['product_backlog_comments'] = self.seminar_conclusion
        return chat_env

class SprintBacklogReview(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               'plain_product_backlog': plain_product_backlog,
                                "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               'current_programming_task': chat_env.env_dict['current-programming-task']})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.env_dict['sprint_backlog_comments'] = self.seminar_conclusion
        return chat_env
class ProductBacklogModification(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               'plain_product_backlog': plain_product_backlog,
                               "product_backlog_comments": chat_env.env_dict['product_backlog_comments']})

    def update_chat_env(self, chat_env) -> ChatEnv:
        print('ProductBacklogModification:', self.seminar_conclusion)
        if len(self.seminar_conclusion) > 0:
            lists_of_backlog_items = self.seminar_conclusion.splitlines()
            chat_env.env_dict['product-backlog'] = list(filter(check_if_string_starts_with_number, lists_of_backlog_items))
        elif 'product-backlog' not in chat_env.env_dict:
            lists_of_backlog_items = self.seminar_conclusion.splitlines()
            chat_env.env_dict['product-backlog'] = list(filter(check_if_string_starts_with_number, lists_of_backlog_items))
        print("chat_env.env_dict['product-backlog']", chat_env.env_dict['product-backlog'])
        return chat_env

class SprintBacklogModification(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               'plain_product_backlog': plain_product_backlog,
                               "product_backlog_comments": chat_env.env_dict['product_backlog_comments'],
                               "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               "sprint_backlog_comments": chat_env.env_dict['sprint_backlog_comments']})

    def update_chat_env(self, chat_env) -> ChatEnv:
        sprint_goal = ''
        if len(self.seminar_conclusion) > 0 and 'Sprint Backlog:' in self.seminar_conclusion:
            coms = self.seminar_conclusion.split('Sprint Backlog:')
            sprint_goal = coms[0].split('Sprint Goals:')[1].strip()
            sprint_backlog_items = coms[1].strip().splitlines()
            list_of_sprint_backlog_items = []
            for item in sprint_backlog_items:
                if check_if_string_starts_with_number(item):
                    if '.' in item:
                        list_of_sprint_backlog_items.append(item.split('.')[1].strip())
                    else:
                        list_of_sprint_backlog_items.append(item.strip())
                else: break
        if 'all-sprints' not in chat_env.env_dict:
            chat_env.env_dict['all-sprints'] = []
        if 'all-sprint-goals' not in chat_env.env_dict:
            chat_env.env_dict['all-sprint-goals'] = []
        chat_env.env_dict['all-sprints'].append(list_of_sprint_backlog_items)
        chat_env.env_dict['all-sprint-goals'].append(sprint_goal)
        chat_env.env_dict['current-sprint-backlog'] = list_of_sprint_backlog_items
        chat_env.env_dict['current-sprint-goals'] = sprint_goal
        current_tasks = []
        
        task_id = 1
        for task in list_of_sprint_backlog_items:
            if len(task.strip()) == 0: continue
            if task.strip().startswith('-'):
                current_tasks.append(task)
            else:
                current_tasks.append(str(task_id) + '. ' + task)
                task_id += 1
        chat_env.env_dict['current-programming-task'] = '\n'.join(current_tasks)
        return chat_env
class CodeReviewComment(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        
        codes = chat_env.get_codes()
        # print('codescodes:', codes)
        if '.png' in codes:
            directory = chat_env.env_dict['directory']
            # print('directorydirectorydirectory:', directory)
            assets_paths = glob.glob(f'{directory}/*.png') + glob.glob(f'{directory}/*/*.png')
            assets_paths = list(map(lambda x: x.replace(directory, '.'), assets_paths))
            assets_paths = '\n'.join(assets_paths)
        else:
            assets_paths = ''
        self.phase_env.update(
            {"task": chat_env.env_dict['task_prompt'],
             "modality": chat_env.env_dict['modality'],
             "ideas": chat_env.env_dict['ideas'],
             "language": chat_env.env_dict['language'],
             "codes": codes,
             "paths": assets_paths,
              "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
             'current_programming_task': chat_env.env_dict['current-programming-task'],
             "images": ", ".join(chat_env.incorporated_images)})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.env_dict['review_comments'] = self.seminar_conclusion
        return chat_env


class CodeReviewModification(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes(),
                                "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               "comments": chat_env.env_dict['review_comments']})

    def update_chat_env(self, chat_env) -> ChatEnv:
        if "```".lower() in self.seminar_conclusion.lower():
            chat_env.update_codes(self.seminar_conclusion)
            chat_env.rewrite_codes()
            log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        self.phase_env['modification_conclusion'] = self.seminar_conclusion
        return chat_env


class CodeReviewHuman(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        print(
            f"You can participate in the development of the software {chat_env.env_dict['task_prompt']}. Please input your feedback. (\"End\" to quit the involvement.)")
        provided_comments = input()
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes(),
                                "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               "comments": provided_comments})

    def update_chat_env(self, chat_env) -> ChatEnv:
        if "```".lower() in self.seminar_conclusion.lower():
            chat_env.update_codes(self.seminar_conclusion)
            chat_env.rewrite_codes()
            log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        return chat_env


class TestErrorSummary(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.errors = {}
    def update_phase_env(self, chat_env):
        chat_env.generate_images_from_codes()
        (exist_bugs_flag, test_reports) = chat_env.exist_bugs()
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes(),
                               "test_reports": test_reports,
                               "exist_bugs_flag": exist_bugs_flag})
        log_and_print_online("**[Test Reports]**:\n\n{}".format(test_reports))

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.env_dict['error_summary'] = self.seminar_conclusion
        chat_env.env_dict['test_reports'] = self.phase_env['test_reports']

        return chat_env

    def execute(self, chat_env, chat_turn_limit, need_reflect) -> ChatEnv:
        self.update_phase_env(chat_env)
        flag = True
        if "ModuleNotFoundError" in self.phase_env['test_reports']:
            installed_module = chat_env.fix_module_not_found_error(self.phase_env['test_reports'])
            if self.errors.get(installed_module, 0) == 0:
                flag = False
                
                log_and_print_online(
                    f"Software Test Engineer found ModuleNotFoundError:\n{self.phase_env['test_reports']}\n")
                pip_install_content = ""
                for match in re.finditer(r"No module named '(\S+)'", self.phase_env['test_reports'], re.DOTALL):
                    module = match.group(1)
                    pip_install_content += "{}\n```{}\n{}\n```\n".format("cmd", "bash", f"pip install {module}")
                    log_and_print_online(f"Programmer resolve ModuleNotFoundError by:\n{pip_install_content}\n")
                self.seminar_conclusion = "nothing need to do"
                if installed_module is not None:
                    self.errors[installed_module] = self.errors.get(installed_module, 0) + 1
        if flag:
            self.seminar_conclusion = \
                self.chatting(chat_env=chat_env,
                              task_prompt=chat_env.env_dict['task_prompt'],
                              need_reflect=need_reflect,
                              assistant_role_name=self.assistant_role_name,
                              user_role_name=self.user_role_name,
                              phase_prompt=self.phase_prompt,
                              phase_name=self.phase_name,
                              assistant_role_prompt=self.assistant_role_prompt,
                              user_role_prompt=self.user_role_prompt,
                              chat_turn_limit=chat_turn_limit,
                              placeholders=self.phase_env)
        chat_env = self.update_chat_env(chat_env)
        return chat_env

def extract_file_names(traceback_str):
    file_names = []
    
    # Define a regular expression pattern to match file names in tracebacks
    file_name_pattern = r'File "(.*?)", line \d+, in '
    
    # Use re.finditer to find all matches in the traceback string
    matches = re.finditer(file_name_pattern, traceback_str)
    
    # Extract file names from the matches
    for match in matches:
        file_names.append(match.group(1))
    
    return file_names
def extract_code_and_filename(file_content):
    # Define a regular expression pattern to match code sections
    code_pattern = r'([\w.]+)\n```(.*?)```'
    
    # Use re.finditer to find all matches in the file content
    matches = re.finditer(code_pattern, file_content, re.DOTALL)
    
    # Extract code sections from the matches
    code_sections = []
    for match in matches:
        language = match.group(1)
        code = match.group(2).strip()
        code_sections.append((language, code))
    
    return code_sections
class TestModification(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.force_unsplit = True

    def update_phase_env(self, chat_env):
        test_reports = chat_env.env_dict['test_reports']
        if 'FileNotFoundError' in test_reports:
            directory = chat_env.env_dict['directory']
            assets_paths = glob.glob(f'{directory}/*.png') + glob.glob(f'{directory}/*/*.png')
            assets_paths = list(map(lambda x: x.replace(directory, '.'), assets_paths))
            assets_paths = '\n'.join(assets_paths)
            self.phase_prompt = '\n'.join([
      "Our developed source codes and corresponding test reports are listed below: ",
      "Programming Language: \"{language}\"",
      "Source Codes:",
      "\"{codes}\"",
      "Test Reports of Source Codes:",
      "\"{test_reports}\"",
      "Error Summary of Test Reports:",
      "\"{error_summary}\"",
        "Existing assets' paths:",
      "\"{paths}\"",
    "As the {assistant_role}, in light of a error relevant to FileNotFound, to satisfy the new user's demand and make the software execute smoothly and robustly, you should modify the codes by considering the error summary and the paths of existing assets above to fix this error.",
      "Note that each file must strictly follow a markdown code block format, where the following tokens must be replaced such that \"FILENAME\" is the lowercase file name including the file extension, \"LANGUAGE\" in the programming language, \"DOCSTRING\" is a string literal specified in source code that is used to document a specific segment of code, and \"CODE\" is the original code:",
      "FILENAME",
      "```LANGUAGE",
      "'''",
      "DOCSTRING",
      "'''",
      "CODE",
      "```",
      "Now, use the format exemplified above and modify the problematic codes based on the error summary. If you cannot find the assets from the existing paths, you should consider removing relevant code and features. Output the codes that you fixed based on the test reported and corresponding explanations (strictly follow the format defined above, including FILENAME, LANGUAGE, DOCSTRING and CODE; incomplete \"TODO\" codes are strictly prohibited). If no bugs are reported, please return only one line like \"<INFO> Finished\"."
    ])
        else:
            assets_paths = ''
        if 'NameError:' in test_reports or 'ImportError' in test_reports:
            directory = chat_env.env_dict['directory']
            module_dict = get_classes_in_folder(directory)
            module_structure = []
            for k, classes in module_dict.items():
                if len(classes) == 0: continue
                module_structure.append(k)
                for c in classes:
                    module_structure.append(f'\t- class {c}')
            module_structure = '\n'.join(module_structure)
            self.phase_prompt = '\n'.join([
                "Our developed source codes, corresponding test reports and module structure are listed below: ",
                "Programming Language: \"{language}\"",
                "Buggy Source Codes:",
                "\"{codes}\"",
                "Test Reports of Source Codes:",
                "\"{test_reports}\"",
                "Error Summary of Test Reports:",
                "\"{error_summary}\"",
                "Module Structure:",
                "\"{module_structure}\"",
                "As the {assistant_role}, in light of a error relevant to module structure, to satisfy the new user's demand and make the software execute smoothly and robustly, you should modify the codes by considering the error summary and the module structure above to fix this error. However, if the module structure does not include used classes, you implement missing code.",
                "Note that each file must strictly follow a markdown code block format, where the following tokens must be replaced such that \"FILENAME\" is the lowercase file name including the file extension, \"LANGUAGE\" in the programming language, \"DOCSTRING\" is a string literal specified in source code that is used to document a specific segment of code, and \"CODE\" is the original code:",
                "FILENAME",
                "```LANGUAGE",
                "'''",
                "DOCSTRING",
                "'''",
                "CODE",
                "```",
                "Now, use the format exemplified above and modify the problematic codes. If you cannot fix this error, you should consider remove relevant code and features. Output the codes that you fixed based on the test reported and corresponding explanations (strictly follow the format defined above, including FILENAME, LANGUAGE, DOCSTRING and CODE; incomplete \"TODO\" codes are strictly prohibited). If no bugs are reported, please return only one line like \"<INFO> Finished\"."
            ])
        else:
            module_structure = ''
        
        module = ''
        modules = ''
        if 'ModuleNotFoundError' in test_reports:
            for match in re.finditer(r"No module named '(\S+)'", test_reports, re.DOTALL):
                module = match.group(1)
            modules = list(map(lambda x: '- ' + x.split('.')[0], glob.glob(chat_env.env_dict['directory'] + '/.*py')))
            modules = '\n'.join(modules)
            self.phase_prompt = '\n'.join([
                "Our developed source codes, corresponding test reports and available modules are listed below: ",
                "Programming Language: \"{language}\"",
                "Buggy Source Codes:",
                "\"{codes}\"",
                "Test Reports of Source Codes:",
                "\"{test_reports}\"",
                "Error Summary of Test Reports:",
                "\"{error_summary}\"",
                "Available Modules:",
                "\"{modules}\""
                "Note that each file must strictly follow a markdown code block format, where the following tokens must be replaced such that \"FILENAME\" is the lowercase file name including the file extension, \"LANGUAGE\" in the programming language, \"DOCSTRING\" is a string literal specified in source code that is used to document a specific segment of code, and \"CODE\" is the original code:",
                "FILENAME",
                "```LANGUAGE",
                "'''",
                "DOCSTRING",
                "'''",
                "CODE",
                "```",
                "As the {assistant_role}, to satisfy the new user's demand and make the software execute smoothly and robustly, you should modify the codes based on the error summary.",
                "There is a raised issue relevant to ModuleNotFoundError because you have not implemented the required module {missing_module}. To fix this error, you must take a great care to current source code to implement the module {missing_module} accurately.",
                "Now, use the format exemplified above and modify the problematic codes based on the error summary. If you cannot find the assets from the existing paths, you should consider remove relevant code and features. Output the codes that you fixed based on the test reported and corresponding explanations (strictly follow the format defined above, including FILENAME, LANGUAGE, DOCSTRING and CODE where FILENAME is the file name, LANGUAGE is the programming language and CODE is the source code; incomplete \"TODO\" codes are strictly prohibited). If no bugs are reported, please return only one line like \"<INFO> Finished\"."
            ])

        file_names = extract_file_names(test_reports)
        if len(file_names) > 1:
            all_relevant_code = []
            code_sections = extract_code_and_filename(chat_env.get_codes())
            for file_name, code in code_sections:
                if file_name in file_names:
                    all_relevant_code.extend([file_name, code, '\n'])
            all_relevant_code = '\n'.join(all_relevant_code)
        else:
            all_relevant_code = chat_env.get_codes()
        
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "test_reports": test_reports,
                               "error_summary": chat_env.env_dict['error_summary'],
                               "paths": assets_paths,
                               "codes": all_relevant_code,
                               "module_structure": module_structure,
                               'missing_module': module,
                               'modules': modules
                               })

    def update_chat_env(self, chat_env) -> ChatEnv:
        log_and_print_online("TEST MODIFICATION:", self.seminar_conclusion)
        if "```".lower() in self.seminar_conclusion.lower():
            chat_env.update_codes(self.seminar_conclusion)
            chat_env.rewrite_codes()
            log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        return chat_env
class EnvironmentDoc(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes()})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env._update_requirements(self.seminar_conclusion)
        chat_env.rewrite_requirements()
        log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        return chat_env


class Manual(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes(),
                               "requirements": chat_env.get_requirements()})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env._update_manuals(self.seminar_conclusion)
        chat_env.rewrite_manuals()
        return chat_env

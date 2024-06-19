import os, ast
import re
from abc import ABC, abstractmethod

from agilecoder.camel.agents import RolePlaying
from agilecoder.camel.messages import ChatMessage
from agilecoder.camel.typing import TaskType, ModelType
from agilecoder.components.chat_env import ChatEnv
from agilecoder.components.statistics import get_info
from agilecoder.components.utils import log_and_print_online, log_arguments, get_classes_in_folder, extract_product_requirements, get_non_leaf_and_intermediate_files, find_ancestors, extract_function_from_class
import glob

def is_valid_syntax(code):
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False

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
        # log_and_print_online("===========self.phase_prompt", phase_prompt)
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
                if i == 0:
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
                if i == chat_turn_limit - 1:
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
            seminar_conclusion = seminar_conclusion.strip()
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
        return 1
    elif text.strip().startswith('-'):
        return 2
    return 0
def extract_trunk_text(text, keyword, is_lower = True):
    if is_lower:
        pattern = re.compile(r'{}:(.+?)(?=\bProduct backlog:|\bAcceptance criteria:|\Z)'.format(keyword), re.DOTALL)
    else:
        pattern = re.compile(r'{}(.+?)(?=\bPRODUCT_BACKLOG|\bACCEPTANCE_CRITERIA|\Z)'.format(keyword), re.DOTALL)
    match = re.search(pattern, text)
    text = match.group(1).strip()
    lines = text.splitlines()
    results = []
    for i, line in enumerate(lines):
        if len(line.strip()) ==  0: break
        results.append(line)
    return '\n'.join(results)
    
    
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
        # if len(self.seminar_conclusion) > 0 and "<INFO>" in self.seminar_conclusion:
        #     lists_of_backlog_items = self.seminar_conclusion.split("<INFO>")[-1].splitlines()
        #     product_backlog = []
        #     acceptance_criteria = []
        #     flag = True
        #     for item in lists_of_backlog_items:
        #         if check_if_string_starts_with_number(item):
        #             if flag:
        #                 product_backlog.append(item)
        #             else:
        #                 acceptance_criteria.append(item)
        #         elif item.startswith('Acceptance Criteria'): break
        #         # else: 
        #         #     flag = False
        #     chat_env.env_dict['product-backlog'] = product_backlog
        #     chat_env.env_dict['acceptance-criteria'] = acceptance_criteria
        # elif 'product-backlog' not in chat_env.env_dict:
        #     lists_of_backlog_items = self.seminar_conclusion.splitlines()
        #     product_backlog = []
        #     acceptance_criteria = []
        #     flag = True
        #     for item in lists_of_backlog_items:
        #         if check_if_string_starts_with_number(item):
        #             if flag:
        #                 product_backlog.append(item)
        #             else:
        #                 acceptance_criteria.append(item)
        #         elif item.startswith('Acceptance Criteria'): break
        #         # else: 
        #         #     flag = False
        #     chat_env.env_dict['product-backlog'] = product_backlog
        #     chat_env.env_dict['acceptance-criteria'] = acceptance_criteria
        # print("chat_env.env_dict['product-backlog']", chat_env.env_dict['product-backlog'])
        # return chat_env
        if len(self.seminar_conclusion) > 0:
            try:
                product_backlog = extract_trunk_text(self.seminar_conclusion, "Product backlog")
                acceptance_criteria = extract_trunk_text(self.seminar_conclusion, "Acceptance criteria")
            except:
                try:
                    product_backlog = extract_trunk_text(self.seminar_conclusion, "PRODUCT_BACKLOG", False).replace(':', '').strip()
                    acceptance_criteria = extract_trunk_text(self.seminar_conclusion, "ACCEPTANCE_CRITERIA", False).replace(':', '').strip()
                except:
                    try:
                        product_backlog, acceptance_criteria = extract_product_requirements(self.seminar_conclusion)
                    except: pass
            chat_env.env_dict['product-backlog'] = product_backlog.strip().splitlines()
            chat_env.env_dict['acceptance-criteria'] = acceptance_criteria.strip().splitlines()
        return chat_env
def extract_sprint_trunk_text(text, keyword, is_lower = True):
    if is_lower:
        pattern = re.compile(r'{}:(.+?)(?=\bSprint Goals:|\bSprint backlog:|\bSprint acceptance criteria:|\Z)'.format(keyword), re.DOTALL)
    else:
        pattern = re.compile(r'{}(.+?)(?=\bSPRINT_BACKLOG|\bSPRINT_ACCEPTANCE_CRITERIA|\Z)'.format(keyword), re.DOTALL)
    match = re.search(pattern, text)
    text = match.group(1).strip()
    lines = text.splitlines()
    results = []
    for i, line in enumerate(lines):
        if len(line.strip()) ==  0: break
        results.append(line)
    return '\n'.join(results)
    
    
class SprintBacklogCreating(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        plain_acceptance_criteria = '\n'.join(chat_env.env_dict['acceptance-criteria'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               "ideas": chat_env.env_dict['ideas'],
                               'plain_product_backlog': plain_product_backlog,
                               'plain_acceptance_criteria': plain_acceptance_criteria})

    def update_chat_env(self, chat_env) -> ChatEnv:
        # print('chat_env', self.seminar_conclusion)
        # sprint_goal = ''
        # list_of_sprint_backlog_items = []
        # if len(self.seminar_conclusion) > 0 and 'Sprint Backlog:' in self.seminar_conclusion:
        #     coms = self.seminar_conclusion.split('Sprint Backlog:')
        #     sprint_goal = coms[0].split('Sprint Goals:')[1].strip()
        #     sprint_backlog_items = coms[1].strip().splitlines()
        #     for item in sprint_backlog_items:
        #         flag = check_if_string_starts_with_number(item)
        #         if flag > 0:
        #             if flag == 1 and '. ' in item:
        #                 list_of_sprint_backlog_items.append(item.split('.')[1].strip())
        #             else:
        #                 list_of_sprint_backlog_items.append(item.strip())
        #         # else: break
        # if 'all-sprints' not in chat_env.env_dict:
        #     chat_env.env_dict['all-sprints'] = []
        # if 'all-sprint-goals' not in chat_env.env_dict:
        #     chat_env.env_dict['all-sprint-goals'] = []
        # chat_env.env_dict['all-sprints'].append(list_of_sprint_backlog_items)
        # chat_env.env_dict['all-sprint-goals'].append(sprint_goal)
        # chat_env.env_dict['current-sprint-backlog'] = list_of_sprint_backlog_items
        # chat_env.env_dict['current-sprint-goals'] = sprint_goal
        # chat_env.env_dict['num-sprints'] = chat_env.env_dict.get('num-sprints', 0) + 1
        # current_tasks = []
        
        # task_id = 1
        # for task in list_of_sprint_backlog_items:
        #     if len(task.strip()) == 0: continue
        #     if task.strip().startswith('-'):
        #         current_tasks.append(task)
        #     else:
        #         current_tasks.append(str(task_id) + '. ' + task)
        #         task_id += 1
        # chat_env.env_dict['current-programming-task'] = '\n'.join(current_tasks)
        for k in ['all-sprint-backlog', 'all-sprint-acceptance-criteria', 'all-sprint-goals']:
            if k not in chat_env.env_dict:
                chat_env.env_dict[k] = []
        
        if len(self.seminar_conclusion) > 0:
            # sprint_goals = extract_sprint_trunk_text(self.seminar_conclusion, "Sprint Goals").strip()
            try:
                sprint_backlog = extract_sprint_trunk_text(self.seminar_conclusion, "Sprint backlog").strip()
                sprint_acceptance_criteria = extract_sprint_trunk_text(self.seminar_conclusion, "Sprint acceptance criteria").strip()
            except:
                try:
                    sprint_backlog = extract_sprint_trunk_text(self.seminar_conclusion, "SPRINT_BACKLOG", False).replace(':', '').strip()
                    sprint_acceptance_criteria = extract_sprint_trunk_text(self.seminar_conclusion, "SPRINT_ACCEPTANCE_CRITERIA", False).replace(':', '').strip()
                except: 
                    try:
                        sprint_backlog, sprint_acceptance_criteria = extract_product_requirements(self.seminar_conclusion, False)
                    except: pass
            list_of_sprint_backlog = sprint_backlog.splitlines()
            list_of_sprint_acceptance_criteria = sprint_acceptance_criteria.splitlines()

            chat_env.env_dict['current-programming-task'] = sprint_backlog
            chat_env.env_dict['current-acceptance-criteria'] = sprint_acceptance_criteria

            chat_env.env_dict['current-sprint-backlog'] = list_of_sprint_backlog
            chat_env.env_dict['current-sprint-acceptance-criteria'] = list_of_sprint_acceptance_criteria
            # chat_env.env_dict['current-sprint-goals'] = sprint_goals

            # chat_env.env_dict['all-sprint-backlog'].append(list_of_sprint_backlog)
            # chat_env.env_dict['all-sprint-acceptance-criteria'].append(list_of_sprint_acceptance_criteria)
            # chat_env.env_dict['all-sprint-goals'].append(sprint_goals)
            # chat_env.env_dict['num-sprints'] = chat_env.env_dict.get('num-sprints', 0) + 1
        # print("chat_env.env_dict['current-sprint-backlog']", chat_env.env_dict['current-sprint-backlog'])
        # print("chat_env.env_dict['current-sprint-goals']", chat_env.env_dict['current-sprint-goals'])
        return chat_env

class NextSprintBacklogCreating(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        plain_acceptance_criteria = '\n'.join(chat_env.env_dict['acceptance-criteria'])
        all_done_tasks = '\n'.join(chat_env.env_dict['done-works'])
        all_undone_tasks = '\n'.join(chat_env.env_dict['undone-works'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               "ideas": chat_env.env_dict['ideas'],
                               'plain_product_backlog': plain_product_backlog,
                               'plain_acceptance_criteria': plain_acceptance_criteria,
                               'all_done_tasks': all_done_tasks,
                               'num_sprints': chat_env.env_dict.get('num-sprints', 0),
                               'all_undone_tasks': all_undone_tasks})

    def update_chat_env(self, chat_env) -> ChatEnv:
        if len(self.seminar_conclusion) > 0:
            # print('self.seminar_conclusion', self.seminar_conclusion)
            # sprint_goals = extract_sprint_trunk_text(self.seminar_conclusion, "Sprint Goals").strip()
            try:
                sprint_backlog = extract_sprint_trunk_text(self.seminar_conclusion, "Sprint backlog").strip()
                sprint_acceptance_criteria = extract_sprint_trunk_text(self.seminar_conclusion, "Sprint acceptance criteria").strip()
            except:
                try:
                    sprint_backlog = extract_sprint_trunk_text(self.seminar_conclusion, "SPRINT_BACKLOG", False).replace(':', '').strip()
                    sprint_acceptance_criteria = extract_sprint_trunk_text(self.seminar_conclusion, "SPRINT_ACCEPTANCE_CRITERIA", False).replace(':', '').strip()
                except: 
                    try:
                        sprint_backlog, sprint_acceptance_criteria = extract_product_requirements(self.seminar_conclusion, False)
                    except: pass
            list_of_sprint_backlog = sprint_backlog.splitlines()
            list_of_sprint_acceptance_criteria = sprint_acceptance_criteria.splitlines()

            chat_env.env_dict['current-programming-task'] = sprint_backlog
            chat_env.env_dict['current-acceptance-criteria'] = sprint_acceptance_criteria

            chat_env.env_dict['current-sprint-backlog'] = list_of_sprint_backlog
            chat_env.env_dict['current-sprint-acceptance-criteria'] = list_of_sprint_acceptance_criteria
            # chat_env.env_dict['current-sprint-goals'] = sprint_goals

            chat_env.env_dict['all-sprint-backlog'].append(list_of_sprint_backlog)
            chat_env.env_dict['all-sprint-acceptance-criteria'].append(list_of_sprint_acceptance_criteria)
            # chat_env.env_dict['all-sprint-goals'].append(sprint_goals)
            chat_env.env_dict['num-sprints'] = chat_env.env_dict.get('num-sprints', 0) + 1
            chat_env.reset_all_changed_files()
        # print("chat_env.env_dict['current-sprint-backlog']", chat_env.env_dict['current-sprint-backlog'])
        # print("chat_env.env_dict['current-sprint-goals']", chat_env.env_dict['current-sprint-goals'])
        return chat_env

class CheckProgressStatus(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        plain_acceptance_criteria = '\n'.join(chat_env.env_dict['acceptance-criteria'])
        all_done_tasks = '\n'.join(chat_env.env_dict['done-works'])
        all_undone_tasks = '\n'.join(chat_env.env_dict['undone-works'])
        if all_undone_tasks.strip() == 'None':
            self.phase_prompt = '\n'.join([
                "According to the user's task, our software designs, product backlog and acceptance criteria listed below: ",
                "Task: \"{task}\".",
                "Modality: \"{modality}\".",
                "Programming Language: \"{language}\"",
                "Product backlog:\n\"{plain_product_backlog}\"",
                "Acceptance Criteria:\n\"{plain_acceptance_criteria}\"",
                "We have decided to complete the task through a executable software with multiple files implemented via {language} by accomplishing the product backlog and acceptance criteria through multiple sprints. Here are the tasks that have been completed so far:",
                "Current done tasks:",
                "\"{all_done_tasks}\"",
                "As the {assistant_role}, to satisfy the user's demands, you should carefully decide whether to conclude the project or create a next sprint based on the product backlog, acceptance criteria, done works and undone works.",
                "Specifically, you compare done works with the product backlog to determine whether any items in the product backlog or acceptance criteria are incomplete, and you carefully review undone works to check if the program has any errors.", 
                "When all tasks in the product backlog and acceptance criteria are fully accomplished and the program is completely error-free, you should end the project by returning the response with the content: \"<INFO> DONE.\".",
                "Otherwise, your answer includes the content: \"<INFO> UNDONE.\", indicating that the product backlog has not been accomplished or the program has some existing bugs, so you must create a next sprint to complete remaining tasks and fix all existing bugs.",
                "Importantly, you are not allowed to conclude the project if there is any existing bug.",
                "Think step by step and reason yourself to the right decisions before making a decision to make sure we get it right. Your answer should include reasons to justify your decision.",
                "Additionally, you must adhere to the following regulations:",
                "\t1) the project is concluded only if all the tasks in the product backlog and acceptance criteria are accomplished without any errors,",
                "\t2) if the software has any bugs and errors, you should not conclude the project, and you should focus on making the software executable successfully.",
                "Note that your answer must follow the required format above."
            ])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               "ideas": chat_env.env_dict['ideas'],
                               'plain_product_backlog': plain_product_backlog,
                               'plain_acceptance_criteria': plain_acceptance_criteria,
                               'all_done_tasks': all_done_tasks,
                               'num_sprints': chat_env.env_dict.get('num-sprints', 0),
                               'all_undone_tasks': all_undone_tasks})

    def update_chat_env(self, chat_env) -> ChatEnv:
        if len(self.seminar_conclusion) > 0:
            # print('[CheckProgressStatus] self.seminar_conclusion', self.seminar_conclusion)
            if ' DONE' in self.seminar_conclusion:
                if 'UNDONE' not in self.seminar_conclusion:
                    chat_env.env_dict['end-sprint'] = True
                    return chat_env
        # print("chat_env.env_dict['current-sprint-goals']", chat_env.env_dict['current-sprint-goals'])
        return chat_env


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
                            #    "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
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
                            #    "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               "current_sprint_backlog": chat_env.env_dict['current-sprint-backlog'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               'current_acceptance_criteria': chat_env.env_dict['current-acceptance-criteria'],
                               "gui": gui})

    def update_chat_env(self, chat_env) -> ChatEnv:
        has_correct_format = chat_env.update_codes(self.seminar_conclusion)
        if has_correct_format:
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

class WritingTestSuite(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        gui = "" if not chat_env.config.gui_design \
            else "The software should be equipped with graphical user interface (GUI) so that user can visually and graphically use it; so you must choose a GUI framework (e.g., in Python, you can implement GUI via tkinter, Pygame, Flexx, PyGUI, etc,)."
                # print('chat_env', self.seminar_conclusion)
        # if chat_env.env_dict.get('num-sprints', 0) > 1:
        #     codes =  chat_env.get_changed_codes(find_ancestors(chat_env.dependency_graph, chat_env.get_all_changed_files()),  True) 
        # else:
        #     codes = chat_env.get_codes(simplify_code = True)
        # print('ALL CHANGED FILES:',chat_env.get_all_changed_files())
        log_and_print_online('ALL CHANGED FILES: ' + str(chat_env.get_all_changed_files()))
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "current_sprint_backlog": chat_env.env_dict['current-sprint-backlog'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               'current_acceptance_criteria': chat_env.env_dict['current-acceptance-criteria']
                               })

    def update_chat_env(self, chat_env) -> ChatEnv:
        # print('WritingTestSuite', self.seminar_conclusion)
        chat_env.update_codes(self.seminar_conclusion, is_testing = True, file_name = self.phase_env['current_file_name'])
        if len(chat_env.codes.codebooks.keys()) == 0:
            raise ValueError("No Valid Codes.")
        chat_env.rewrite_codes()
        log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        return chat_env
class CodeFormatting(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"codes": chat_env.env_dict['raw_code_conclusion']})

    def update_chat_env(self, chat_env) -> ChatEnv:
        has_correct_format = chat_env.update_codes(self.seminar_conclusion)
        if has_correct_format:
            chat_env.rewrite_codes()
            log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
            self.phase_env.update({
                'has_correct_format': True
            })
        else:
            self.phase_env.update({
                'has_correct_format': False
            })
        # if len(chat_env.codes.codebooks.keys()) == 0:
        #     raise ValueError("No Valid Codes.")
        # chat_env.rewrite_codes()
        # log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
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
                                "codes": chat_env.get_codes(simplify_code = True),
                            #    "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               "current_sprint_backlog": chat_env.env_dict['current-sprint-backlog'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               'current_acceptance_criteria': chat_env.env_dict['current-acceptance-criteria'],
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
             "codes": chat_env.get_codes(simplify_code = True),
            #   "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
             'current_programming_task': chat_env.env_dict['current-programming-task'],
             'current_acceptance_criteria': chat_env.env_dict['current-acceptance-criteria'],
             "test_reports": chat_env.env_dict['test_reports'],
            "error_summary": chat_env.env_dict['error_summary'],
             "images": ", ".join(chat_env.incorporated_images)})

    def update_chat_env(self, chat_env) -> ChatEnv:
        # chat_env.env_dict['review_comments'] = self.seminar_conclusion
        if len(self.seminar_conclusion):
            coms = self.seminar_conclusion.split('Undone Work:')
            undone_work = coms[1].strip()
            _undone_work = []
            undone_work_lines = undone_work.splitlines()
            for line in undone_work_lines:
                if len(line.strip()) == 0: break
                _undone_work.append(line)
            undone_work = '\n'.join(_undone_work)
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
        done_work_lines = '\n'.join(chat_env.env_dict['done-works']).splitlines()
        _lines = []
        for i, line in enumerate(done_work_lines):
            if len(line.strip()) == 0: continue
            flag = check_if_string_starts_with_number(line)
            if flag == 1:
                _lines.append(re.sub(r'\d+', '', line, count = 1))
            elif flag == 2:
                _lines.append(re.sub(r'-', '', line, count = 1))
            else:
                _lines.append(line)
            while not _lines[-1][0].isalpha():
                _lines[-1] = _lines[-1][1:]
            _lines[-1] = str(i + 1) + '. ' + _lines[-1]
        chat_env.env_dict['done-works'] = _lines
        chat_env.env_dict['undone-works'] = [undone_work]
        # chat_env.env_dict['undone-works'].append(undone_work)
        # print('done work:', done_work)
        # print('undone work:', undone_work)
        return chat_env
class ProductBacklogReview(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        plain_acceptance_criteria = '\n'.join(chat_env.env_dict['acceptance-criteria'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               'plain_product_backlog': plain_product_backlog,
                               'plain_acceptance_criteria': plain_acceptance_criteria
                               })

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.env_dict['product_backlog_comments'] = self.seminar_conclusion.strip()
        return chat_env

class SprintBacklogReview(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        plain_acceptance_criteria = '\n'.join(chat_env.env_dict['acceptance-criteria'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               'plain_product_backlog': plain_product_backlog,
                               'plain_acceptance_criteria': plain_acceptance_criteria,
                                # "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               'current_acceptance_criteria': chat_env.env_dict['current-acceptance-criteria'],})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.env_dict['sprint_backlog_comments'] = self.seminar_conclusion.strip()
        return chat_env
    
class NextSprintBacklogReview(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        plain_acceptance_criteria = '\n'.join(chat_env.env_dict['acceptance-criteria'])
        all_done_tasks = '\n'.join(chat_env.env_dict['done-works'])
        all_undone_tasks = '\n'.join(chat_env.env_dict['undone-works'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               'plain_product_backlog': plain_product_backlog,
                               'plain_acceptance_criteria': plain_acceptance_criteria,
                                # "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               'current_acceptance_criteria': chat_env.env_dict['current-acceptance-criteria'],
                               'all_done_tasks': all_done_tasks,
                               'all_undone_tasks': all_undone_tasks})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env.env_dict['sprint_backlog_comments'] = self.seminar_conclusion.strip()
        return chat_env

class ProductBacklogModification(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        plain_acceptance_criteria = '\n'.join(chat_env.env_dict['acceptance-criteria'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               'plain_product_backlog': plain_product_backlog,
                               'plain_acceptance_criteria': plain_acceptance_criteria,
                               "product_backlog_comments": chat_env.env_dict['product_backlog_comments']})

    def update_chat_env(self, chat_env) -> ChatEnv:
        # print('ProductBacklogModification:', self.seminar_conclusion)
        # if len(self.seminar_conclusion) > 0:
        #     lists_of_backlog_items = self.seminar_conclusion.splitlines()
        #     lst = []
        #     flag = False
        #     for item in lists_of_backlog_items:
        #         if check_if_string_starts_with_number(item):
        #             lst.append(item)
        #             flag = True
        #         elif len(item.strip()) and flag: break
        #         # else: break
        #     chat_env.env_dict['product-backlog'] = lst#list(filter(check_if_string_starts_with_number, lists_of_backlog_items))
        # elif 'product-backlog' not in chat_env.env_dict:
        #     lists_of_backlog_items = self.seminar_conclusion.splitlines()
        #     # chat_env.env_dict['product-backlog'] = list(filter(check_if_string_starts_with_number, lists_of_backlog_items))
        #     lst = []
        #     flag = False
        #     for item in lists_of_backlog_items:
        #         if check_if_string_starts_with_number(item):
        #             lst.append(item)
        #             flag = True
        #         elif len(item.strip()) and flag: break
        #     chat_env.env_dict['product-backlog'] = lst
        # print("chat_env.env_dict['product-backlog']", chat_env.env_dict['product-backlog'])
        # return chat_env
        if len(self.seminar_conclusion) > 0:
            try:
                product_backlog = extract_trunk_text(self.seminar_conclusion, "Product backlog")
                acceptance_criteria = extract_trunk_text(self.seminar_conclusion, "Acceptance criteria")
            except:
                try:
                    product_backlog = extract_trunk_text(self.seminar_conclusion, "PRODUCT_BACKLOG", False).replace(':', '').strip()
                    acceptance_criteria = extract_trunk_text(self.seminar_conclusion, "ACCEPTANCE_CRITERIA", False).replace(':', '').strip()
                except:
                    try:
                        product_backlog, acceptance_criteria = extract_product_requirements(self.seminar_conclusion)
                    except: pass
            chat_env.env_dict['product-backlog'] = product_backlog.strip().splitlines()
            chat_env.env_dict['acceptance-criteria'] = acceptance_criteria.strip().splitlines()
        return chat_env

class SprintBacklogModification(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        plain_acceptance_criteria = '\n'.join(chat_env.env_dict['acceptance-criteria'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               'plain_product_backlog': plain_product_backlog,
                               "product_backlog_comments": chat_env.env_dict['product_backlog_comments'],
                            #    "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               'current_acceptance_criteria': chat_env.env_dict['current-acceptance-criteria'],
                               "sprint_backlog_comments": chat_env.env_dict['sprint_backlog_comments']})

    def update_chat_env(self, chat_env) -> ChatEnv:
        if len(self.seminar_conclusion) > 0:
            # sprint_goals = extract_sprint_trunk_text(self.seminar_conclusion, "Sprint Goals").strip()
            try:
                sprint_backlog = extract_sprint_trunk_text(self.seminar_conclusion, "Sprint backlog").strip()
                sprint_acceptance_criteria = extract_sprint_trunk_text(self.seminar_conclusion, "Sprint acceptance criteria").strip()
            except:
                try:
                    sprint_backlog = extract_sprint_trunk_text(self.seminar_conclusion, "SPRINT_BACKLOG").strip()
                    sprint_acceptance_criteria = extract_sprint_trunk_text(self.seminar_conclusion, "SPRINT_ACCEPTANCE_CRITERIA").strip()
                except: 
                    try:
                        sprint_backlog, sprint_acceptance_criteria = extract_product_requirements(self.seminar_conclusion, False)
                    except: pass
            list_of_sprint_backlog = sprint_backlog.splitlines()
            list_of_sprint_acceptance_criteria = sprint_acceptance_criteria.splitlines()

            chat_env.env_dict['current-programming-task'] = sprint_backlog
            chat_env.env_dict['current-acceptance-criteria'] = sprint_acceptance_criteria

            chat_env.env_dict['current-sprint-backlog'] = list_of_sprint_backlog
            chat_env.env_dict['current-sprint-acceptance-criteria'] = list_of_sprint_acceptance_criteria
            # chat_env.env_dict['current-sprint-goals'] = sprint_goals

            chat_env.env_dict['all-sprint-backlog'].append(list_of_sprint_backlog)
            chat_env.env_dict['all-sprint-acceptance-criteria'].append(list_of_sprint_acceptance_criteria)
            # chat_env.env_dict['all-sprint-goals'].append(sprint_goals)
            chat_env.env_dict['num-sprints'] = chat_env.env_dict.get('num-sprints', 0) + 1
        # print("chat_env.env_dict['current-sprint-backlog']", chat_env.env_dict['current-sprint-backlog'])
        # print("chat_env.env_dict['current-sprint-goals']", chat_env.env_dict['current-sprint-goals'])
        return chat_env
class NextSprintBacklogModification(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        plain_product_backlog = '\n'.join(chat_env.env_dict['product-backlog'])
        plain_acceptance_criteria = '\n'.join(chat_env.env_dict['acceptance-criteria'])
        all_done_tasks = '\n'.join(chat_env.env_dict['done-works'])
        all_undone_tasks = '\n'.join(chat_env.env_dict['undone-works'])
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               'plain_product_backlog': plain_product_backlog,
                               "product_backlog_comments": chat_env.env_dict['product_backlog_comments'],
                            #    "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               'current_acceptance_criteria': chat_env.env_dict['current-acceptance-criteria'],
                               "sprint_backlog_comments": chat_env.env_dict['sprint_backlog_comments'],
                               'all_done_tasks': all_done_tasks,
                                'all_undone_tasks': all_undone_tasks})

    def update_chat_env(self, chat_env) -> ChatEnv:
        if len(self.seminar_conclusion) > 0:
            # sprint_goals = extract_sprint_trunk_text(self.seminar_conclusion, "Sprint Goals").strip()
            try:
                sprint_backlog = extract_sprint_trunk_text(self.seminar_conclusion, "Sprint backlog").strip()
                sprint_acceptance_criteria = extract_sprint_trunk_text(self.seminar_conclusion, "Sprint acceptance criteria").strip()
            except:
                try:
                    sprint_backlog = extract_sprint_trunk_text(self.seminar_conclusion, "SPRINT_BACKLOG").strip()
                    sprint_acceptance_criteria = extract_sprint_trunk_text(self.seminar_conclusion, "SPRINT_ACCEPTANCE_CRITERIA").strip()
                except: 
                    try:
                        sprint_backlog, sprint_acceptance_criteria = extract_product_requirements(self.seminar_conclusion, False)
                    except: pass
            list_of_sprint_backlog = sprint_backlog.splitlines()
            list_of_sprint_acceptance_criteria = sprint_acceptance_criteria.splitlines()

            chat_env.env_dict['current-programming-task'] = sprint_backlog
            chat_env.env_dict['current-acceptance-criteria'] = sprint_acceptance_criteria

            chat_env.env_dict['current-sprint-backlog'] = list_of_sprint_backlog
            chat_env.env_dict['current-sprint-acceptance-criteria'] = list_of_sprint_acceptance_criteria
            # chat_env.env_dict['current-sprint-goals'] = sprint_goals

            chat_env.env_dict['all-sprint-backlog'].append(list_of_sprint_backlog)
            chat_env.env_dict['all-sprint-acceptance-criteria'].append(list_of_sprint_acceptance_criteria)
            # chat_env.env_dict['all-sprint-goals'].append(sprint_goals)
            chat_env.env_dict['num-sprints'] = chat_env.env_dict.get('num-sprints', 0) + 1
        # print("chat_env.env_dict['current-sprint-backlog']", chat_env.env_dict['current-sprint-backlog'])
        # print("chat_env.env_dict['current-sprint-goals']", chat_env.env_dict['current-sprint-goals'])
        return chat_env


def is_method_empty(method_node):
    """
    Check if the given method node has an empty implementation (contains only 'pass').
    """
    if len(method_node.body) == 1 and isinstance(method_node.body[0], ast.Pass):
        return True
    return False

def check_empty_methods_from_text(class_text):
    """
    Check all methods in the class defined by the given text for empty implementation.
    """
    try:
        parsed_code = ast.parse(class_text)
        empty_methods = []
        
        # Traverse the AST to find class definitions
        for node in parsed_code.body:
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        if is_method_empty(item):
                            empty_methods.append(item.name)
        
        return len(empty_methods) > 0
    except: return False

import ast
import os

class AttributeChecker(ast.NodeVisitor):
    def __init__(self):
        self.errors = {}

    def visit_ClassDef(self, node):
        """Visit a class definition and collect attribute definitions."""
        class_name = node.name
        self.errors[class_name] = []

        # Collect attribute definitions in the class body and methods
        class_defs = self._collect_class_definitions(node)

        # Check for undefined attribute usage
        self._check_attribute_usage(node, class_defs, class_name)

    def _collect_class_definitions(self, node):
        """Collect attribute and method definitions in the class."""
        class_defs = {'attributes': set(), 'methods': set()}
        self.class_attrs = []
        for stmt in node.body:
            if isinstance(stmt, ast.FunctionDef):
                class_defs['methods'].add(stmt.name)
            elif isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self':
                        print('das', target.attr)
                        class_defs['attributes'].add(target.attr)
        return class_defs

    def _check_attribute_usage(self, node, class_defs, class_name):
        """Check if attributes accessed are defined in the class."""
        for stmt in node.body:
            if isinstance(stmt, ast.FunctionDef):
                self.generic_visit(stmt)
                for subnode in ast.walk(stmt):
                    if isinstance(subnode, ast.Attribute) and isinstance(subnode.value, ast.Name) and subnode.value.id == 'self':
                        if subnode.attr not in class_defs['attributes'] and subnode.attr not in class_defs['methods'] and subnode.attr not in self.class_attrs:
                            # print(self.class_attrs)
                            self.errors[class_name].append(
                                f"Error: Class '{class_name}' uses undefined attribute '{subnode.attr}' at line {subnode.lineno}"
                            )

    def visit_Assign(self, node):

        for target in node.targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self':
                self.class_attrs.append(target.attr)
        self.generic_visit(node)
    def visit_AnnAssign(self, node):
        target = node.target
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'self':
            self.class_attrs.append(target.attr)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        """Check if attributes accessed are defined in the class."""
        self.generic_visit(node)




def analyze_file(code):
    try:
        tree = ast.parse(code)
    except:
        return {}
    checker = AttributeChecker()
    checker.visit(tree)
    return checker.errors
class CodeReviewComment(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_empty_body_filenames(self, chat_env):
        results = []
        for filename, code in chat_env.codes.codebooks.items():
            if filename.startswith('test') or filename.split('.')[0].endswith('test'): continue
            if check_empty_methods_from_text(code):
                results.append(filename)
        return results
    def get_empty_error(self, chat_env):
        results = self.get_empty_body_filenames(chat_env)
        if len(results):
            text = ', '.join(results)
            return f'\nThe files {text} contain empty body implementations, which is not allowed, so please provide the complete code for these files to correct this issue.'
    def get_missing_attributes(self, chat_env):
        total_error = []
        for filename, code in chat_env.codes.codebooks.items():
            if not filename.endswith('.py'): continue
            if filename.startswith('test') or filename.split('.')[0].endswith('test'): continue
            errors = analyze_file(code)
            for v in errors.values():
                total_error.extend(v)
        if len(total_error):
            return ', '.join(total_error)


    def update_phase_env(self, chat_env):
        
        # codes = chat_env.get_total_changed_lines()
        # chat_env.count_graph_call()
        changed_files = chat_env.get_changed_files()
        if len(changed_files) == 0:
            codes1 = chat_env.get_codes()
        else:
            codes1 = chat_env.get_changed_codes(changed_files)
        # if len(codes1) and len(codes) / len(codes1) > 1.3: 
        codes = codes1
        # print('codescodes:', codes)
        self.image_comment = ''
        if '.png' in codes or '.jpg' in codes:
        #     chat_env.generate_images_from_codes()
            directory = chat_env.env_dict['directory']
        #     # print('directorydirectorydirectory:', directory)
            assets_paths = glob.glob(f'{directory}/*.png') + glob.glob(f'{directory}/*/*.png')
            assets_paths = list(map(lambda x: x.replace(directory, '.'), assets_paths))
            assets_paths = '\n'.join(assets_paths)
            self.image_comment = "\nThere is a serious bug because the source code is using non-existent images. Please remove the corresponding code and consider using a color canvas or drawing objects with colored pixels instead to fix bugs."
        else:
            assets_paths = ''
            

        self.phase_env.update(
            {"task": chat_env.env_dict['task_prompt'],
             "modality": chat_env.env_dict['modality'],
             "ideas": chat_env.env_dict['ideas'],
             "language": chat_env.env_dict['language'],
             "codes": codes,
             "paths": assets_paths,
             'changed_files': changed_files,
            #   "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
             'current_programming_task': chat_env.env_dict['current-programming-task'],
             'current_acceptance_criteria': chat_env.env_dict['current-acceptance-criteria'],
             "images": ", ".join(chat_env.incorporated_images)})

    def update_chat_env(self, chat_env) -> ChatEnv:
        if self.seminar_conclusion.strip() == "Finished.":
            self.phase_env.update({
                'has_no_comment': True
            })
            return chat_env
        results = chat_env.get_high_overlap_code()
        content = "\nThere are high overlap among files: "
        for f1, f2 in results:
            content += f"({f1}, {f2}), "
        content += "\nThus, considering removing redundant code."
        self.seminar_conclusion += self.image_comment
        empty_error = self.get_empty_error(chat_env)
        if empty_error is not None:
            self.seminar_conclusion += "\n" + empty_error
        attr_error = self.get_missing_attributes(chat_env)
        if attr_error is not None:
            self.seminar_conclusion += "\nThere are attribute errors: " + attr_error
        if len(results) > 0:
            chat_env.env_dict['review_comments'] = self.seminar_conclusion + content
        else:
            chat_env.env_dict['review_comments'] = self.seminar_conclusion

        return chat_env

class CodeReviewComment1(CodeReviewComment):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    def update_chat_env(self, chat_env) -> ChatEnv:
        if self.seminar_conclusion.strip() == "Finished.":
            self.phase_env.update({
                'has_no_comment': True
            })
            return chat_env
        invalid_filenames = []
        for filename, code in chat_env.codes.codebooks.items():
            if not filename.endswith('.py'): continue
            if not is_valid_syntax(code):
                invalid_filenames.append(filename)
        if len(invalid_filenames):
            plain_filenames = ', '.join(invalid_filenames)
            invalid_error = f"\nThere is a serious problem regarding syntax errors. Files {plain_filenames} have syntax errors. Please modify them correctly to fix syntax errors."
            self.seminar_conclusion += invalid_error
        
        changed_files = chat_env.get_changed_files()
        if len(changed_files) == 0:
            codes = chat_env.get_codes()
        else:
            codes = chat_env.get_changed_codes(changed_files)

        filepaths = list(set(re.findall(r'"(.*?\.\w+)"', codes) + re.findall(r"'(.*?\.\w+)'", codes)))
        non_paths = []
        has_image = False
        for _filepath in filepaths:
            if not os.path.exists(_filepath):
                if _filepath.split('.')[-1] in ['png', 'jpg', 'jpeg']:
                    has_image = True
                non_paths.append(_filepath)
        if len(non_paths):
            _plain_non_path = ', '.join(non_paths)
            self.seminar_conclusion += f"The code has FileNotFound errors. The files {_plain_non_path} do not exist, so please modify correctly to fix. "
            if has_image:
                self.seminar_conclusion += "Importantly, source code is using non-existent images, so you must remove the corresponding code and consider using a color canvas or drawing objects with colored pixels instead."

        results = chat_env.get_high_overlap_code()
        content = "\nThere are high overlap among files: "
        for f1, f2 in results:
            content += f"({f1}, {f2}), "
        content += "\nThus, considering removing redundant code."
        empty_error = self.get_empty_error(chat_env)
        if empty_error is not None:
            self.seminar_conclusion += "\n" + empty_error
        attr_error = self.get_missing_attributes(chat_env)
        if attr_error is not None:
            self.seminar_conclusion += "\nThere are attribute errors: " + attr_error
        if len(results) > 0:
            chat_env.env_dict['review_comments'] = self.seminar_conclusion + content
        else:
            chat_env.env_dict['review_comments'] = self.seminar_conclusion

        return chat_env
class CodeReviewComment2(CodeReviewComment):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
class CodeReviewComment3(CodeReviewComment):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class CodeReviewModification(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        changed_files = chat_env.get_changed_files()
        if len(changed_files) == 0:
            codes = chat_env.get_codes()
        else:
            codes = chat_env.get_changed_codes(changed_files)
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": codes,
                                # "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               'current_acceptance_criteria': chat_env.env_dict['current-acceptance-criteria'],
                               "comments": chat_env.env_dict['review_comments']})

    def update_chat_env(self, chat_env) -> ChatEnv:
      
        has_correct_format = chat_env.update_codes(self.seminar_conclusion)
        # chat_env.rewrite_codes()
        # log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        if has_correct_format:
            chat_env.rewrite_codes()
            log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
            self.phase_env.update({
                'has_correct_format': True
            })
            self.phase_env['raw_code_conclusion'] = self.seminar_conclusion
        else:
            self.phase_env.update({
                'has_correct_format': False
            })
            chat_env.env_dict['raw_code_conclusion'] = self.seminar_conclusion

        return chat_env
class CodeReview1Modification(CodeReviewModification):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
class CodeReview2Modification(CodeReviewModification):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
class CodeReview3Modification(CodeReviewModification):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
                                # "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               "comments": provided_comments})

    def update_chat_env(self, chat_env) -> ChatEnv:
        if "```".lower() in self.seminar_conclusion.lower():
            chat_env.update_codes(self.seminar_conclusion)
            chat_env.rewrite_codes()
            log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        return chat_env

class TestingPlan(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        # print(
            # f"You can participate in the development of the software {chat_env.env_dict['task_prompt']}. Please input your feedback. (\"End\" to quit the involvement.)")
        # if chat_env.env_dict.get('num-sprints', 0) > 1:
        #     codes = chat_env.get_changed_codes(find_ancestors(chat_env.dependency_graph, chat_env.get_all_changed_files()), True)
        # else:
        # codes = chat_env.get_codes(simplify_code = True, ignore_test_code = True, get_entry_point = True)
        chat_env.count_graph_call()
        if chat_env.dependency_graph is not None:
            file_names = get_non_leaf_and_intermediate_files(chat_env.dependency_graph)
            if len(file_names) == 0:
                codes = chat_env.get_codes(ignore_test_code = False, simplify_code = True)
            else:
                codes = chat_env.get_changed_codes(file_names, True)
        else:
            codes = chat_env.get_codes(ignore_test_code = False, simplify_code = True)
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "language": chat_env.env_dict['language'],
                               "codes": codes,
                                # "current_sprint_goals": chat_env.env_dict['current-sprint-goals'],
                               'current_programming_task': chat_env.env_dict['current-programming-task'],
                               'current_acceptance_criteria': chat_env.env_dict['current-acceptance-criteria'],
                               })

    def update_chat_env(self, chat_env) -> ChatEnv:
        if len(self.seminar_conclusion) > 0:
            commands = re.findall(r"python (\w+\.py)", self.seminar_conclusion)
            existing_commands = list(filter(lambda x: x in chat_env.codes.codebooks, commands))
            chat_env.env_dict['commands'] = existing_commands
            # print('commands', commands)
        return chat_env

class TestErrorSummary(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.errors = {}
    def update_phase_env(self, chat_env):
        # chat_env.generate_images_from_codes()
        (exist_bugs_flag, test_reports) = chat_env.exist_bugs(chat_env)
        # print("======test_reports", test_reports)
        log_and_print_online("======test_reports: " + test_reports)
        file_names = extract_file_names(test_reports, chat_env.env_dict['directory'])
        is_failed_test_case = False
        overwrite_prompt = False
        if 'FileNotFoundError' in test_reports:
            overwrite_prompt = True
            directory = chat_env.env_dict['directory']
            assets_paths = glob.glob(f'{directory}/*.png') + glob.glob(f'{directory}/*/*.png') + glob.glob(f'{directory}/*.jpg') + glob.glob(f'{directory}/*/*.jpg')
            assets_paths = list(map(lambda x: x.replace(directory, '.'), assets_paths))
            
            assets_paths = '\n'.join(assets_paths) or 'None'
            # needed_filepath = re.search(r"'(.+?)'", test_reports).group(1)
            lines = test_reports.splitlines()
            needed_filepaths = []
            # for line in lines:
            #     if 'FileNotFoundError' in line:
            #         try:
            #             needed_filepath = re.search(r'(.*?\.\w+)', line).group(1).replace('"', '').replace("'", '')
            #             if needed_filepath.split('.')[-1] not in ['png', 'jpg', 'jpeg']:
            #                 needed_filepaths.append(needed_filepath)
            #         except:
            #             pass
            # if len(needed_filepaths):
            #     _plain_path = ', '.join(needed_filepaths)
                # error_summary = error_summary + f". File {_plain_path} does not exist, thereby removing code lines related to this file to fix this error."
            
            chat_env.count_file_system_call()
            self.phase_prompt = '\n'.join([
                "Our developed source codes and corresponding test reports are listed below: ",
                "Programming Language: \"{language}\"",
                "Source Codes:",
                "\"{codes}\"",
                "Test Reports of Source Codes:",
                "\"{test_reports}\"",
                "Existing assets' paths:",
                "\"{paths}\"",
                "According to my test reports, please locate and summarize the bugs that cause the problem. You should carefully review source code, test reports and existing assets' paths to figure out problems correctly."
            ])
        else:
            assets_paths = ''
        if 'NameError:' in test_reports or 'ImportError' in test_reports:
            directory = chat_env.env_dict['directory']
            module_dict = get_classes_in_folder(directory)
            module_structure = []
            chat_env.count_class_call()
            for k, classes in module_dict.items():
                if len(classes) == 0: continue
                module_structure.append(k)
                for c in classes:
                    module_structure.append(f'\t- class {c}')
            module_structure = '\n'.join(module_structure)
            overwrite_prompt = True
            self.phase_prompt = '\n'.join([
                "Our developed source codes, corresponding test reports and module structure are listed below: ",
                "Programming Language: \"{language}\"",
                "Buggy Source Codes:",
                "\"{codes}\"",
                "Test Reports of Source Codes:",
                "\"{test_reports}\"",
                "Module Structure:",
                "\"{module_structure}\"",
                "According to my test reports, please locate and summarize the bugs that cause the problem. You should carefully review source code, test reports and available modules to figure out problems correctly."
            ])
        else:
            module_structure = ''
        if len(file_names) and not overwrite_prompt and (file_names[0].startswith('test') or file_names[0].split('.')[0].endswith('test')) and ('lacks an entry point to start' not in test_reports):
            self.phase_prompt = '\n'.join([
                "Our potentially buggy source codes and corresponding test reports are listed below: ",
                "Programming Language: \"{language}\"",
                "Source Codes:",
                "\"{codes}\"",
                "Failed Test Case:",
                "\"{failed_test_case}\""
                "Test Reports of Source Codes:",
                "\"{test_reports}\"",
                "According to my test reports, please locate and summarize the bugs that cause the problem. Importantly, it should be noted that the failed test case may be an incorrect test case, so you should carefully review code, failed test case, sprint backlog and acceptance criteria to figure out problems correctly."
            ])
            overwrite_prompt = True
            is_failed_test_case = True
            chat_env.count_test_case_call()
            find_test_case = False
            try:
                _item = extract_file_names_and_lines(test_reports, chat_env.env_dict['directory'])
                if _item is not None:
                    if len(_item):
                        find_test_case = True
                        _item = _item[0]
                else: raise RuntimeError
            except:
                _item = extract_pytest_file_names(test_reports, chat_env.env_dict['directory'])
                if len(_item):
                    find_test_case = True
                    _item = _item[0]
            
            context = ''
            if find_test_case:
                if _item[0] in chat_env.codes.codebooks:
                    _content = extract_function_from_class(chat_env.codes.codebooks[_item[0]], _item[2])
                    context += "{}\n```{}\n{}\n```\n\n".format(_item[0],
                                                                    "python" if _item[0].endswith(".py") else _item[0].split(".")[
                                                                        -1], _content)
            if len(context) == 0:
                context = chat_env.codes.codebooks[file_names[0]]
            self.phase_env.update({
                'failed_test_case': context
            })
        if 'ModuleNotFoundError' in test_reports and not overwrite_prompt:
            for match in re.finditer(r"No module named '(\S+)'", test_reports, re.DOTALL):
                module = match.group(1)
            modules = list(map(lambda x: '- ' + os.path.basename(x).split('.')[0], glob.glob(chat_env.env_dict['directory'] + '/*.py')))
            modules = '\n'.join(modules)
            chat_env.count_module_call()
            self.phase_prompt = '\n'.join([
                "Our developed source codes, corresponding test reports and available modules are listed below: ",
                "Programming Language: \"{language}\"",
                "Buggy Source Codes:",
                "\"{codes}\"",
                "Test Reports of Source Codes:",
                "\"{test_reports}\"",
                "Available Modules:",
                "\"{modules}\"\n",
                "According to my test reports, please locate and summarize the bugs that cause the problem. You should carefully review source code, test reports and available modules to figure out problems correctly."
                
            ])
        else:
            modules = ''
        if 'AttributeError' in test_reports:
            chat_env.count_attribute_error()
            error_line = test_reports.split('AttributeError')[-1]
            match = re.search(r"'(.+?)'", error_line)
            graph = chat_env.dependency_graph
            if match:
                class_name = match.group(1).split('.')[-1]
                # print('graph', graph)
                if len(file_names):
                    relevant_files = []
                    for _filename in file_names[::-1]:
                        _files = graph.get(_filename, [])
                        for _f in _files:
                            if _f not in relevant_files:
                                relevant_files.append(_f)
                    for file in relevant_files:
                        if 'class ' + class_name in chat_env.codes.codebooks[file]:
                            file_names.append(file)
            else:
                relevant_files = graph.get(file_names[-1], [])
                file_names.extend(relevant_files)
        elif 'TypeError:' in test_reports and 'missing' in test_reports:
            chat_env.count_type_error()
            words = test_reports.strip().split()
            index = words.index('TypeError:')
            class_name = words[index + 1].split('.')[0]
            graph = chat_env.dependency_graph
            # print('graph', graph)
            if len(file_names):
                flag = False
                relevant_files = []
                for _filename in file_names[::-1]:
                    _files = graph.get(_filename, [])
                    for _f in _files:
                        if _f not in relevant_files:
                            relevant_files.append(_f)

                for file in relevant_files:
                    if 'class ' + class_name in chat_env.codes.codebooks[file]:
                        file_names.append(file)
                        flag = True
                if not flag:
                    file_names.extend(relevant_files)
        elif 'ModuleNotFoundError' not in test_reports and 'ImportError' not in test_reports:
            graph = chat_env.dependency_graph
            chat_env.count_other_call()
            if 'lacks an entry point to start' not in test_reports:
                if len(file_names):
                    chat_env.count_graph_call()
                    relevant_files = graph.get(file_names[-1], [])
                    file_names.extend(relevant_files)
        
            # for filename, code in chat_env.codes.codebooks.items():
            #     if class_name.lower() in filename:
            #         file_names.append(filename)
        log_and_print_online('file_names==' + str(file_names))
        if len(file_names):
            if len(file_names) == 1 and (file_names[0].startswith('test') or file_names[0].split('.')[0].endswith('test')):
                graph = chat_env.dependency_graph
                if graph is not None:
                    relevant_files = graph.get(file_names[-1], [])
                    file_names.extend(relevant_files)
            if is_failed_test_case:
                file_names = file_names[1:]
                
            all_relevant_code = chat_env.get_changed_codes(file_names)
        else:
            if chat_env.dependency_graph  is not None:
                chat_env.count_graph_call()
                if test_reports == 'The software run successfully without errors.':
                    file_names = get_non_leaf_and_intermediate_files(chat_env.dependency_graph)
                    if len(file_names) == 0:
                        all_relevant_code = chat_env.get_codes(ignore_test_code = True)
                    else:
                        all_relevant_code = chat_env.get_changed_codes(file_names)
                elif 'the software lacks an entry point to start' in test_reports:
                    file_names = get_non_leaf_and_intermediate_files(chat_env.dependency_graph)
                    if len(file_names) == 0:
                        all_relevant_code = chat_env.get_codes(ignore_test_code = True)
                    else:
                        all_relevant_code = chat_env.get_changed_codes(file_names)
                else:
                    all_relevant_code = chat_env.get_codes(ignore_test_code = True)
            else:
                all_relevant_code = chat_env.get_codes(ignore_test_code = True)
        self.phase_env.update({
                                "task": chat_env.env_dict['task_prompt'],
                                "modality": chat_env.env_dict['modality'],
                                "ideas": chat_env.env_dict['ideas'],
                                "language": chat_env.env_dict['language'],
                                "codes": all_relevant_code,
                                "test_reports": test_reports,
                                "exist_bugs_flag": exist_bugs_flag,
                                "paths": assets_paths,
                                'modules': modules,
                                'module_structure': module_structure
                            })
        log_and_print_online("**[Test Reports]**:\n\n{}".format(test_reports))

    def update_chat_env(self, chat_env) -> ChatEnv:
        # print("self.phase_env['test_reports']", self.phase_env['test_reports'])
        chat_env.env_dict['error_summary'] = self.seminar_conclusion
        chat_env.env_dict['test_reports'] = self.phase_env['test_reports']

        return chat_env

    def execute(self, chat_env, chat_turn_limit, need_reflect) -> ChatEnv:
        self.update_phase_env(chat_env)
        flag = True
        if "ModuleNotFoundError" in self.phase_env['test_reports']:
            local_module = False
            for match in re.finditer(r"No module named '(\S+)'", self.phase_env['test_reports'], re.DOTALL):
                module = match.group(1)
                for file_name in chat_env.codes.codebooks:
                    if module == file_name.split('.')[0]:
                        local_module = True
            if not local_module:
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

class SprintTestErrorSummary(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.errors = {}
    def update_phase_env(self, chat_env):
        # chat_env.generate_images_from_codes()
        (exist_bugs_flag, test_reports) = chat_env.exist_bugs_ignoring_test_cases(chat_env)
        attr_error = self.get_missing_attributes(chat_env)
        if 'software run successfully without errors' in test_reports:
            if attr_error is not None:
                exist_bugs_flag = True
                test_reports = "There are attribute errors: " + attr_error
        else:
            if attr_error is not None:
                exist_bugs_flag = True
                test_reports += attr_error
        # print("======test_reports", test_reports)
        log_and_print_online("======test_reports: " + test_reports)
        file_names = extract_file_names(test_reports, chat_env.env_dict['directory'])
        is_failed_test_case = False
        is_success = "The software run successfully without errors."
        if len(file_names) and (file_names[0].startswith('test') or file_names[0].split('.')[0].endswith('test')) and ('lacks an entry point to start' not in test_reports) and 'ImportError:' not in test_reports:
            self.phase_prompt = '\n'.join([
                "Our potentially buggy source codes and corresponding test reports are listed below: ",
                "Programming Language: \"{language}\"",
                "Source Codes:",
                "\"{codes}\"",
                 "Failed Test Case:",
                "\"{failed_test_case}\""
                "Test Reports of Source Codes:",
                "\"{test_reports}\"",
                "According to my test reports, please locate and summarize the bugs that cause the problem. Importantly, it should be noted that the failed test case may be an incorrect test case, so you should carefully review code, failed test case, sprint backlog and acceptance criteria to figure out problems correctly."
            ])
            is_failed_test_case = True
            find_test_case = False
            try:
                _item = extract_file_names_and_lines(test_reports, chat_env.env_dict['directory'])
                if _item is not None:
                    if len(_item):
                        find_test_case = True
                        _item = _item[0]
                else: raise RuntimeError
            except:
                _item = extract_pytest_file_names(test_reports, chat_env.env_dict['directory'])
                if len(_item):
                    find_test_case = True
                    _item = _item[0]
            
            context = ''
            if find_test_case:
                if _item[0] in chat_env.codes.codebooks:
                    _content = extract_function_from_class(chat_env.codes.codebooks[_item[0]], _item[2])
                    context += "{}\n```{}\n{}\n```\n\n".format(_item[0],
                                                                    "python" if _item[0].endswith(".py") else _item[0].split(".")[
                                                                        -1], _content)
            if len(context) == 0:
                context = chat_env.codes.codebooks[file_names[0]]
            self.phase_env.update({
                'failed_test_case': context
            })
        if 'AttributeError' in test_reports:
            error_line = test_reports.split('AttributeError')[-1]
            match = re.search(r"'(.+?)'", error_line)
            graph = chat_env.dependency_graph
            if match:
                class_name = match.group(1).split('.')[-1]
                # print('graph', graph)
                if len(file_names):
                    relevant_files = []
                    for _filename in file_names[::-1]:
                        _files = graph.get(_filename, [])
                        for _f in _files:
                            if _f not in relevant_files:
                                relevant_files.append(_f)

                    for file in relevant_files:
                        if 'class ' + class_name in chat_env.codes.codebooks[file]:
                            file_names.append(file)
            else:
                relevant_files = graph.get(file_names[-1], [])
                file_names.extend(relevant_files)
        elif 'TypeError:' in test_reports and 'missing' in test_reports:
            words = test_reports.strip().split()
            index = words.index('TypeError:')
            class_name = words[index + 1].split('.')[0]
            graph = chat_env.dependency_graph
            # print('graph', graph)
            if len(file_names):
                flag = False
                relevant_files = []
                for _filename in file_names[::-1]:
                    _files = graph.get(_filename, [])
                    for _f in _files:
                        if _f not in relevant_files:
                            relevant_files.append(_f)

                for file in relevant_files:
                    if 'class ' + class_name in chat_env.codes.codebooks[file]:
                        file_names.append(file)
                        flag = True
                if not flag:
                    file_names.extend(relevant_files)
        elif 'ModuleNotFoundError' not in test_reports and 'ImportError' not in test_reports:
            graph = chat_env.dependency_graph
            if ('the software lacks an entry point to start' not in test_reports) and ('[Error] the testing script lacks an entry point to start.' not in test_reports):
                if len(file_names):
                    relevant_files = graph.get(file_names[-1], [])
                    file_names.extend(relevant_files)
        
            # for filename, code in chat_env.codes.codebooks.items():
            #     if class_name.lower() in filename:
            #         file_names.append(filename)

        if len(file_names):
            all_relevant_code = []
            if len(file_names) == 1 and (file_names[0].startswith('test') or file_names[0].split('.')[0].endswith('test')):
                graph = chat_env.dependency_graph
                if graph is not None:
                    relevant_files = graph.get(file_names[-1], [])
                    file_names.extend(relevant_files)
            if is_failed_test_case:
                file_names = file_names[1:]
                
            all_relevant_code = chat_env.get_changed_codes(file_names)
        else:
            if chat_env.dependency_graph  is not None:
                if test_reports == 'The software run successfully without errors.':
                    file_names = get_non_leaf_and_intermediate_files(chat_env.dependency_graph)
                    if len(file_names) == 0:
                        all_relevant_code = chat_env.get_codes(ignore_test_code = True)
                    else:
                        all_relevant_code = chat_env.get_changed_codes(file_names)
                elif 'the software lacks an entry point to start' in test_reports:
                    file_names = get_non_leaf_and_intermediate_files(chat_env.dependency_graph)
                    if len(file_names) == 0:
                        all_relevant_code = chat_env.get_codes(ignore_test_code = True)
                    else:
                        all_relevant_code = chat_env.get_changed_codes(file_names)
                else:
                    all_relevant_code = chat_env.get_codes(ignore_test_code = True)
            else:
                all_relevant_code = chat_env.get_codes(ignore_test_code = True)
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": all_relevant_code,
                               "test_reports": test_reports,
                               "exist_bugs_flag": exist_bugs_flag})
        log_and_print_online("**[Test Reports]**:\n\n{}".format(test_reports))

    def get_missing_attributes(self, chat_env):
        total_error = []
        for filename, code in chat_env.codes.codebooks.items():
            if not filename.endswith('.py'): continue
            if filename.startswith('test') or filename.split('.')[0].endswith('test'): continue
            errors = analyze_file(code)
            for v in errors.values():
                total_error.extend(v)
        if len(total_error):
            return ' '.join(total_error)
    def update_chat_env(self, chat_env) -> ChatEnv:
        # print("self.phase_env['test_reports']", self.phase_env['test_reports'])
        chat_env.env_dict['error_summary'] = self.seminar_conclusion
        chat_env.env_dict['test_reports'] = self.phase_env['test_reports']

        return chat_env

    def execute(self, chat_env, chat_turn_limit, need_reflect) -> ChatEnv:
        self.update_phase_env(chat_env)
        flag = True
        if "ModuleNotFoundError" in self.phase_env['test_reports']:
            local_module = False
            for match in re.finditer(r"No module named '(\S+)'", self.phase_env['test_reports'], re.DOTALL):
                module = match.group(1)
                for file_name in chat_env.codes.codebooks:
                    if module == file_name.split('.')[0]:
                        local_module = True
            if local_module:
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

def extract_file_names(traceback_str, directory):
    file_names = []
    existing_files = os.listdir(directory)
    # Define a regular expression pattern to match file names in tracebacks
    file_name_pattern = r'File "(.*?)"'
    
    # Use re.finditer to find all matches in the traceback string
    matches = re.finditer(file_name_pattern, traceback_str)
    
    # Extract file names from the matches
    for match in matches:
        file_name = match.group(1)
        if file_name in file_names: continue
        if file_name not in existing_files: continue
        file_names.append(file_name)
    
    return file_names

def extract_file_names_and_lines(traceback_str, directory):
    results = []
    existing_files = os.listdir(directory)
    
    # Define a regular expression pattern to match file names in tracebacks
    file_name_pattern = r'File "(.*?)", line (\d+), in (.+)'
    
    # Use re.finditer to find all matches in the traceback string
    matches = re.finditer(file_name_pattern, traceback_str)
    
    # Extract file names from the matches
    has_match = False
    for match in matches:
        has_match = True
        filename = match.group(1)
        if filename not in existing_files: continue
        results.append((filename, match.group(2), match.group(3)))
    if has_match: return results

def extract_pytest_file_names(traceback, directory):
    lines = traceback.splitlines()
    file_name_pattern = r'File "(.*?)"'
    existing_files = os.listdir(directory)
    results = []
    filename = None
    for line in lines:
        x = re.search(file_name_pattern, line)
        if x is not None:
            filename = x.group(1)
            continue
        if line.startswith('____'): 
            function_name = re.findall(r"(\w+)", line)[1]
            if filename is not None and filename in existing_files:
                results.append((filename, None, function_name))
    return results



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
        code_sections.append((language, '```' + code + '\n```'))
    
    return code_sections
class TestModification(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.force_unsplit = True

    def update_phase_env(self, chat_env):
        test_reports = chat_env.env_dict['test_reports']
        error_summary = chat_env.env_dict['error_summary']
        overwrite_prompt = False
        log_and_print_online('graph: ' + str(chat_env.dependency_graph))
        if 'FileNotFoundError' in test_reports:
            overwrite_prompt = True
            directory = chat_env.env_dict['directory']
            assets_paths = glob.glob(f'{directory}/*.png') + glob.glob(f'{directory}/*/*.png') + glob.glob(f'{directory}/*.jpg') + glob.glob(f'{directory}/*/*.jpg')
            assets_paths = list(map(lambda x: x.replace(directory, '.'), assets_paths))
            
            assets_paths = '\n'.join(assets_paths)
            # needed_filepath = re.search(r"'(.+?)'", test_reports).group(1)
            lines = test_reports.splitlines()
            needed_filepaths = []
            has_image = False
            for line in lines:
                if 'FileNotFoundError' in line:
                    try:
                        needed_filepath = re.search(r'(.*?\.\w+)', line).group(1).replace('"', '').replace("'", '')
                        if needed_filepath.split('.')[-1] not in ['png', 'jpg', 'jpeg']:
                            has_image = True
                        needed_filepaths.append(needed_filepath)
                    except:
                        pass
            if len(needed_filepaths):
                _plain_path = ', '.join(needed_filepaths)
                error_summary = error_summary + f". File {_plain_path} does not exist, thereby removing corresponding code lines related to this file to fix this error."
                if has_image:
                    error_summary += "Importantly, source code is using non-existent images, so the only way to fix this bug is that you must remove the corresponding code and consider using a color canvas or drawing objects with colored pixels instead."
            
            chat_env.count_file_system_call()
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
            chat_env.count_class_call()
            for k, classes in module_dict.items():
                if len(classes) == 0: continue
                module_structure.append(k)
                for c in classes:
                    module_structure.append(f'\t- class {c}')
            module_structure = '\n'.join(module_structure)
            overwrite_prompt = True
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
        file_names = extract_file_names(test_reports, chat_env.env_dict['directory'])
        is_failed_test_case = False
        # print('file_names:', file_names)
        if len(file_names) and not overwrite_prompt and (file_names[0].startswith('test') or file_names[0].split('.')[0].endswith('test')) and ('testing script lacks an entry point to start' not in test_reports):
            self.phase_prompt = '\n'.join([
                "Our potentially buggy source codes and corresponding test reports are listed below:",
                "Programming Language: \"{language}\"",
                "Potentially Buggy Source Codes:",
                "\"{codes}\"",
                "Failed Test Case:",
                "\"{failed_test_case}\""
                "Test Reports of Source Codes:",
                "\"{test_reports}\"",
                "Error Summary of Test Reports:",
                "\"{error_summary}\"",
                "Note that each file must strictly follow a markdown code block format, where the following tokens must be replaced such that FILENAME is the lowercase file name including the file extension, LANGUAGE in the programming language, DOCSTRING is a string literal specified in source code that is used to document a specific segment of code, and CODE is the original code:",
                "FILENAME",
                "```LANGUAGE",
                "'''",
                "DOCSTRING",
                "'''",
                "CODE",
                "```",
                "As the {assistant_role}, to satisfy the new user's demand and make the software execute smoothly and robustly, you should modify the codes based on the failed test case and the error summary.",
                "Now, use the format exemplified above and modify the problematic codes based on the failed test case and error summary. If you cannot find the assets from the existing paths, you should consider remove relevant code and features. Output the codes that you fixed based on the test reported and corresponding explanations (strictly follow the format defined above, including FILENAME, LANGUAGE, DOCSTRING and CODE; incomplete \"TODO\" codes are strictly prohibited). Your answer just includes changed codes and is prohibited from repeating unchanged codes. If no bugs are reported, please return only one line like \"<INFO> Finished\"."
            ])
            overwrite_prompt = True
            is_failed_test_case = True
            chat_env.count_test_case_call()
            find_test_case = False
            try:
                _item = extract_file_names_and_lines(test_reports, chat_env.env_dict['directory'])
                if _item is not None:
                    if len(_item):
                        find_test_case = True
                        _item = _item[0]
                else: raise RuntimeError
            except:
                _item = extract_pytest_file_names(test_reports, chat_env.env_dict['directory'])
                if len(_item):
                    find_test_case = True
                    _item = _item[0]
            
            context = ''
            if find_test_case:
                if _item[0] in chat_env.codes.codebooks:
                    _content = extract_function_from_class(chat_env.codes.codebooks[_item[0]], _item[2])
                    context += "{}\n```{}\n{}\n```\n\n".format(_item[0],
                                                                    "python" if _item[0].endswith(".py") else _item[0].split(".")[
                                                                        -1], _content)
            if len(context) == 0:
                context = chat_env.codes.codebooks[file_names[0]]
            self.phase_env.update({
                'failed_test_case': context
            })
        # print('file_names', file_names)
        # log_and_print_online('BUGGY CONTEXT: ' + context)
        if 'ModuleNotFoundError' in test_reports and not overwrite_prompt:
            for match in re.finditer(r"No module named '(\S+)'", test_reports, re.DOTALL):
                module = match.group(1)
            modules = list(map(lambda x: '- ' + os.path.basename(x).split('.')[0], glob.glob(chat_env.env_dict['directory'] + '/*.py')))
            modules = '\n'.join(modules)
            chat_env.count_module_call()
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
                "\"{modules}\"\n"
                "Note that each file must strictly follow a markdown code block format, where the following tokens must be replaced such that \"FILENAME\" is the lowercase file name including the file extension, \"LANGUAGE\" in the programming language, \"DOCSTRING\" is a string literal specified in source code that is used to document a specific segment of code, and \"CODE\" is the original code:",
                "FILENAME",
                "```LANGUAGE",
                "'''",
                "DOCSTRING",
                "'''",
                "CODE",
                "```",
                "Example of the format:",
                "a.py",
                "```python",
                "def f():",
                "'''",
                "an empty function",
                "'''",
                "    pass",
                "```",
                "As the {assistant_role}, to satisfy the new user's demand and make the software execute smoothly and robustly, you should modify the codes based on the error summary.",
                "There is a raised issue relevant to ModuleNotFoundError because you have not implemented the required module {missing_module}. To fix this error, you must take a great care to current source code to implement the module {missing_module} accurately.",
                "Now, use the format exemplified above and modify the problematic codes based on the error summary. If you cannot find the assets from the existing paths, you should consider remove relevant code and features. Output the codes that you fixed based on the test reported and corresponding explanations (strictly follow the format defined above, including FILENAME, LANGUAGE, DOCSTRING and CODE where FILENAME is the file name, LANGUAGE is the programming language and CODE is the source code; incomplete \"TODO\" codes are strictly prohibited). If no bugs are reported, please return only one line like \"<INFO> Finished\"."
            ])
        elif 'AttributeError' in test_reports:
            chat_env.count_attribute_error()
            error_line = test_reports.split('AttributeError')[-1]
            match = re.search(r"'(.+?)'", error_line)
            graph = chat_env.dependency_graph
            if match:
                class_name = match.group(1).split('.')[-1]
                # print('graph', graph)
                if len(file_names):
                    relevant_files = []
                    for _filename in file_names[::-1]:
                        _files = graph.get(_filename, [])
                        for _f in _files:
                            if _f not in relevant_files:
                                relevant_files.append(_f)

                    for file in relevant_files:
                        if 'class ' + class_name in chat_env.codes.codebooks[file]:
                            file_names.append(file)
            else:
                relevant_files = graph.get(file_names[-1], [])
                file_names.extend(relevant_files)
        elif 'TypeError:' in test_reports and 'missing' in test_reports:
            words = test_reports.strip().split()
            index = words.index('TypeError:')
            class_name = words[index + 1].split('.')[0]
            graph = chat_env.dependency_graph
            # print('graph', graph)
            chat_env.count_type_error()
            if len(file_names):
                flag = False
                relevant_files = []
                for _filename in file_names[::-1]:
                    _files = graph.get(_filename, [])
                    for _f in _files:
                        if _f not in relevant_files:
                            relevant_files.append(_f)

                for file in relevant_files:
                    if 'class ' + class_name in chat_env.codes.codebooks[file]:
                        file_names.append(file)
                        flag = True
                if not flag:
                    file_names.extend(relevant_files)
        elif 'ModuleNotFoundError' not in test_reports and 'ImportError' not in test_reports:
            graph = chat_env.dependency_graph
            chat_env.count_other_call()
            if ('[Error] the software lacks an entry point to start' not in test_reports) and ('[Error] the testing script lacks an entry point to start.' not in test_reports):
                if len(file_names):
                    relevant_files = graph.get(file_names[-1], [])
                    file_names.extend(relevant_files)
                    chat_env.count_graph_call()
            
            # for filename, code in chat_env.codes.codebooks.items():
            #     if class_name.lower() in filename:
            #         file_names.append(filename)
        
        if len(file_names):
            if len(file_names) == 1 and (file_names[0].startswith('test') or file_names[0].split('.')[0].endswith('test')):
                graph = chat_env.dependency_graph
                if graph is not None:
                    relevant_files = graph.get(file_names[-1], [])
                    file_names.extend(relevant_files)
            if is_failed_test_case:
                file_names = file_names[1:]
            all_relevant_code = chat_env.get_changed_codes(file_names)
            # print('all_relevant_code', all_relevant_code)
        else:
            if chat_env.dependency_graph  is not None:
                chat_env.count_graph_call()
                if test_reports == 'The software run successfully without errors.':
                    file_names = get_non_leaf_and_intermediate_files(chat_env.dependency_graph)
                    if len(file_names) == 0:
                        all_relevant_code = chat_env.get_codes(ignore_test_code = True)
                    else:
                        all_relevant_code = chat_env.get_changed_codes(file_names)
                elif 'the software lacks an entry point to start' in test_reports:
                    file_names = get_non_leaf_and_intermediate_files(chat_env.dependency_graph)
                    if len(file_names) == 0:
                        all_relevant_code = chat_env.get_codes(ignore_test_code = True)
                    else:
                        all_relevant_code = chat_env.get_changed_codes(file_names)
                else:
                    all_relevant_code = chat_env.get_codes(ignore_test_code = True)
            else:
                all_relevant_code = chat_env.get_codes(ignore_test_code = True)
            # print('=====all_relevant_code', all_relevant_code)
        
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "test_reports": test_reports,
                               "error_summary": error_summary,
                               "paths": assets_paths,
                               "codes": all_relevant_code,
                               "module_structure": module_structure,
                               'missing_module': module,
                               'modules': modules
                               })

    def update_chat_env(self, chat_env) -> ChatEnv:
        # log_and_print_online("TEST MODIFICATION:", self.seminar_conclusion)
       
        has_correct_format = chat_env.update_codes(self.seminar_conclusion)
        # chat_env.rewrite_codes()
        # log_and_print_online("**[Software Info]**:\n\n {}".format(get_info(chat_env.env_dict['directory'],self.log_filepath)))
        if has_correct_format:
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
        return chat_env
class EnvironmentDoc(Phase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env.update({"task": chat_env.env_dict['task_prompt'],
                               "modality": chat_env.env_dict['modality'],
                               "ideas": chat_env.env_dict['ideas'],
                               "language": chat_env.env_dict['language'],
                               "codes": chat_env.get_codes(simplify_code = True)})

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
                               "codes": chat_env.get_codes(simplify_code = True),
                               "requirements": chat_env.get_requirements()})

    def update_chat_env(self, chat_env) -> ChatEnv:
        chat_env._update_manuals(self.seminar_conclusion)
        chat_env.rewrite_manuals()
        return chat_env

class SolutionDesign(Phase):
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

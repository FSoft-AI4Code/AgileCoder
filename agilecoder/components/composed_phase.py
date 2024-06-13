import importlib
import os
from abc import ABC, abstractmethod
from collections import defaultdict
import copy
import concurrent.futures
from agilecoder.camel.typing import ModelType
from agilecoder.components.chat_env import ChatEnv
from agilecoder.components.utils import log_and_print_online, find_ancestors
from copy import deepcopy

def check_bool(s):
    return s.lower() == "true"


class ComposedPhase(ABC):
    def __init__(self,
                 phase_name: str = None,
                 cycle_num: int = None,
                 composition: list = None,
                 config_phase: dict = None,
                 config_role: dict = None,
                 model_type: ModelType = ModelType.GPT_3_5_TURBO,
                 log_filepath: str = ""
                 ):
        """

        Args:
            phase_name: name of this phase
            cycle_num: loop times of this phase
            composition: list of SimplePhases in this ComposePhase
            config_phase: configuration of all SimplePhases
            config_role: configuration of all Roles
        """

        self.phase_name = phase_name
        self.cycle_num = cycle_num
        self.composition = composition
        self.model_type = model_type
        self.log_filepath = log_filepath

        self.config_phase = config_phase
        self.config_role = config_role

        self.phase_env = dict()

        # init chat turn
        self.chat_turn_limit_default = 10

        # init role
        self.role_prompts = dict()
        for role in self.config_role:
            self.role_prompts[role] = "\n".join(self.config_role[role])
        self.compose_phase_module = importlib.import_module("agilecoder.components.composed_phase")
        # init all SimplePhases instances in this ComposedPhase
        self.phases = dict()
        for phase in self.config_phase:
            assistant_role_name = self.config_phase[phase]['assistant_role_name']
            user_role_name = self.config_phase[phase]['user_role_name']
            phase_prompt = "\n".join(self.config_phase[phase]['phase_prompt'])
            phase_module = importlib.import_module("agilecoder.components.phase")
            phase_class = getattr(phase_module, phase)
            phase_instance = phase_class(assistant_role_name=assistant_role_name,
                                         user_role_name=user_role_name,
                                         phase_prompt=phase_prompt,
                                         role_prompts=self.role_prompts,
                                         phase_name=phase,
                                         model_type=self.model_type,
                                         log_filepath=self.log_filepath)
            self.phases[phase] = phase_instance

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

    @abstractmethod
    def break_cycle(self, phase_env) -> bool:
        """
        special conditions for early break the loop in ComposedPhase
        Args:
            phase_env: phase environment

        Returns: None

        """
        pass

    def execute(self, chat_env) -> ChatEnv:
        """
        similar to Phase.execute, but add control for breaking the loop
        1. receive information from environment(ComposedPhase): update the phase environment from global environment
        2. for each SimplePhase in ComposedPhase
            a) receive information from environment(SimplePhase)
            b) check loop break
            c) execute the chatting
            d) change the environment(SimplePhase)
            e) check loop break
        3. change the environment(ComposedPhase): update the global environment using the conclusion

        Args:
            chat_env: global chat chain environment

        Returns:

        """
        self.update_phase_env(chat_env)
        for cycle_index in range(self.cycle_num):
            for phase_item in self.composition:
                if phase_item["phaseType"] == "SimplePhase":  # right now we do not support nested composition
                    phase = phase_item['phase']
                    max_turn_step = phase_item['max_turn_step']
                    need_reflect = check_bool(phase_item['need_reflect'])
                    log_and_print_online(
                        f"**[Execute Detail]**\n\nexecute SimplePhase:[{phase}] in ComposedPhase:[{self.phase_name}], cycle {cycle_index}")
                    if phase in self.phases:
                        self.phases[phase].phase_env = self.phase_env
                        self.phases[phase].update_phase_env(chat_env)
                        
                        if self.break_cycle(self.phases[phase].phase_env):
                            return chat_env
                        
                        if phase in ['ProductBacklogModification', 'SprintBacklogModification', 'SprintReview', 'NextSprintBacklogCreating']:
                            for i in range(3):
                                try:
                                    _chat_env = copy.deepcopy(chat_env)
                                    _chat_env = self.phases[phase].execute(_chat_env,
                                                                        self.chat_turn_limit_default if max_turn_step <= 0 else max_turn_step,
                                                                        need_reflect)
                                    chat_env = _chat_env
                                    break
                                except: 
                                    pass
                        else:
                            chat_env = self.phases[phase].execute(chat_env,
                                                                        self.chat_turn_limit_default if max_turn_step <= 0 else max_turn_step,
                                                                        need_reflect)
                        # print('@' * 20)
                        # print('self.phases[phase].phase_env', self.phases[phase].phase_env)
                        if self.break_cycle(self.phases[phase].phase_env):
                            return chat_env
                        # chat_env = self.phases[phase].update_chat_env(chat_env)
                        if chat_env.env_dict.get('end-sprint', False):
                            return chat_env
                    else:
                        print(f"Phase '{phase}' is not yet implemented. \
                                Please write its config in phaseConfig.json \
                                and implement it in components.phase")
                elif phase_item['phaseType'] == 'ComposedPhase':
                    phase = phase_item['phase']
                    cycle_num = phase_item['cycleNum']
                    composition = phase_item['Composition']
                    compose_phase_class = getattr(self.compose_phase_module, phase)
                    compose_phase_instance = compose_phase_class(phase_name=phase,
                                                         cycle_num=cycle_num,
                                                         composition=composition,
                                                         config_phase=self.config_phase,
                                                         config_role=self.config_role,
                                                         model_type=self.model_type,
                                                         log_filepath=self.log_filepath)
                    chat_env = compose_phase_instance.execute(chat_env)
                else:
                    raise NotImplementedError
                

        chat_env = self.update_chat_env(chat_env)
        return chat_env

class ProductBacklogUpdate(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        pass

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, phase_env) -> bool:
        return 'Finished.' == phase_env.get('product_backlog_comments', '')
        

class SprintCompletion(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        pass

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, chat_env) -> bool:
        return False

class Art(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        pass

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, chat_env) -> bool:
        return False


class CodeCompleteAll(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        pyfiles = [filename for filename in os.listdir(chat_env.env_dict['directory']) if filename.endswith(".py")]
        num_tried = defaultdict(int)
        num_tried.update({filename: 0 for filename in pyfiles})
        self.phase_env = {
            "max_num_implement": 5,
            "pyfiles": pyfiles,
            "num_tried": num_tried
        }

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, phase_env) -> bool:
        if phase_env['unimplemented_file'] == "":
            return True
        else:
            return False


class CodeReviewChain(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        pass

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, phase_env) -> bool:
        return False

class CodeReview(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env = {"modification_conclusion": ""}

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, phase_env) -> bool:
        if phase_env.get('has_no_comment', False): return True
        if len(phase_env['changed_files']) == 0: return True
        return False

class SprintBacklogUpdate(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env = {"modification_conclusion": ""}

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, phase_env) -> bool:
        return "Finished." == phase_env.get('sprint_backlog_comments', '')


class Test(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env = dict()

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, phase_env) -> bool:
        if not phase_env.get('exist_bugs_flag', True):
            log_and_print_online(f"**[Test Info]**\n\nAI User (Software Test Engineer):\nTest Pass!\n")
            return True
        else:
            return False
class CodeAndFormat(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env = dict()

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, phase_env) -> bool:
        # print('phase_env', 'has_correct_format' in phase_env, phase_env.get('has_correct_format',  False))
        if 'has_correct_format' in phase_env and phase_env['has_correct_format']:
            return True
        else:
            log_and_print_online(f"**[CodeAndFormat Info]**: cannot parse the output!\n")
            return False
    def execute(self, chat_env) -> ChatEnv:
        """
        similar to Phase.execute, but add control for breaking the loop
        1. receive information from environment(ComposedPhase): update the phase environment from global environment
        2. for each SimplePhase in ComposedPhase
            a) receive information from environment(SimplePhase)
            b) check loop break
            c) execute the chatting
            d) change the environment(SimplePhase)
            e) check loop break
        3. change the environment(ComposedPhase): update the global environment using the conclusion

        Args:
            chat_env: global chat chain environment

        Returns:

        """
        self.update_phase_env(chat_env)
        for cycle_index in range(self.cycle_num):
            for phase_item in self.composition:
                if phase_item["phaseType"] == "SimplePhase":  # right now we do not support nested composition
                    phase = phase_item['phase']
                    max_turn_step = phase_item['max_turn_step']
                    need_reflect = check_bool(phase_item['need_reflect'])
                    log_and_print_online(
                        f"**[Execute Detail]**\n\nexecute SimplePhase:[{phase}] in ComposedPhase:[{self.phase_name}], cycle {cycle_index}")
                    if phase in self.phases:
                        self.phases[phase].phase_env = self.phase_env
                        self.phases[phase].update_phase_env(chat_env)
                        
                        if self.break_cycle(self.phases[phase].phase_env):
                            return chat_env
                        
                        counter = 0
                        while not self.break_cycle(self.phases[phase].phase_env) and counter < 3:
                            log_and_print_online('TEST FORMAT COUNTER: ' + str(counter))
                            _chat_env = copy.deepcopy(chat_env)
                            try:
                                _chat_env = self.phases[phase].execute(_chat_env,
                                                                        self.chat_turn_limit_default if max_turn_step <= 0 else max_turn_step,
                                                                        need_reflect)
                            except:
                                pass
                            counter += 1
                        chat_env = _chat_env
                        # print('@' * 20)
                        # print('self.phases[phase].phase_env', self.phases[phase].phase_env)
                        if self.break_cycle(self.phases[phase].phase_env):
                            return chat_env
                        # chat_env = self.phases[phase].update_chat_env(chat_env)
                        if chat_env.env_dict.get('end-sprint', False):
                            return chat_env
                    else:
                        print(f"Phase '{phase}' is not yet implemented. \
                                Please write its config in phaseConfig.json \
                                and implement it in components.phase")
                elif phase_item['phaseType'] == 'ComposedPhase':
                    phase = phase_item['phase']
                    cycle_num = phase_item['cycleNum']
                    composition = phase_item['Composition']
                    compose_phase_class = getattr(self.compose_phase_module, phase)
                    compose_phase_instance = compose_phase_class(phase_name=phase,
                                                         cycle_num=cycle_num,
                                                         composition=composition,
                                                         config_phase=self.config_phase,
                                                         config_role=self.config_role,
                                                         model_type=self.model_type,
                                                         log_filepath=self.log_filepath)
                    chat_env = compose_phase_instance.execute(chat_env)
                else:
                    raise NotImplementedError
                

        chat_env = self.update_chat_env(chat_env)
        return chat_env
class BugFixing(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env = dict()

    def update_chat_env(self, chat_env):
        chat_env.env_dict.pop('testing_commands')
        return chat_env
    def break_cycle(self, phase_env) -> bool:
        return False
    def execute(self, chat_env) -> ChatEnv:
        """
        similar to Phase.execute, but add control for breaking the loop
        1. receive information from environment(ComposedPhase): update the phase environment from global environment
        2. for each SimplePhase in ComposedPhase
            a) receive information from environment(SimplePhase)
            b) check loop break
            c) execute the chatting
            d) change the environment(SimplePhase)
            e) check loop break
        3. change the environment(ComposedPhase): update the global environment using the conclusion

        Args:
            chat_env: global chat chain environment

        Returns:

        """
        self.update_phase_env(chat_env)
        while len(chat_env.env_dict.get('testing_commands', [None])):
            for phase_item in self.composition:
                log_and_print_online("BUGFIXING:" + str(phase_item))
                # print("BUGFIXING:", phase_item)
                if phase_item["phaseType"] == "SimplePhase":  # right now we do not support nested composition
                    phase = phase_item['phase']
                    max_turn_step = phase_item['max_turn_step']
                    need_reflect = check_bool(phase_item['need_reflect'])
                    log_and_print_online(
                        f"**[Execute Detail]**\n\nexecute SimplePhase:[{phase}] in ComposedPhase:[{self.phase_name}]")
                    if phase in self.phases:
                        self.phases[phase].phase_env = self.phase_env
                        if phase_item['phase'] != 'TestErrorSummary':
                            self.phases[phase].update_phase_env(chat_env)
                     
                        chat_env = self.phases[phase].execute(chat_env,
                                                            self.chat_turn_limit_default if max_turn_step <= 0 else max_turn_step,
                                                            need_reflect)
                        log_and_print_online("chat_env.env_dict['test_reports']: " + chat_env.env_dict['test_reports'])
                        if chat_env.env_dict['test_reports'] == 'The software run successfully without errors.':
                            break
                        # print('@' * 20)
                        # print('self.phases[phase].phase_env', self.phases[phase].phase_env)
                       
                        # chat_env = self.phases[phase].update_chat_env(chat_env)
                        if chat_env.env_dict.get('end-sprint', False):
                            return chat_env
                    else:
                        print(f"Phase '{phase}' is not yet implemented. \
                                Please write its config in phaseConfig.json \
                                and implement it in components.phase")
                elif phase_item['phaseType'] == 'ComposedPhase':
                    phase = phase_item['phase']
                    cycle_num = phase_item['cycleNum']
                    composition = phase_item['Composition']
                    compose_phase_class = getattr(self.compose_phase_module, phase)
                    compose_phase_instance = compose_phase_class(phase_name=phase,
                                                         cycle_num=cycle_num,
                                                         composition=composition,
                                                         config_phase=self.config_phase,
                                                         config_role=self.config_role,
                                                         model_type=self.model_type,
                                                         log_filepath=self.log_filepath)
                    chat_env = compose_phase_instance.execute(chat_env)
                else:
                    raise NotImplementedError
                

        chat_env = self.update_chat_env(chat_env)
        return chat_env

def write_a_single_instance(phase, chat_env, turn_limit, need_reflect):
    return phase.phase_env['current_file_name'], phase.execute(chat_env, turn_limit, need_reflect)

class WritingFullTestSuite(ComposedPhase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_phase_env(self, chat_env):
        self.phase_env = dict()

    def update_chat_env(self, chat_env):
        return chat_env

    def break_cycle(self, phase_env) -> bool:
        return False
    def execute(self, chat_env) -> ChatEnv:
        """
        similar to Phase.execute, but add control for breaking the loop
        1. receive information from environment(ComposedPhase): update the phase environment from global environment
        2. for each SimplePhase in ComposedPhase
            a) receive information from environment(SimplePhase)
            b) check loop break
            c) execute the chatting
            d) change the environment(SimplePhase)
            e) check loop break
        3. change the environment(ComposedPhase): update the global environment using the conclusion

        Args:
            chat_env: global chat chain environment

        Returns:

        """
        self.update_phase_env(chat_env)

        all_changed_files = find_ancestors(chat_env.dependency_graph, deepcopy(list(chat_env.get_all_changed_files())))
        if len(all_changed_files) == 0: return chat_env
        futures = []
        max_workers = min(len(all_changed_files), 5)
        with concurrent.futures.ThreadPoolExecutor(max_workers = max_workers) as executor:
            for file_name in all_changed_files:
                if file_name.startswith('test') or file_name.split('.')[0].endswith('test'): continue
                for phase_item in self.composition:
                    if phase_item["phaseType"] == "SimplePhase":  # right now we do not support nested composition
                        phase = phase_item['phase']
                        max_turn_step = phase_item['max_turn_step']
                        need_reflect = check_bool(phase_item['need_reflect'])
                        log_and_print_online(
                            f"**[Execute Detail]**\n\nexecute SimplePhase:[{phase}] in ComposedPhase:[{self.phase_name}]")
                        if phase in self.phases:
                            untested_code = chat_env.get_changed_codes([file_name], True)
                            code_dependencies = chat_env.get_changed_codes(chat_env.dependency_graph.get(file_name, []), True)
                            _phase = deepcopy(self.phases[phase])
                            _phase.phase_env.update({
                                'code_dependencies': code_dependencies,
                                'untested_code': untested_code,
                                'current_file_name': file_name
                            })
                            futures.append(executor.submit(write_a_single_instance, _phase, deepcopy(chat_env), self.chat_turn_limit_default if max_turn_step <= 0 else max_turn_step, need_reflect))
                            # chat_env = self.phases[phase].execute(chat_env,
                            #                                     self.chat_turn_limit_default if max_turn_step <= 0 else max_turn_step,
                            #                                     need_reflect)
                            
                            
                            # print('@' * 20)
                            # print('self.phases[phase].phase_env', self.phases[phase].phase_env)
                        
                            # chat_env = self.phases[phase].update_chat_env(chat_env)
                            
                        else:
                            print(f"Phase '{phase}' is not yet implemented. \
                                    Please write its config in phaseConfig.json \
                                    and implement it in components.phase")
                    elif phase_item['phaseType'] == 'ComposedPhase':
                        phase = phase_item['phase']
                        cycle_num = phase_item['cycleNum']
                        composition = phase_item['Composition']
                        compose_phase_class = getattr(self.compose_phase_module, phase)
                        compose_phase_instance = compose_phase_class(phase_name=phase,
                                                            cycle_num=cycle_num,
                                                            composition=composition,
                                                            config_phase=self.config_phase,
                                                            config_role=self.config_role,
                                                            model_type=self.model_type,
                                                            log_filepath=self.log_filepath)
                        chat_env = compose_phase_instance.execute(chat_env)
                    else:
                        raise NotImplementedError
        results = []
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
        testing_file_map = {}
        for filename, result in results:
            _files = set(filter(lambda x: x.startswith('test') or x.split('.')[0].endswith('test'), result.get_changed_files()))
            if len(_files):
                testing_file_map[filename] = list(_files)
            # print('[FILENAME]:', filename, result.codes.codebooks.keys())
            chat_env.codes.codebooks.update(result.codes.codebooks)
        chat_env.rewrite_codes()
        for key, value in testing_file_map.items():
            chat_env.testing_file_map[key] = chat_env.testing_file_map.get(key, []) + value
        chat_env = self.update_chat_env(chat_env)
        return chat_env
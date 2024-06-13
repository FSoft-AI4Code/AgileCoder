import os
import re
import shutil
import signal
import json
import subprocess
import time
from typing import Dict, Tuple

import openai
import requests

from agilecoder.components.codes import Codes
from agilecoder.components.documents import Documents
from agilecoder.components.roster import Roster
from agilecoder.components.utils import log_and_print_online, extract_first_error_traceback, extract_top_k_errors
from agilecoder.camel.dependency import build_dependency_graph, get_test_order

class ChatEnvConfig:
    def __init__(self, clear_structure,
                 brainstorming,
                 gui_design,
                 git_management):
        self.clear_structure = clear_structure
        self.brainstorming = brainstorming
        self.gui_design = gui_design
        self.git_management = git_management

    def __str__(self):
        string = ""
        string += "ChatEnvConfig.clear_structure: {}\n".format(self.clear_structure)
        string += "ChatEnvConfig.brainstorming: {}\n".format(self.brainstorming)
        return string

import ast

def has_entry_point(code):
    try:
        tree = ast.parse(code)

        # Check for if __name__ == "__main__": condition
      
        # Check for standalone code (no functions or classes)
        all_flags = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Call):
                return True
            elif not isinstance(node, (ast.Assign, ast.AugAssign, ast.Import, ast.ImportFrom, ast.Module, ast.FunctionDef, ast.ClassDef)):
                
                all_flags.append(has_entry_point(node))
        
        if len(all_flags): return any(all_flags)        
        
        return False
    except SyntaxError:
        return False
class ChatEnv:
    def __init__(self, chat_env_config: ChatEnvConfig):
        self.config = chat_env_config
        self.roster: Roster = Roster()
        self.codes: Codes = Codes()
        self.dependency_graph = None
        self.testing_file_map = {}
        self.proposed_images: Dict[str, str] = {}
        self.incorporated_images: Dict[str, str] = {}
        self.context_images: Dict[str, str] = {}
        self.requirements: Documents = Documents()
        self.manuals: Documents = Documents()
        self.tool_usage = {
            'FileSystem': 0,
            'Class': 0,
            'Testcase': 0,
            'Module': 0,
            'AttributeError': 0,
            'TypeError': 0,
            'other': 0,
            'graph': 0
        }
        self.env_dict = {
            "directory": "",
            "task_prompt": "",
            "modality": "",
            "ideas": "",
            "language": "",
            "review_comments": "",
            "error_summary": "",
            "test_reports": ""
        }
    
    def count_file_system_call(self):
        self.tool_usage['FileSystem'] += 1
    def count_class_call(self):
        self.tool_usage['Class'] += 1
    def count_test_case_call(self):
        self.tool_usage['Testcase'] += 1
    def count_module_call(self):
        self.tool_usage['Module'] += 1
    def count_attribute_error(self):
        self.tool_usage['AttributeError'] += 1
    def count_type_error(self):
        self.tool_usage['TypeError'] += 1
    def count_other_call(self):
        self.tool_usage['other'] += 1
    def count_graph_call(self):
        self.tool_usage['graph'] += 1
    @staticmethod
    def fix_module_not_found_error(test_reports):
        if "ModuleNotFoundError" in test_reports:
            for match in re.finditer(r"No module named '(\S+)'", test_reports, re.DOTALL):
                module = match.group(1)
                subprocess.Popen("pip install {}".format(module), shell=True).wait()
                log_and_print_online("**[CMD Execute]**\n\n[CMD] pip install {}".format(module))
                return module

    def set_directory(self, directory):
        assert len(self.env_dict['directory']) == 0
        self.env_dict['directory'] = directory
        self.codes.directory = directory
        self.requirements.directory = directory
        self.manuals.directory = directory

        if os.path.exists(self.env_dict['directory']) and len(os.listdir(directory)) > 0:
            new_directory = "{}.{}".format(directory, time.strftime("%Y%m%d%H%M%S", time.localtime()))
            shutil.copytree(directory, new_directory)
            # print("{} Copied to {}".format(directory, new_directory))
        if self.config.clear_structure:
            if os.path.exists(self.env_dict['directory']):
                shutil.rmtree(self.env_dict['directory'])
                os.mkdir(self.env_dict['directory'])
                # print("{} Created".format(directory))
            else:
                os.mkdir(self.env_dict['directory'])
        os.makedirs(os.path.join(self.env_dict['directory'], 'assets'), exist_ok = True)

    def exist_bugs(self, chat_env) -> Tuple[bool, str]:
        directory = self.env_dict['directory']
        # print('DIRECTORY:', directory)

        success_info = "The software run successfully without errors."
        try:

            # check if we are on windows or linux
            if os.name == 'nt':
                command = "cd {} && dir && python main.py".format(directory)
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                runnable_files = []
                is_python = False
                program_files = []
                for file, code in self.codes.codebooks.items():
                    # print('FILE:', file, code)
                    if not file.endswith('.py'): continue
                    is_python = True
                    if has_entry_point(code):
                        runnable_files.append(file)
                        if not (('test' in file) or ('test' in file)):
                            program_files.append(file)
                return_flag = False
                if 'testing_commands' not in self.env_dict:
                    chat_env.count_graph_call()
                    testing_commands = self.env_dict['commands']
                    _testing_commands = list(filter(lambda x: x.startswith('test') or x.split('.')[0].endswith('test'), get_test_order(chat_env.dependency_graph, chat_env.testing_file_map)))
                    additional_commands = list(set(testing_commands) - set(_testing_commands))
                    # print('additional_commands', additional_commands)
                    # additional_commands = list(filter(lambda x: x in runnable_files, additional_commands))
                    testing_commands = _testing_commands + additional_commands + program_files
                    if len(program_files) == 0:
                        testing_commands.append('no_entry_point')
                    # testing_commands = _testing_commands + additional_commands
                    # for file in program_files:
                    #     if file not in testing_commands:
                    #         testing_commands.append(file)
                    error_contents = ''
                    
                    # testing_commands.extend(runnable_files)
                    for file in runnable_files:
                        if file not in testing_commands:
                            testing_commands.append(file)
                    # testing_commands.extend(['-m unittest'])
                    
                    # testing_commands = list(set(testing_commands))
                else:
                    testing_commands = self.env_dict['testing_commands']
                    error_contents = ''
                current_idx = 0
                no_entry_point_error = False
                for testing_command in testing_commands:
                    if testing_command == 'no_entry_point' or testing_command not in runnable_files:
                        if testing_command.startswith('test') or testing_command.split('.')[0].endswith('test'):
                            errs = "[Error] the testing script lacks an entry point to start. Please modify accordingly to run test cases."
                        
                            error_contents += """\nError Traceback for Running File "{testing_command}":\n{errs}""".format(testing_command = testing_command, errs = errs)
                            return_flag = True
                            no_entry_point_error = True
                            break
                        elif testing_command != 'no_entry_point':
                            errs = "[Error] the software lacks an entry point to start. Please modify accordingly to make the program executable."
                            error_contents += """\nError Traceback for Running File "{testing_command}":\n{errs}""".format(testing_command = testing_command, errs = errs)
                            return_flag = True
                            no_entry_point_error = True
                            break
                        else:
                            errs = "[Error] the software lacks an entry point to start. Please modify accordingly to make the program executable."
                            error_contents += """There is a serious bug:\n{errs}""".format(testing_command = testing_command, errs = errs)
                            return_flag = True
                            no_entry_point_error = True
                            break
                    if 'main.py' in self.codes.codebooks and testing_command == 'main.py':
                        command = "cd {}; ls -l; python main.py;".format(directory)
                    else:
                        command = "cd {}; ls -l; python ".format(directory) + testing_command
                    # print('COMMAND:', command)
                    process = subprocess.Popen(command,
                                    shell=True,
                                    preexec_fn=os.setsid,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE
                                    )
                            # if len(process.stderr.read().decode('utf-8')) > 0: break
                        # if not flag:
                        #     return False, "Error: the software lacks the entry point to start"
                    time.sleep(3)
                    return_code = process.returncode
                    # Check if the software is still running
                    if process.poll() is None:
                        if "killpg" in dir(os):
                            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        else:
                            os.kill(process.pid, signal.SIGTERM)
                            if process.poll() is None:
                                os.kill(process.pid,signal.CTRL_BREAK_EVENT)

                    # if return_code == 0:
                    #     return False, success_info
                    # else:
                    #     error_output = process.stderr.read().decode('utf-8')
                    #     if error_output:
                    #         if "Traceback".lower() in error_output.lower():
                    #             errs = error_output.replace(directory + "/", "")
                    #             return True, errs
                            
                    #     else:
                    #         return False, success_info
                    error_output = process.stderr.read().decode('utf-8')
                    std_output = process.stdout.read().decode('utf-8')
                    # print('error_output', "Traceback".lower() in error_output.lower(), ':return_code:', return_code)
                    if return_code != 0:
                        if error_output:
                            if "Traceback".lower() in error_output.lower():
                                errs = error_output.replace(directory + "/", "")
                                # all_file_names = re.findall(r'File "(.*?)"', errs)
                                # if len(all_file_names) > len(set(all_file_names)):
                                #     errs = extract_first_error_traceback(errs)
                                if errs.count('--------------------------') > 1:
                                    new_errs = extract_first_error_traceback(errs)
                                    if len(new_errs):
                                        if len(new_errs.splitlines()) < 50:
                                            errs = new_errs
                                        else:
                                            errs = extract_first_error_traceback(errs, 1)
                                
                                # return True, errs
                                error_contents += """\nError Traceback for running File "{testing_command}":\n{errs}""".format(testing_command = testing_command, errs = errs)
                                return_flag = True
                        elif testing_command.startswith('test') or testing_command.split('.')[0].endswith('test'):
                            if 'FAILED' in std_output and '**************' not in std_output:
                                std_output = extract_top_k_errors(std_output, k = 1)
                                error_contents += """\nError Traceback for running File "{testing_command}":\n{std_output}""".format(testing_command = testing_command, std_output = std_output)
                                return_flag = True

                        elif 'failures' in std_output.lower() and 'failed' in std_output.lower():
                            error_contents += """\nError Traceback for running File "{testing_command}":\n{std_output}""".format(testing_command = testing_command, std_output = std_output)
                            return_flag = True

                            # else:
                            #     return False, success_info
                        # else:
                        #     return_flag = True
                        #     error_contents += """\nError Traceback for Running `{testing_command}`":\n{errs}""".format(testing_command = testing_command, errs = errs)
                    # print('return_flag:', return_flag)
                    current_idx += 1
                    if return_flag:
                        chat_env.env_dict['testing_commands'] = testing_commands[current_idx:]
                        return return_flag, error_contents
                if no_entry_point_error:
                    current_idx += 1
                    chat_env.env_dict['testing_commands'] = testing_commands[current_idx:]
                if return_flag:
                    return return_flag, error_contents
                else:
                    chat_env.env_dict['testing_commands'] = []
                    return False, success_info
        except subprocess.CalledProcessError as e:
            return True, f"Error: {e}"
        except Exception as ex:
            return True, f"An error occurred: {ex}"

        return False, success_info

    def exist_bugs_ignoring_test_cases(self, chat_env) -> Tuple[bool, str]:
        directory = self.env_dict['directory']
        # print('DIRECTORY:', directory)

        success_info = "The software run successfully without errors."
        try:

            # check if we are on windows or linux
            if os.name == 'nt':
                command = "cd {} && dir && python main.py".format(directory)
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                runnable_files = []
                is_python = False
                program_files = []
                for file, code in self.codes.codebooks.items():
                    # print('FILE:', file, code)
                    if not file.endswith('.py'): continue
                    is_python = True
                    if has_entry_point(code):
                        runnable_files.append(file)
                        if not (('test' in file) or ('test' in file)):
                            program_files.append(file)
                return_flag = False
                    
                testing_commands = self.env_dict['commands']
                _testing_commands = list(filter(lambda x: x.startswith('test') or x.split('.')[0].endswith('test'), get_test_order(chat_env.dependency_graph, chat_env.testing_file_map)))
                additional_commands = list(set(testing_commands) - set(_testing_commands))
                # print('additional_commands', additional_commands)
                # additional_commands = list(filter(lambda x: x in runnable_files, additional_commands))
                testing_commands = additional_commands + program_files
                error_contents = ''
                
                if len(program_files) == 0:
                    return True, "[Error] There is a serious bug since the software lacks an entry point to start. Please modify accordingly to make the program executable."
            
                for testing_command in testing_commands:
                    if testing_command not in runnable_files:
                        
                        errs = "[Error] the software lacks an entry point to start. Please modify accordingly to make the program executable."
                        error_contents += """\nError Traceback for Running File "{testing_command}":\n{errs}""".format(testing_command = testing_command, errs = errs)
                        return_flag = True
                        continue
                    if 'main.py' in self.codes.codebooks and testing_command == 'main.py':
                        command = "cd {}; ls -l; python main.py;".format(directory)
                    else:
                        command = "cd {}; ls -l; python ".format(directory) + testing_command
                    # print('COMMAND:', command)
                    process = subprocess.Popen(command,
                                    shell=True,
                                    preexec_fn=os.setsid,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE
                                    )
                            # if len(process.stderr.read().decode('utf-8')) > 0: break
                        # if not flag:
                        #     return False, "Error: the software lacks the entry point to start"
                    time.sleep(3)
                    return_code = process.returncode
                    # Check if the software is still running
                    if process.poll() is None:
                        if "killpg" in dir(os):
                            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        else:
                            os.kill(process.pid, signal.SIGTERM)
                            if process.poll() is None:
                                os.kill(process.pid,signal.CTRL_BREAK_EVENT)

                    # if return_code == 0:
                    #     return False, success_info
                    # else:
                    #     error_output = process.stderr.read().decode('utf-8')
                    #     if error_output:
                    #         if "Traceback".lower() in error_output.lower():
                    #             errs = error_output.replace(directory + "/", "")
                    #             return True, errs
                            
                    #     else:
                    #         return False, success_info
                    error_output = process.stderr.read().decode('utf-8')
                    # print('error_output', "Traceback".lower() in error_output.lower(), ':return_code:', return_code)
                    std_output = process.stdout.read().decode('utf-8')
                    if return_code != 0:
                        if error_output:
                            if "Traceback".lower() in error_output.lower():
                                errs = error_output.replace(directory + "/", "")
                                # all_file_names = re.findall(r'File "(.*?)"', errs)
                                # if len(all_file_names) > len(set(all_file_names)):
                                #     errs = extract_first_error_traceback(errs)
                                if errs.count('--------------------------') > 1:
                                    new_errs = extract_first_error_traceback(errs)
                                    if len(new_errs):
                                        if len(new_errs.splitlines()) < 50:
                                            errs = new_errs
                                        else:
                                            errs = extract_first_error_traceback(errs, 1)
                                
                                # return True, errs
                                error_contents += """\nError Traceback for running File "{testing_command}":\n{errs}""".format(testing_command = testing_command, errs = errs)
                                return_flag = True
                        elif testing_command.startswith('test') or testing_command.split('.')[0].endswith('test'):
                            if 'FAILED' in std_output and '**************' not in std_output:
                                std_output = extract_top_k_errors(std_output, k = 1)
                                error_contents += """\nError Traceback for running File "{testing_command}":\n{std_output}""".format(testing_command = testing_command, std_output = std_output)
                                return_flag = True

                        elif 'failures' in std_output.lower() and 'failed' in std_output.lower():
                            error_contents += """\nError Traceback for running File "{testing_command}":\n{std_output}""".format(testing_command = testing_command, std_output = std_output)
                            return_flag = True
                            # else:
                            #     return False, success_info
                        # else:
                        #     return_flag = True
                        #     error_contents += """\nError Traceback for Running `{testing_command}`":\n{errs}""".format(testing_command = testing_command, errs = errs)
                   
                    
                if return_flag:
                    return return_flag, error_contents
                else:
                    return False, success_info
        except subprocess.CalledProcessError as e:
            return True, f"Error: {e}"
        except Exception as ex:
            return True, f"An error occurred: {ex}"

        return False, success_info

    def recruit(self, agent_name: str):
        self.roster._recruit(agent_name)

    def exist_employee(self, agent_name: str) -> bool:
        return self.roster._exist_employee(agent_name)

    def print_employees(self):
        self.roster._print_employees()

    def update_codes(self, generated_content, is_testing = False, file_name = None):
       return self.codes._update_codes(generated_content, is_testing, file_name)

    def rewrite_codes(self) -> None:
        self.codes._rewrite_codes(self.config.git_management)
        self.dependency_graph = build_dependency_graph(self.env_dict['directory'])
        # print('self.dependency_graph', self.dependency_graph)
    def get_high_overlap_code(self):
        return self.codes._get_high_overlap_code()

    def get_codes(self, ignore_test_code = True, get_entry_point = False, simplify_code = False, only_test_code = False) -> str:
        return self.codes._get_codes(ignore_test_code, get_entry_point, simplify_code, only_test_code)

    def _load_from_hardware(self, directory) -> None:
        self.codes._load_from_hardware(directory)
    
    def get_total_changed_lines(self):
        if hasattr(self.codes, 'total_changed_lines'): return self.codes.total_changed_lines
    def get_changed_codes(self, changed_files, _simplify_code = False) -> str:
        return self.codes._get_changed_codes(changed_files, _simplify_code = _simplify_code)
    def get_changed_files(self):
        return self.codes._get_changed_files()
    def get_all_changed_files(self):
        return self.codes.all_changed_files
    def reset_all_changed_files(self):
        self.codes.all_changed_files = set()
    def _update_requirements(self, generated_content):
        self.requirements._update_docs(generated_content)

    def rewrite_requirements(self):
        self.requirements._rewrite_docs()

    def get_requirements(self) -> str:
        return self.requirements._get_docs()

    def _update_manuals(self, generated_content):
        self.manuals._update_docs(generated_content, parse=False, predifined_filename="manual.md")

    def rewrite_manuals(self):
        self.manuals._rewrite_docs()

    def write_meta(self) -> None:
        directory = self.env_dict['directory']

        if not os.path.exists(directory):
            os.mkdir(directory)
            print("{} Created.".format(directory))

        meta_filename = "meta.txt"
        with open(os.path.join(directory, meta_filename), "w", encoding="utf-8") as writer:
            writer.write("{}:\n{}\n\n".format("Task", self.env_dict['task_prompt']))
            writer.write("{}:\n{}\n\n".format("Config", self.config.__str__()))
            writer.write("{}:\n{}\n\n".format("Roster", ", ".join(self.roster.agents)))
            writer.write("{}:\n{}\n\n".format("Modality", self.env_dict['modality']))
            writer.write("{}:\n{}\n\n".format("Ideas", self.env_dict['ideas']))
            writer.write("{}:\n{}\n\n".format("Language", self.env_dict['language']))
            writer.write("{}:\n{}\n\n".format("Code_Version", self.codes.version))
            writer.write("{}:\n{}\n\n".format("Proposed_images", len(self.proposed_images.keys())))
            writer.write("{}:\n{}\n\n".format("Incorporated_images", len(self.incorporated_images.keys())))
        with open(os.path.join(directory, 'tool_usage.json'), "w") as f:
            json.dump(self.tool_usage, f)
        print(os.path.join(directory, meta_filename), "Wrote")

    def generate_images_from_codes(self):
        def download(img_url, file_name):
            r = requests.get(img_url)
            filepath = os.path.join(self.env_dict['directory'], "assets", file_name)
            if os.path.exists(filepath):
                os.remove(filepath)
            with open(filepath, "wb") as f:
                f.write(r.content)
                print("{} Downloaded".format(filepath))
        flag = False
        for regex in [r"(\w+.png)", r"(\w+.gif)"]:
            for _code in self.codes.codebooks.values():
                
                joined_codes = _code
                matches = re.finditer(regex, joined_codes, re.DOTALL)
                # matched_images = {}

                for match in matches:
                    filename = match.group(1).strip()
                    if filename in self.proposed_images.keys():
                        self.incorporated_images[filename] = self.proposed_images[filename]
                        flag = True 
                    else:
                        self.incorporated_images[filename] = filename.replace("_", " ")
                    self.context_images[filename] = _code
        
        for filename in self.incorporated_images.keys():
            if not os.path.exists(os.path.join(self.env_dict['directory'], "assets", filename)):
                desc = self.incorporated_images[filename]
                print("{}: {}".format(filename, desc))
                prompt = openai.ChatCompletion.create(engine = os.environ['API_ENGINE'], 
                                                        messages = [
                                                            {"role": "system", "content": "You are an experienced Art Prompt Engineer and working in the AgileCoder in the IT field. Your task is to write optimal prompts to feed to DALLE models to generate high-quality images needed for software."},
                                                            {"role": "user", "content": f"The user's task and our relevant code files are listed:\nTask: \"{self.env_dict['task_prompt']}\"\nCodes:\n\"{self.context_images[filename]}\".\nAs a Prompt Engineer, you write a prompt to generate the image \"{filename}\" and you also make sure that the generated image has a suitable size and highly aligns with the user's task and existing source code.\nThen just output the prompt with the format:\nPrompt: PROMPT where PROMPT is the possible prompt."}
                                                        ])['choices'][0]["message"]["content"]
                # log_and_print_online('*****************response', response)
                response = openai.Image.create(
                    prompt=prompt,
                    n=1,
                    size="256x256"
                )
                image_url = response['data'][0]['url']
                download(image_url, filename) 
                flag = True
        return flag

    def get_proposed_images_from_message(self, messages):
        def download(img_url, file_name):
            r = requests.get(img_url)
            filepath = os.path.join(self.env_dict['directory'], "assets", file_name)
            if os.path.exists(filepath):
                os.remove(filepath)
            with open(filepath, "wb") as f:
                f.write(r.content)
                print("{} Downloaded".format(filepath))
        images = {}
        for regex in [r"(\w+.png):(.*?)\n", r"(\w+.gif):(.*?)\n"]:
            matches = re.finditer(regex, messages, re.DOTALL)

            for match in matches:
                filename = match.group(1).strip()
                desc = match.group(2).strip()
                images[filename] = desc

        if len(images.keys()) == 0:
            for regex in [r"(\w+.png):(.*?)\n", r"(\w+.gif):(.*?)\n"]:
                matches = re.finditer(regex, messages, re.DOTALL)
                for match in matches:
                    filename = match.group(1).strip()
                    desc = " ".join(filename.split('.')[0].split("_"))
                    images[filename] = desc
                    print("{}: {}".format(filename, images[filename]))

        for filename in images.keys():
            if not os.path.exists(os.path.join(self.env_dict['directory'], filename)):
                # desc = images[filename]
                # if desc.endswith(".png"):
                #     desc = desc.replace(".png", "")
               
                prompt = openai.ChatCompletion.create(engine = os.environ['API_ENGINE'], 
                                                        messages = [
                                                            {"role": "system", "content": "You are an experienced Prompt Engineer and working in a AgileCoder in the IT field. Your task is to write optimal prompts to feed to DALLE models to generate high-quality images needed for software."},
                                                            {"role": "user", "content": f"The user's task and our relevant code files are listed:\nTask: \"{self.env_dict['task_prompt']}\"\nCodes:\n\"{self.context_images[filename]}\".\nAs a Prompt Engineer, you write a prompt to generate the image \"{filename}\" and you also make sure that the generated image has a suitable size and highly aligns with the user's task and existing source code.\nThen just output the prompt with the format:\nPrompt: PROMPT where PROMPT is the possible prompt."}
                                                        ])['choices'][0]["message"]["content"]
                # log_and_print_online('*****************response', response)
                # log_and_print_online('*****************response', response)
                print("{}: {}".format(filename, prompt))
                response = openai.Image.create(
                    prompt=prompt,
                    n=1,
                    size="256x256"
                )
                image_url = response['data'][0]['url']
                download(image_url, filename)

        return images

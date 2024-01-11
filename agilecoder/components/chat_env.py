import os
import re
import shutil
import signal
import glob
import subprocess
import time
from typing import Dict

import openai
import requests

from agilecoder.components.codes import Codes
from agilecoder.components.documents import Documents
from agilecoder.components.roster import Roster
from agilecoder.components.utils import log_and_print_online


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


class ChatEnv:
    def __init__(self, chat_env_config: ChatEnvConfig):
        self.config = chat_env_config
        self.roster: Roster = Roster()
        self.codes: Codes = Codes()
        self.proposed_images: Dict[str, str] = {}
        self.incorporated_images: Dict[str, str] = {}
        self.requirements: Documents = Documents()
        self.manuals: Documents = Documents()
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
            print("{} Copied to {}".format(directory, new_directory))
        if self.config.clear_structure:
            if os.path.exists(self.env_dict['directory']):
                shutil.rmtree(self.env_dict['directory'])
                os.mkdir(self.env_dict['directory'])
                print("{} Created".format(directory))
            else:
                os.mkdir(self.env_dict['directory'])
        os.makedirs(os.path.join(self.env_dict['directory'], 'assets'), exist_ok = True)

    def exist_bugs(self) -> tuple[bool, str]:
        directory = self.env_dict['directory']

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
                all_files = os.listdir(directory)
                if 'main.py' in all_files:
                    command = "cd {}; ls -l; python3 main.py;".format(directory)
                    process = subprocess.Popen(command,
                                        shell=True,
                                        preexec_fn=os.setsid,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE
                                        )
                else:
                    for file in all_files:
                        if not file.endswith('.py'): continue
                        command = "cd {}; ls -l; python3 ".format(directory) + file
                        process = subprocess.Popen(command,
                                        shell=True,
                                        preexec_fn=os.setsid,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE
                                        )
                        if len(process.stderr.read().decode('utf-8')) > 0: break
                
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

            if return_code == 0:
                return False, success_info
            else:
                error_output = process.stderr.read().decode('utf-8')
                if error_output:
                    if "Traceback".lower() in error_output.lower():
                        errs = error_output.replace(directory + "/", "")
                        return True, errs
                    
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

    def update_codes(self, generated_content):
        self.codes._update_codes(generated_content)

    def rewrite_codes(self) -> None:
        self.codes._rewrite_codes(self.config.git_management)

    def get_codes(self) -> str:
        return self.codes._get_codes()

    def _load_from_hardware(self, directory) -> None:
        self.codes._load_from_hardware(directory)

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
            joined_codes = self.get_codes()
            matches = re.finditer(regex, joined_codes, re.DOTALL)
            # matched_images = {}

            for match in matches:
                filename = match.group(1).strip()
                if filename in self.proposed_images.keys():
                    self.incorporated_images[filename] = self.proposed_images[filename]
                    flag = True 
                else:
                    self.incorporated_images[filename] = filename.replace("_", " ")
        
        for filename in self.incorporated_images.keys():
            if not os.path.exists(os.path.join(self.env_dict['directory'], "assets", filename)):
                desc = self.incorporated_images[filename]
                print("{}: {}".format(filename, desc))
                prompt = openai.ChatCompletion.create(engine = os.environ['API_ENGINE'], 
                                                        messages = [
                                                            {"role": "system", "content": "You are an experienced Art Prompt Engineer and working in the AgileCoder in the IT field. Your task is to write optimal prompts to feed to DALLE models to generate high-quality images needed for software."},
                                                            {"role": "user", "content": f"The user's task and our relevant code files are listed:\nTask: \"{self.env_dict['task_prompt']}\"\nCodes:\n\"{self.codes}\".\nAs a Prompt Engineer, you write a prompt to generate the image \"{filename}\" and you also make sure that the generated image has a suitable size and highly aligns with the user's task and existing source code.\nThen just output the prompt with the format:\nPrompt: PROMPT where PROMPT is the possible prompt."}
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
                                                            {"role": "user", "content": f"The user's task and our relevant code files are listed:\nTask: \"{self.env_dict['task_prompt']}\"\nCodes:\n\"{self.codes}\".\nAs a Prompt Engineer, you write a prompt to generate the image \"{filename}\" and you also make sure that the generated image has a suitable size and highly aligns with the user's task and existing source code.\nThen just output the prompt with the format:\nPrompt: PROMPT where PROMPT is the possible prompt."}
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

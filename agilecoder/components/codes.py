import os
import re
# from strsimpy.normalized_levenshtein import NormalizedLevenshtein
from nltk.translate.bleu_score import sentence_bleu
from codebleu import calc_codebleu
from agilecoder.components.utils import log_and_print_online
import difflib
import ast
def is_valid_syntax(code):
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False
    
def check_the_same_file(name1, name2):
    name1 = name1.split('.')[0].replace('_', '')
    name2 = name2.split('.')[0].replace('_', '')
    return name2 in name1
def extract_files(code_string):
    """Extracts code and names for each file from the given string."""

    files = {}
    current_file = None
    current_code = ""
    flag = False
    flag1 = False
    for line in code_string.splitlines():
    # Check for file header lines
        if line.startswith('FILENAME:'):
            if current_file:
                files[current_file] = current_code
            current_file = line.split()[1].strip()
            current_code = ""
            flag1 = True
        elif line.startswith('DOCSTRING') or line.startswith('CODE'): continue
        elif line.startswith('```'): 
            if flag:
                flag1 = False
            flag = not flag
            # continue
        elif not line.startswith('LANGUAGE'):
            if flag1:
                current_code += line + "\n"

  # Add the last file
    if current_file and not flag:
        files[current_file] = current_code

    return files

def extract_class_names(source_code):
    pattern = r'class\s+([A-Za-z_]\w*)'
    class_names = re.findall(pattern, source_code)
    return class_names

def simplify_code(code):
    codelines = code.splitlines()
    outputs = []
    flag = False
    for line in codelines:
        if line.strip().startswith('def'):
            flag = True
            is_docstring = 0

        if flag and line.strip() in ['"""', "'''"]:
            is_docstring += 1
                # if not is_docstring:
                #     flag = False
        if flag and is_docstring == 2: 
            outputs.append(line)
            is_docstring += 1
        if flag and is_docstring > 2: continue
        outputs.append(line)
    return '\n'.join(outputs)
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

class Codes:
    def __init__(self, generated_content="", is_testing = False):
        self.directory: str = None
        self.version: float = 1.0
        self.generated_content: str = generated_content
        self.codebooks = {}
        self.testing_filenames = set()
        self.is_testing = is_testing
        self.all_changed_files = set()
        def extract_filename_from_line(lines):
            file_name = ""
            for candidate in re.finditer(r"(\w+\.\w+)", lines, re.DOTALL):
                file_name = candidate.group()
                file_name = file_name#.lower()
            return file_name

        def extract_filename_from_code(code):
            file_name = ""
            regex_extract = r"class (\S+?):\n"
            matches_extract = re.finditer(regex_extract, code, re.DOTALL)
            count = 0
            for match_extract in matches_extract:
                file_name = match_extract.group(1)
                count += 1
            if count > 1:
                return None
            file_name = file_name.lower().split("(")[0] + ".py"
            return file_name

        if generated_content != "":
            regex = r"FILENAME\n```.*?\n(.*?)```"
            matches = re.finditer(regex, self.generated_content, re.DOTALL)
            unmatched_codes = []
            flag = False
            # normalized_levenshtein = NormalizedLevenshtein()
            # for match in matches:
            #     flag = True
            #     code = match.group(1)
            #     if "CODE" in code:
            #         continue
            #     if not self.is_testing and ("__main__" in code or 'main.py' in code):
            #         # filename = "main.py"
            #         filename = None
            #     else:
            #         filename = extract_filename_from_code(code)
            #     if filename is not None and filename != '.py' and code is not None and len(filename) > 0 and len(code) > 0:
            #         self.codebooks[filename] = self._format_code(code)
            #     else:
            #         unmatched_codes.append(self._format_code(code))
            for match in matches:
                flag = True
                code = match.group(1)
                if "CODE" in code:
                    continue
                # if not self.is_testing and ("__main__" in code or 'main.py' in code):
                #     # filename = "main.py"
                #     filename = None
                # else:
                #     filename = extract_filename_from_code(code)
                # if filename is not None and filename != '.py' and code is not None and len(filename) > 0 and len(code) > 0:
                #     self.codebooks[filename] = self._format_code(code)
                # else:
                #     unmatched_codes.append(self._format_code(code))
                formatted_code = self._format_code(code)
                scores = []
                for filename, file_code in self.codebooks.items():
                    if filename.endswith('.py'):
                        _score = max(sentence_bleu([formatted_code.split()], file_code.split()), calc_codebleu([formatted_code], [file_code], lang = 'python')['codebleu'])
                        scores.append((filename, formatted_code, _score))
                    else:
                        scores.append((filename, formatted_code, sentence_bleu([formatted_code.split()], file_code.split())))
                has_duplicated = False
                if len(scores) > 0:
                    scores = sorted(scores, key = lambda x: x[2], reverse = True)[0]
                    if scores[2] > 0.6:
                        self.codebooks[scores[0]] = scores[1]
                        has_duplicated = True
                if not has_duplicated:
                    filename = extract_filename_from_code(code)
                    for _filename in self.codebooks:
                        if _filename.lower().replace('_', '')  == filename:
                            filename = _filename
                            break
                    if filename is not None and filename != '.py' and formatted_code is not None and len(filename) > 0 and len(formatted_code) > 0:
                        self.codebooks[filename] = formatted_code
            # normalized_levenshtein = NormalizedLevenshtein()
            # for code in unmatched_codes:
            #     scores = []
            #     for filename, file_code in self.codebooks.items():
            #         scores.append((filename, code, normalized_levenshtein.similarity(code, file_code)))
            #     if len(scores) > 0:
            #         scores = sorted(scores, key = lambda x: x[2], reverse = True)[0]
            #         if scores[2] > 0.7:
            #             self.codebooks[scores[0]] = scores[1]
            
            if not flag:
                regex = r"FILENAME: ([a-z_0-9]+\.\w+)\n```.*?\n(.*?)```"
                matches = re.finditer(regex, self.generated_content, re.DOTALL)
                
                for match in matches:
                    flag = True
                    filename = match.group(1)
                    code = match.group(2)
                    if "CODE" in code:
                        continue
                    if filename is not None and code is not None and len(filename) > 0 and len(code) > 0:
                        if filename.endswith('.py'):
                            if is_valid_syntax(code):
                                self.codebooks[filename] = self._format_code(code)
                        else:
                            self.codebooks[filename] = self._format_code(code)
                    
            if not flag:
                regex = r"(.+?\.\w+)\n```\w+\n(.*?)```"
                matches = re.finditer(regex, self.generated_content, re.DOTALL)
                flag = False
                for match in matches:
                    code = match.group(2)
                    if "CODE" in code:
                        continue
                    flag = True
                    group1 = match.group(1)
                    filename = extract_filename_from_line(group1)
                    old_filename = None
                    if not self.is_testing and ("__main__" in code or 'main.py' in code):
                        # new_filename = "main.py"
                        # if new_filename != filename:
                        #     old_filename = filename
                        #     filename = new_filename
                        pass
                    if filename == "":  # post-processing
                        filename = extract_filename_from_code(code)
                    # assert filename != ""
                    if filename == '.py':
                        scores = []
                        # normalized_levenshtein = NormalizedLevenshtein()
                        formatted_code = self._format_code(code)
                        for _filename, file_code in self.codebooks.items():
                            if _filename.endswith('.py'):
                                _score = max(sentence_bleu([formatted_code.split()], file_code.split()), calc_codebleu([formatted_code], [file_code], lang = 'python')['codebleu'])
                                scores.append((_filename, formatted_code, _score))
                            else:
                                scores.append((_filename, formatted_code, sentence_bleu([formatted_code.split()], file_code.split())))
                        if len(scores) > 0:
                            scores = sorted(scores, key = lambda x: x[2], reverse = True)[0]
                            if scores[2] > 0.6:
                                self.codebooks[scores[0]] = scores[1]
                    elif filename is not None and code is not None and len(filename) > 0 and len(code) > 0:
                        if filename.endswith('.py'):
                            if is_valid_syntax(code):
                                self.codebooks[filename] = self._format_code(code)
                                if old_filename is not None and old_filename in self.codebooks:
                                    self.codebooks.pop(old_filename)
                        else:
                            self.codebooks[filename] = self._format_code(code)

            if not flag:
                try:
                    file_codes = extract_files(self.generated_content)
                    for filename, filecode in file_codes.items():
                        if filename.endswith('.py'):
                            if is_valid_syntax(filecode):
                                flag = True
                                self.codebooks[filename] = self._format_code(filecode)
                        else:
                            flag = True
                            self.codebooks[filename] = self._format_code(filecode)
                except: pass
            
            self.has_correct_format = flag
                
    def _format_code(self, code):
        code = "\n".join([line for line in code.split("\n") if len(line.strip()) > 0])
        return code
    
    def _get_high_overlap_code(self):
        filename_pairs = set()
        results = {}
        for filename, filecode in self.codebooks.items():
            for filename1, filecode1 in self.codebooks.items():
                if filename == filename1: continue
                p = filename, filename1
                p1 = filename1, filename
                if p not in filename_pairs and p1 not in filename_pairs:
                    filename_pairs.add(p)
                else: continue
                if filename.endswith('.py'):
                    s = max(calc_codebleu([filecode], [filecode1], lang = 'python')['codebleu'], sentence_bleu([filecode.split()], filecode1.split()))
                else:
                    s = sentence_bleu([filecode.split()], filecode1.split())
                if s > 0.6:
                    results[p] = s
        return results
                

    def _update_codes(self, generated_content, is_testing, file_name):
        new_codes = Codes(generated_content, is_testing)
        # differ = difflib.Differ()
        flag = False
        total_new_length = 0
        total_changed_lines = ''
        changed_files = []
        total_generated_line_num = len(list(filter(lambda x: len(x.strip()), generated_content.splitlines())))
        for key in new_codes.codebooks.keys():
            if is_testing and key == file_name: continue
            if file_name is not None and not check_the_same_file(key, file_name):  continue

            total_new_length += len(new_codes.codebooks[key].splitlines())
            corres_key = None
            if key not in self.codebooks.keys():
                scores = []
                for filename, file_code in self.codebooks.items():
                    if filename.endswith('.py'):
                        _score = max(sentence_bleu([new_codes.codebooks[key].split()], file_code.split()), calc_codebleu([new_codes.codebooks[key]], [file_code], lang = 'python')['codebleu'])
                        scores.append((filename, _score))
                    else:
                        scores.append((filename, sentence_bleu([new_codes.codebooks[key].split()], file_code.split())))
                if len(scores):
                    scores = sorted(scores, key = lambda x: x[1], reverse = True)[0]
                    if scores[1] > 0.6:
                        corres_key = scores[0]
                if corres_key is None:
                    for filename in self.codebooks:
                        if filename.lower().replace('_', '') ==  key:
                            corres_key = filename
            if key not in self.codebooks.keys() or self.codebooks[key] != new_codes.codebooks[key]:
                if is_testing:
                    self.testing_filenames.update([key])

                update_codes_content = "**[Update Codes]**\n\n"
                update_codes_content += "{} updated.\n".format(key)
                total_changed_lines +=  "File: {} updated.\n".format(key)
                old_codes_content = self.codebooks[key] if key in self.codebooks.keys() else "# None"
                new_codes_content = new_codes.codebooks[key]

                lines_old = old_codes_content.splitlines()
                lines_new = new_codes_content.splitlines()

                unified_diff = difflib.unified_diff(lines_old, lines_new, lineterm='', fromfile='Old', tofile='New')
                unified_diff = '\n'.join(unified_diff)
                update_codes_content = update_codes_content + "\n\n" + """```
'''

'''\n""" + unified_diff + "\n```"
                total_changed_lines +=  "```\n" + unified_diff + "\n```\n"

                log_and_print_online(update_codes_content)
                log_and_print_online('FILE==' + str(corres_key) + '--OLD==' + key)
                self.codebooks[corres_key or key] = new_codes.codebooks[key]
                changed_files.append(corres_key or key)

            flag = True
        log_and_print_online('AFTERCODE==:' + str(self.codebooks.keys()))
        self.total_changed_lines = total_changed_lines
        self.changed_files = changed_files
        self.all_changed_files.update(self.changed_files)

        # print('changed_files', changed_files)
        return flag and (total_new_length / total_generated_line_num > 0.5)
        # return hasattr(new_codes, 'has_correct_format') and new_codes.has_correct_format

    def _get_changed_files(self):
        if hasattr(self, 'changed_files'): return self.changed_files
        return []
    def _rewrite_codes(self, git_management) -> None:
        directory = self.directory
        rewrite_codes_content = "**[Rewrite Codes]**\n\n"
        if os.path.exists(directory) and len(os.listdir(directory)) > 0:
            self.version += 1.0
        if not os.path.exists(directory):
            os.mkdir(self.directory)
            rewrite_codes_content += "{} Created\n".format(directory)


        for filename in self.codebooks.keys():
            if self.codebooks[filename].endswith('.py') and 'flask' in self.codebooks[filename]:
                os.makedirs(os.path.join(directory, 'templates'), exist_ok = True)
            if filename.endswith('.html'):
                filepath = os.path.join(directory, 'templates', os.path.basename(filename))
            else:
                filepath = os.path.join(directory, os.path.basename(filename))
            with open(filepath, "w", encoding="utf-8") as writer:
                writer.write(self.codebooks[filename])
                rewrite_codes_content += os.path.join(directory, filename) + " Wrote\n"

        if git_management:
            if self.version == 1.0:
                os.system("cd {}; git init".format(self.directory))
            os.system("cd {}; git add .".format(self.directory))
            os.system("cd {}; git commit -m \"{}\"".format(self.directory, self.version))

        log_and_print_online(rewrite_codes_content)

    def _get_codes(self, ignore_test_code, get_entry_point = False, _simplify_code = False, only_test_code = False) -> str:
        content = ""
        # print('self.testing_filenames', self.testing_filenames)
        for filename in self.codebooks.keys():
            if get_entry_point:
                if has_entry_point(self.codebooks[filename]):
                    if ignore_test_code and (filename.startswith('test') or filename.split('.')[0].endswith('test')): continue
                    code = self.codebooks[filename]
                    if _simplify_code:
                        code = simplify_code(code)
                    content += "{}\n```{}\n{}\n```\n\n".format(filename,
                                                            "python" if filename.endswith(".py") else filename.split(".")[
                                                                -1], code)
                continue
            if only_test_code and not (filename.startswith('test') or filename.split('.')[0].endswith('test')): continue
            elif ignore_test_code and (filename.startswith('test') or filename.split('.')[0].endswith('test')): continue
            code = self.codebooks[filename]
            if _simplify_code:
                code = simplify_code(code)
            content += "{}\n```{}\n{}\n```\n\n".format(filename,
                                                       "python" if filename.endswith(".py") else filename.split(".")[
                                                           -1], code)
        return content

    def _get_changed_codes(self, changed_files, _simplify_code = False) -> str:
        content = ""
        for filename in self.codebooks.keys():
            if filename not in changed_files: continue
            code = self.codebooks[filename]
            if _simplify_code:
                code = simplify_code(code)
            content += "{}\n```{}\n{}\n```\n\n".format(filename,
                                                       "python" if filename.endswith(".py") else filename.split(".")[
                                                           -1], code)
        return content

    def _load_from_hardware(self, directory) -> None:
        assert len([filename for filename in os.listdir(directory) if filename.endswith(".py")]) > 0
        for root, directories, filenames in os.walk(directory):
            for filename in filenames:
                if filename.endswith(".py"):
                    code = open(os.path.join(directory, filename), "r", encoding="utf-8").read()
                    self.codebooks[filename] = self._format_code(code)
        log_and_print_online("{} files read from {}".format(len(self.codebooks.keys()), directory))

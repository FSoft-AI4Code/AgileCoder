import os
import re

from strsimpy.normalized_levenshtein import NormalizedLevenshtein
import difflib
def is_valid_syntax(code):
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False
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
class Codes:
    def __init__(self, generated_content=""):
        self.directory: str = None
        self.version: float = 1.0
        self.generated_content: str = generated_content
        self.codebooks = {}

        def extract_filename_from_line(lines):
            file_name = ""
            for candidate in re.finditer(r"(\w+\.\w+)", lines, re.DOTALL):
                file_name = candidate.group()
                file_name = file_name.lower()
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
            for match in matches:
                print('dakjdsaghsdjkas')
                flag = True
                code = match.group(1)
                if "CODE" in code:
                    continue
                if "__main__" in code:
                    filename = "main.py"
                else:
                    filename = extract_filename_from_code(code)
                if filename is not None and code is not None and len(filename) > 0 and len(code) > 0:
                    self.codebooks[filename] = self._format_code(code)
                else:
                    unmatched_codes.append(self._format_code(code))
            normalized_levenshtein = NormalizedLevenshtein()
            for code in unmatched_codes:
                scores = []
                for filename, file_code in self.codebooks.items():
                    scores.append((filename, code, normalized_levenshtein.similarity(code, file_code)))
                if len(scores) > 0:
                    scores = sorted(scores, key = lambda x: x[2], reverse = True)[0]
                    if scores[2] > 0.7:
                        self.codebooks[scores[0]] = scores[1]
           
            
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
                regex = r"(.+?\.\w+)\n```.*?\n(.*?)```"
                matches = re.finditer(regex, self.generated_content, re.DOTALL)
                for match in matches:
                    print('1111')
                    code = match.group(2)
                    if "CODE" in code:
                        continue
                    flag = True
                    group1 = match.group(1)
                    print(group1)
                    print('code', code, '122')
                    filename = extract_filename_from_line(group1)
                    old_filename = None
                    if "__main__" in code or 'main.py' in code:
                        new_filename = "main.py"
                        if new_filename != filename:
                            old_filename = filename
                            filename = new_filename
                    if filename == "":  # post-processing
                        filename = extract_filename_from_code(code)
                    # assert filename != ""
                    if filename == '.py':
                        scores = []
                        normalized_levenshtein = NormalizedLevenshtein()
                        formatted_code = self._format_code(code)
                        for _filename, file_code in self.codebooks.items():
                            scores.append((_filename, formatted_code, normalized_levenshtein.similarity(formatted_code, file_code)))
                        if len(scores) > 0:
                            scores = sorted(scores, key = lambda x: x[2], reverse = True)[0]
                            if scores[2] > 0.7:
                                self.codebooks[scores[0]] = scores[1]
                    elif filename is not None and code is not None and len(filename) > 0 and len(code) > 0:
                        if filename.endswith('.py'):
                            if is_valid_syntax(code):
                                self.codebooks[filename] = self._format_code(code)
                                if old_filename is not None and old_filename in self.codebooks:
                                    self.codebooks.pop(old_filename)
                        else:
                            self.codebooks[filename] = self._format_code(code)
                # regex = r"FILENAME\n```.*?\n(.*?)```"
                # matches = re.finditer(regex, self.generated_content, re.DOTALL)
                # unmatched_codes = []
                # for match in matches:
                #     print('dakjdsaghsdjkas')
                #     flag = True
                #     code = match.group(1)
                #     if "CODE" in code:
                #         continue
                #     if "__main__" in code:
                #         filename = "main.py"
                #     else:
                #         filename = extract_filename_from_code(code)
                #     if filename is not None and code is not None and len(filename) > 0 and len(code) > 0:
                #         self.codebooks[filename] = self._format_code(code)
                #     else:
                #         unmatched_codes.append(self._format_code(code))
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
                file_codes = extract_files(self.generated_content)
                for filename, filecode in file_codes.items():
                    if filename.endswith('.py'):
                        if is_valid_syntax(filecode):
                            flag = True
                            self.codebooks[filename] = self._format_code(filecode)
                    else:
                        flag = True
                        self.codebooks[filename] = self._format_code(filecode)
            self.has_correct_format = flag
                


    def _format_code(self, code):
        code = "\n".join([line for line in code.split("\n") if len(line.strip()) > 0])
        return code

    def _update_codes(self, generated_content):
        new_codes = Codes(generated_content)
        # print('new_codes.codebooks', new_codes.codebooks)
        differ = difflib.Differ()
        for key in new_codes.codebooks.keys():
            if key not in self.codebooks.keys() or self.codebooks[key] != new_codes.codebooks[key]:
                update_codes_content = "**[Update Codes]**\n\n"
                update_codes_content += "{} updated.\n".format(key)
                old_codes_content = self.codebooks[key] if key in self.codebooks.keys() else "# None"
                new_codes_content = new_codes.codebooks[key]

                lines_old = old_codes_content.splitlines()
                lines_new = new_codes_content.splitlines()

                unified_diff = difflib.unified_diff(lines_old, lines_new, lineterm='', fromfile='Old', tofile='New')
                unified_diff = '\n'.join(unified_diff)
                update_codes_content = update_codes_content + "\n\n" + """```
'''

'''\n""" + unified_diff + "\n```"

                self.codebooks[key] = new_codes.codebooks[key]
        # print('self.codebooks', self.codebooks)

    def _rewrite_codes(self, git_management) -> None:
        directory = self.directory
        rewrite_codes_content = "**[Rewrite Codes]**\n\n"
        if os.path.exists(directory) and len(os.listdir(directory)) > 0:
            self.version += 1.0
        if not os.path.exists(directory):
            os.mkdir(self.directory)
            rewrite_codes_content += "{} Created\n".format(directory)

        for filename in self.codebooks.keys():
            filepath = os.path.join(directory, filename)
            with open(filepath, "w", encoding="utf-8") as writer:
                writer.write(self.codebooks[filename])
                rewrite_codes_content += os.path.join(directory, filename) + " Wrote\n"

        if git_management:
            if self.version == 1.0:
                os.system("cd {}; git init".format(self.directory))
            os.system("cd {}; git add .".format(self.directory))
            os.system("cd {}; git commit -m \"{}\"".format(self.directory, self.version))


    def _get_codes(self) -> str:
        content = ""
        for filename in self.codebooks.keys():
            content += "{}\n```{}\n{}\n```\n\n".format(filename,
                                                       "python" if filename.endswith(".py") else filename.split(".")[
                                                           -1], self.codebooks[filename])
        return content

    def _load_from_hardware(self, directory) -> None:
        assert len([filename for filename in os.listdir(directory) if filename.endswith(".py")]) > 0
        for root, directories, filenames in os.walk(directory):
            for filename in filenames:
                if filename.endswith(".py"):
                    code = open(os.path.join(directory, filename), "r", encoding="utf-8").read()
                    self.codebooks[filename] = self._format_code(code)

s = """
main.py
```python
'''
This file contains the StartScreen class, which represents the start screen of the game.
'''
from startscreen import StartScreen
if __name__ == "__main__":
    screen = StartScreen(800, 600, 30, (255, 255, 255))
    screen.draw()
```

game.py
```python
'''
This class will manage the game state and logic. It will be responsible for initializing the game objects, generating food, updating the game state, and drawing the game on the GUI.
'''
class Game:
    def __init__(self):
        pass
```

gui.py
```python
'''
This file contains the GUI class and its methods.
'''
import pygame
class GUI:
    '''
    Manages the graphical user interface for the game.
    '''
    def __init__(self, game_window, game):
        '''
        Initializes the GUI with the given game window and game.
        '''
        self.game_window = game_window
        self.game = game
        self.font = pygame.font.SysFont("Arial", 24)
    def draw(self):
        '''
        Draws the game on the GUI.
        '''
        # Clear the screen
        self.game_window.fill((0, 0, 0))
        # Draw the snake
        for rect in self.game.snake.body:
            pygame.draw.rect(self.game_window, self.game.snake.color, rect)
        # Draw the food
        self.game.food.draw(self.game_window)
        # Draw the score
        score_text = self.font.render("Score: " + str(self.game.score), True, (255, 255, 255))
        self.game_window.blit(score_text, (10, 10))
```

snake.py
```python
'''
This class will represent the snake in the game and will be responsible for its movement, growth, collision detection, and self-collision detection.
'''
class Snake:
    def __init__(self):
        pass
```

gameboard.py
```python
'''
This class will represent the game board and will be responsible for drawing the game board on the GUI.
'''
class GameBoard:
    def __init__(self):
        pass
```

food.py
```python
'''
This class will represent the food in the game and will be responsible for generating new food objects at random locations on the game board.
'''
class Food:
    def __init__(self):
        pass
```

scoreboard.py
```python
'''
This class will represent the scoreboard in the game and will be responsible for keeping track of the player
'''
class Scoreboard:
    def __init__(self):
        pass
```

startscreen.py
```python
'''
This class will represent the start screen of the game and will be responsible for displaying the game's title and instructions to the user.
'''
class StartScreen:
    def __init__(self):
        pass
```

gameoverscreen.py
```python
'''
This file contains the game over screen class and its methods.
'''
import pygame
class GameOverScreen:
    '''
    Represents the game over screen in the game.
    '''
    def __init__(self, width, height, font_size, color):
        '''
        Initializes the game over screen with the given width, height, font size, and color.
        '''
        self.width = width
        self.height = height
        self.font = pygame.font.SysFont("Arial", font_size)
        self.color = color
    def draw(self, surface, score):
        '''
        Draws the game over screen on the given surface.
        '''
        # Draw the background
        background = pygame.Surface((self.width, self.height))
        background.set_alpha(128)
        background.fill((0, 0, 0))
        surface.blit(background, (0, 0))
        # Draw the text
        text1 = self.font.render("Game Over", True, self.color)
        text1_rect = text1.get_rect(center=(self.width // 2, self.height // 2 - 20))
        surface.blit(text1, text1_rect)
        text2 = self.font.render("Score: " + str(score), True, self.color)
        text2_rect = text2.get_rect(center=(self.width // 2, self.height // 2 + 20))
        surface.blit(text2, text2_rect)
```


startscreen.py
```python
'''
This class will represent the start screen of the game and will be responsible for displaying the game's title and instructions to the user.
'''
import pygame

class StartScreen:
    def __init__(self, width, height, font_size, color):
        self.width = width
        self.height = height
        self.font = pygame.font.SysFont("Arial", font_size)
        self.color = color

    def draw(self, surface):
        # Draw the background
        surface.fill(self.color)
        # Draw the text
        text = self.font.render("Snake Game", True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.width // 2, self.height // 2 - 20))
        surface.blit(text, text_rect)
        text = self.font.render("Press any key to start", True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.width // 2, self.height // 2 + 20))
        surface.blit(text, text_rect)
```

gameoverscreen.py
```python
'''
This file contains the game over screen class and its methods.
'''
import pygame

class GameOverScreen:
    '''
    Represents the game over screen


"""

import ast

def is_valid_syntax(code):
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False
code = """

main.py

"""
print(is_valid_syntax(code))
code = Codes()
# code._update_codes(s)
# print(code.)

import subprocess

class TerminalRun():
    def __init__(self) -> None:
        self.hi = 1
    def show(self, text):
        print(text)
        print(self.hi)
    def run(self, text):
        new = text.split(' ')
        print(new)
        subprocess.run(new)
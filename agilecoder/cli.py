import argparse
import os
from agilecoder.run_api import run_task
def main():
    try:
        import tree_sitter_python
    except Exception as e:
        print('Please run the following command to fix this error: pip install git+https://github.com/tree-sitter/tree-sitter-python.git@master')
        raise e
    parser = argparse.ArgumentParser(description='argparse')
    parser.add_argument('--config', type=str, default="Agile",
                        help="Name of config, which is used to load configuration under CompanyConfig/")
    parser.add_argument('--org', type=str, default="DefaultOrganization",
                        help="Name of organization, your software will be generated in WareHouse/name_org_timestamp")
    parser.add_argument('--task', type=str, default="Develop a basic Gomoku game.",
                        help="Prompt of software")
    parser.add_argument('--name', type=str, default="Gomoku",
                        help="Name of software, your software will be generated in WareHouse/name_org_timestamp")
    parser.add_argument('--max-num-sprints', type=int, default=10)
    parser.add_argument('--model', type=str, default="GPT_3_5_AZURE",
                        help="GPT Model, choose from {'GPT_3_5_TURBO','GPT_4','GPT_4_32K', 'GPT_3_5_AZURE', 'CLAUDE', 'ANTHROPIC_CLAUDE'}")
    args = parser.parse_args()
    print('------------------------------')
    run_task(args)                                           
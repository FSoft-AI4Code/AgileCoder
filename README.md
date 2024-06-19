    
<p align="center">
    <br>
    <img src="assets/logo_1.svg" width="500"/>
    <br>
<p>
<div align="center">
  <a href="https://opensource.org/license/apache-2-0/">
  <img alt="license" src="https://img.shields.io/badge/License-Apache%202.0-green.svg"/>
  </a>
   <a href="https://www.python.org/downloads/release/python-380/">
  <img alt="python" src="https://img.shields.io/badge/python-3.8+-yellow.svg"/>
  </a> 


    
# AgileCoder: A Multi-Agents Software Development Framework based on Agile Methodology

<!-- 
[![Code License](https://img.shields.io/badge/Code%20License-Apache_2.0-green.svg)](https://github.com/bdqnghi/CodeTF_personal/blob/main/LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) -->
 </div>   
    
## Table of Contents
  - [Overview](#overview)
  - [Installation](#installation)
  - [Get Started](#get-started)
  - [Demo](#demo)



## Overview
***AgileCoder*** integrates Agile Methodology into a multi-agent system framework, enabling a collaborative environment where software agents assume specific Agile roles such as Product Manager, Scrum Master, Developer, Senior Developer, and Tester. These agents work together to develop software efficiently and iteratively, simulating a dynamic and adaptive software development team.

In AgileCoder, each agent is not just a participant but a stakeholder in the software development process, engaging in sprints that mimic real-world Agile practices. This setup enhances the adaptability and effectiveness of development workflows, aligning closely with modern software engineering demands. The system is designed to handle the complexities of real-world software projects, supporting incremental development and continuous integration seamlessly.


Key Features of ***AgileCoder***:
- Dynamic Role Assignment: Agents dynamically assume roles based on the project needs and user inputs, ensuring flexibility and optimal resource utilization.
- Sprint-Based Development: The framework organizes development tasks into sprints, promoting rapid prototyping and frequent reassessment of project goals.
- Dynamic Code Graph Generator: This innovative module automatically generates and updates a dependency graph whenever the codebase changes, enhancing the agents’ understanding of the code structure and interdependencies. This feature is crucial for maintaining high accuracy in code generation and modifications.


<div align="center">
  <img alt="demo" src="assets/overview.jpg"/>
</div>

# Dynamic Code Graph Generator (DCGG)
<div align="center">
  <img alt="demo" src="assets/dcgg.png"/>
</div>
We propose Dynamic Code Graph Generator, a static-analysis based module that generates a Code Dependency Graph whenever agents make changes to the codebase. The Code Dependency Graph captures the relationships across files, serving as a reliable source for agents to retrieve the most relevant contexts for generating and modifying code accurately within the workflow.

**Key Features**:

- Real-time graph generation: The Dynamic Code Graph Generator will analyze the codebase and generate an updated Code Dependency Graph whenever changes are made by the agents.
- Dependency analysis: The module will identify and capture dependencies between files, functions, and modules within the codebase, providing a comprehensive overview of the relationships among various code components.
- Context retrieval: Agents will be able to query the Code Dependency Graph to retrieve the most relevant contexts (files, functions, or modules) related to the code being generated or edited. This will ensure that the agents have access to the necessary information to make accurate code modifications.
- Language-agnostic: The Dynamic Code Graph Generator will be designed to support multiple programming languages, making it adaptable to different codebases and development environments.
- Scalability: The module will be optimized to handle large codebases efficiently, ensuring that the graph generation process remains fast and responsive even as the codebase grows.

**Benefits**:

- Improved code accuracy: By providing agents with the most relevant contexts, the Dynamic Code Graph Generator will enable them to generate and modify code more accurately, reducing the likelihood of introducing errors or inconsistencies.
- Enhanced collaboration: The Code Dependency Graph will facilitate better collaboration among agents by providing a shared understanding of the codebase's structure and relationships.
- Increased efficiency: With quick access to relevant contexts, agents will be able to complete code generation and modification tasks more efficiently, streamlining the overall development workflow.
- Maintainability: The Dynamic Code Graph Generator will help maintain the codebase's integrity by ensuring that agents have a clear understanding of the dependencies and relationships within the code.

# Evaluation 
We will evaluate the performance of AgileCoder on two types of datasets to assess its effectiveness in generating code for different scenarios:
- Competitive Programming: HumanEval and MBPP
- Complex Software Requirements: We curate a new dataset called **ProjectDev**, which contains complex software requirements for generating complete software projects. This dataset will be designed to evaluate AgileCoder's ability to handle more intricate and real-world software development scenarios.

## Results
  
| Category             | Model                     | HumanEval | MBPP   |
|----------------------|---------------------------|-----------|--------|
| **LLMs (prompting)** |                           |           |        |
|                      | CodeGeeX-13B              | 18.9      | 26.9   |
|                      | PaLM Coder-540B           | 43.9      | 32.3   |
|                      | DeepSeeker-33B-Inst       | 79.3      | 70.0   |
|                      | GPT-3.5 Turbo             | 60.3      | 52.2   |
|                      | Claude 3 Haiku            | 75.9      | 80.4   |
|                      | GPT 4                     | 80.1      | 80.1   |
| **LLMs-based Agents**|                           |           |        |
| with GPT-3.5 Turbo   | ChatDev                   | 61.79     | 74.80  |
|                      | MetaGPT                   | 62.80     | 74.73  |
|                      | **AgileCoder**            | **70.53** | **80.92** |
| with Claude 3 Haiku  | ChatDev                   | 76.83     | 70.96  |
|                      | **AgileCoder**            | **79.27** | **84.31** |
| with GPT 4           | MetaGPT                   | 85.9      | 87.7   |
|                      | **AgileCoder**            | **90.85** | -      |


For **ProjectDev**, we evaluate the practical application of software projects generated by AgileCoder, ChatDev, and MetaGPT. The evaluation will involve human assessment to compare their performance with 3 criterias:
- Human evaluators will assess the executability of the generated software projects against the expected requirements specified in the ProjectDev dataset.
- For each generated software project, the evaluators will determine whether it is executable and meets the specified requirements.
- The success rate will be calculated as the percentage of requirements met by the executable software projects (e.g., if a generated program is executable and meets 4 out of 10 requirements, its executability rate is 40%).

| Metric                    | ChatDev | MetaGPT | AgileCoder |
|---------------------------|---------|---------|---------------|
| Executability             | 32.79   | 7.73    | **57.79**     |
| Entire Running Time (s)   | 120     | **48**  | 444           |
| Avg. Time/Sprint (s)      | -       | -       | 306           |
| #Sprints                  | -       | -       | 1.64          |
| Token Usage               | 7440    | **3029**| 36818         |
| Expenses (USD)            | 0.12    | **0.02**| 0.44          |
| #Errors                   | 6       | 32      | **0**         |

## Installation
To install the latest version, please clone this repository and then run the command

``
pip install -e AgileCoder
``


We currently supports Azure OpenAI service, so please set following environment variables:

* API_KEY

* RESOURCE_ENDPOINT

* API_TYPE

* API_VERSION

* API_ENGINE
## Get Started
To produce your desired software, simply run the command

``
agilecoder --task "<your requirement about the product you want AgileCoder to create>"
``

For example,

``
agilecoder --task "create a caro game in python"
``


## Demo

![Demo](assets/demo.gif)

*What can AgileCoder do?*

<div align="center">
  <img alt="demo" src="assets/demo_image.png"/>
</div>

More details can be found in [screenshots](assets/screenshots/)


# Citing AgileCoder
More details can be found in our [paper](https://arxiv.org/abs/2406.11912). 

If you're using AgileCoder in your research or applications, please cite using this BibTeX:
```bibtex
@article{minh2024agile,
  title={AgileCoder: Dynamic Collaborative Agents for Software Development based on Agile Methodology},
  author={Minh Huynh Nguyen , Thang Phan Chau , Phong X. Nguyen , Nghi D. Q. Bui},
  journal={arXiv preprint arXiv:2406.11912},
  year={2024}
}
```

# Contact us
If you have any questions, comments or suggestions, please do not hesitate to contact us.
- Website: [fpt-aicenter](https://www.fpt-aicenter.com/ai-residency/)
- Email: support.ailab@fpt.com

# License
[MIT License](LICENSE)

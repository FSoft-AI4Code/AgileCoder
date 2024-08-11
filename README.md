    
<p align="center">
    <br>
    <img src="assets/logo_1.svg" width="500"/>
    <br>
<p>
<div align="center">
<!--   <a href="https://opensource.org/license/apache-2-0/">
  <img alt="license" src="https://img.shields.io/badge/License-Apache%202.0-green.svg"/>
  </a>
   <a href="https://www.python.org/downloads/release/python-380/">
  <img alt="python" src="https://img.shields.io/badge/python-3.8+-yellow.svg"/>
  </a>  -->

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT) [![Python 3.8](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/release/python-380/) [![arXiv](https://img.shields.io/badge/📝-Paper-red)](https://arxiv.org/abs/2406.11912)

# Dynamic Collaborative Agents for Software Development based on Agile Methodology

<!-- 
[![Code License](https://img.shields.io/badge/Code%20License-Apache_2.0-green.svg)](https://github.com/bdqnghi/CodeTF_personal/blob/main/LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) 
-->
 </div>   

![Demo](assets/caro_1.png)
![Demo](assets/caro_2.png)
## Table of Contents
  - [Overview](#overview)
  - [Quick Start](#quick-start)
  - [Evaluation](evaluation)
  - [Apps Gallery](#apps-gallery)



## 📖 Overview
***AgileCoder*** is a novel multi-agent framework for software development that draws inspiration from the widely-used Agile Methodology in professional software engineering. The key innovation lies in its task-oriented approach, where instead of assigning fixed roles to agents, ***AgileCoder mimics real-world software development by creating a backlog of tasks and dividing the development process into sprints, with the backlog being dynamically updated at each sprint.***


Website: https://fsoft-ai4code.github.io/agilecoder/

<div align="center">
  <img alt="demo" src="assets/overview.jpg"/>
</div>

## 💻️ Quickstart
AgileCoder can be installed easily through pip:
```python
pip install agilecoder
```

If you want to clone the repository, be sure to switch to the *new-flow* branch to access the latest source code.

### Configuration
AgileCoder currently supports the Azure OpenAI service. To configure the necessary environment variables, please set the following:

- **API_KEY**: Your Azure OpenAI API key.
- **RESOURCE_ENDPOINT**: The endpoint URL for your Azure OpenAI resource.
- **API_TYPE**: The type of Azure OpenAI API you are using (e.g., "azure").
- **API_VERSION**: The version of the Azure OpenAI API you are using (e.g., "2022-12-01").
- **API_ENGINE**: The name of the Azure OpenAI engine you want to use (e.g., "text-davinci-002").

You can set these environment variables either in your system settings or by creating a ``.env`` file in the project root directory with the following format:
```bash
API_KEY=your_api_key
RESOURCE_ENDPOINT=your_resource_endpoint
API_TYPE=azure
API_VERSION=2022-12-01
API_ENGINE=text-davinci-002
```
  
## Sample Usage
To generate software using AgileCoder, use the following command:

```bash
agilecoder --task "<your software requirements>"
```

Replace ``<your software requirements>`` with a description of the software you want AgileCoder to create.

For example, to generate a Caro game in Python, run:

```bash
agilecoder --task "Create a Caro game in Python"
```

AgileCoder will process your requirements and generate the corresponding software based on the provided task description.
You can specify additional options and flags to customize the behavior of AgileCoder. For more information on the available options, run:
``
agilecoder --help
``

This will display the help message with a list of supported options and their descriptions.
Feel free to explore different software requirements and experiment with AgileCoder to generate various types of software projects tailored to your needs.

## Demo Web UI

![Demo](assets/demo_v2.gif)

[![Watch the video](assets/thumbnail.png)](assets/demo_UI.webm)



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




## Apps Gallery
AgileCoder can generate a wide range of software with high accuracy; a gallery of executable software will be available soon.

<div align="center">
  <img alt="demo" src="assets/demo_image.png"/>
</div>

More details can be found in [screenshots](assets/screenshots/)


# Citing AgileCoder
More details can be found in our [paper](https://arxiv.org/abs/2406.11912). 

If you're using AgileCoder in your research or applications, please cite using this BibTeX:
```bibtex
@article{nguyen2024agilecoder,
  title={AgileCoder: Dynamic Collaborative Agents for Software Development based on Agile Methodology},
  author={Nguyen, Minh Huynh and Chau, Thang Phan and Nguyen, Phong X and Bui, Nghi DQ},
  journal={arXiv preprint arXiv:2406.11912},
  year={2024}
}
```

# Contact us
If you have any questions, comments or suggestions, please do not hesitate to contact us.
- Website: [fpt-aicenter](https://www.fpt-aicenter.com/ai-residency/)
- Email: bdqnghi@gmail.com

# License
[MIT License](LICENSE)

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=FSoft-AI4Code/AgileCoder&type=Date)](https://star-history.com/#FSoft-AI4Code/AgileCoder&Date)

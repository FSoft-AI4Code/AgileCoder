    
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

*What can AgileCoder do?*

<div align="center">
  <img alt="demo" src="assets/demo_image.png"/>
</div>

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

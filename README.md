    
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
  - [Introduction](#introduction)
  - [Installation](#installation-guide)
  - [Getting Started](#getting-started)
    - [Inferencing Pipeline](#inferencing-pipeline)
    - [Model Zoo](#model-zoo)
    - [Fine-Tuning Your Own Model](#fine-tuning-pipeline)
    - [Evaluate On Well-Known Benchmarks](#evaluate-on-well-known-benchmarks)
    - [Utilities to Manipulate Source Code Based on AST](#code-utilities)
        - [AST Parser in Multiple Languages](#ast-parser-in-multiple-languages)
        - [Extract Code Attributes](#extract-code-attributes)
        - [Remove Comments](#remove-comments)
  - [Ethical and Responsible Use](#ethical-and-responsible-use) 
  - [License](#license)

## Overview


## Installation
To install the latest version, please clone this repository and then run the command

``
pip install -e AgileCoder
``

Our library is now available on Pypi, so it can be easily installed by

``
pip install agilecoder
``

Note: The current version available on PyPI does not support the demonstration 

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
To begin showcasing the Flask app, navigate to the directory `agilecoder/online_log` and execute the following command:

``
python app.py
``
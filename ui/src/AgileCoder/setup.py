from setuptools import setup, find_packages
setup(name='agilecoder',
version='0.1.4',
description='AgileCoder',
url='https://github.com/FSoft-AI4Code/AgileCoder',
author='FSoft-AI4Code',
author_email='support.aic@fpt.com',
license='Apache-2.0',
python_requires=">=3.8",
include_package_data=True,
package_data={"agilecoder": ["CompanyConfig/*/*.json"]},
entry_points={
        'console_scripts': ['agilecoder=agilecoder:main'],
},
install_requires=[
        "openai==0.28.1",
        "tiktoken",
        "markdown",
        "colorama",
        "strsimpy==0.2.1",
        "python-dotenv"
      ],
packages=find_packages(),
zip_safe=False)
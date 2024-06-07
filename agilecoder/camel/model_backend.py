# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
from abc import ABC, abstractmethod
from typing import Any, Dict
import os
import openai
import tiktoken

from agilecoder.camel.typing import ModelType
from agilecoder.components.utils import log_and_print_online


from typing import Any, List, Optional, Dict
import google.auth.exceptions
import google.auth.transport.requests
from google.oauth2.service_account import Credentials
from logging import getLogger

logger = getLogger()
import json

from anthropic.lib.vertex import AnthropicVertex
import google.auth.transport
import anthropic


CLAUDE_3_HAIKU = "claude-3-haiku@20240307"
CLAUDE_3_SONNET = "claude-3-sonnet@20240229"
CLAUDE_3_OPUS = "claude-3-opus@20240229"

GCLOUD_LOCATION = "us-central1"
GCLOUD_PROJECT_ID = "ai4code-dev"


def convert_claude_to_openai(claude_output):
    openai_output = {
            "choices": [
        {
            "content_filter_results": {
            "hate": {
                "filtered": False,
                "severity": "safe"
            },
            "self_harm": {
                "filtered": False,
                "severity": "safe"
            },
            "sexual": {
                "filtered": False,
                "severity": "safe"
            },
            "violence": {
                "filtered": False,
                "severity": "safe"
            }
            },
            "finish_reason": "stop",
            "index": 0,
            "message": {
            "content": str(claude_output.content[0].text),
            "role": "user"
            }
        }
        ],
        "created": 1716105669,
        "id": "chatcmpl-9QVldRhe4q0z7qIz3uZ6oFq7E5lvw",
        "model": claude_output.model,
        "object": "chat.completion",
        "prompt_filter_results": [
        {
            "prompt_index": 0,
            "content_filter_results": {
            "hate": {
                "filtered": False,
                "severity": "safe"
            },
            "self_harm": {
                "filtered": False,
                "severity": "safe"
            },
            "sexual": {
                "filtered": False,
                "severity": "safe"
            },
            "violence": {
                "filtered": False,
                "severity": "safe"
            }
            }
        }
        ],
        "system_fingerprint": None,
        "usage": {
        "completion_tokens": claude_output.usage.input_tokens,
        "prompt_tokens": claude_output.usage.output_tokens,
        "total_tokens": claude_output.usage.input_tokens + claude_output.usage.output_tokens
        }
        }

    return openai_output

class ModelBackend(ABC):
    r"""Base class for different model backends.
    May be OpenAI API, a local LLM, a stub for unit tests, etc."""

    @abstractmethod
    def run(self, *args, **kwargs) -> Dict[str, Any]:
        r"""Runs the query to the backend model.

        Raises:
            RuntimeError: if the return value from OpenAI API
            is not a dict that is expected.

        Returns:
            Dict[str, Any]: All backends must return a dict in OpenAI format.
        """
        pass

class OpenAIModel(ModelBackend):
    r"""OpenAI API in a unified ModelBackend interface."""

    def __init__(self, model_type: ModelType, model_config_dict: Dict) -> None:
        super().__init__()
        self.model_type = model_type
        self.model_config_dict = model_config_dict

        if self.model_type == ModelType.GPT_3_5_AZURE or self.model_type==ModelType.GPT_4_32k:
            RESOURCE_ENDPOINT = os.environ['RESOURCE_ENDPOINT']
            API_TYPE = os.environ['API_TYPE']
            API_VERSION = os.environ['API_VERSION']
            API_KEY = os.environ['API_KEY']
            # print('RESOURCE_ENDPOINT', RESOURCE_ENDPOINT)
            openai.api_key = API_KEY
            openai.api_type = API_TYPE
            openai.api_base = RESOURCE_ENDPOINT
            openai.api_version = API_VERSION
    

    def run(self, *args, **kwargs) -> Dict[str, Any]:
        string = "\n".join([message["content"] for message in kwargs["messages"]])
        encoding = tiktoken.encoding_for_model(self.model_type.value)
        num_prompt_tokens = len(encoding.encode(string))
        gap_between_send_receive = 15 * len(kwargs["messages"])
        num_prompt_tokens += gap_between_send_receive

        num_max_token_map = {
            "gpt-3.5-turbo": 4096,
            "gpt-3.5-turbo-16k": 16384,
            "gpt-3.5-turbo-0613": 4096,
            "gpt-3.5-turbo-16k-0613": 16384,
            "gpt-4": 8192,
            "gpt-4-0613": 8192,
            "gpt-4-32k": 4096,
        }
        num_max_token = num_max_token_map[self.model_type.value]
        num_max_completion_tokens = num_max_token - num_prompt_tokens
        self.model_config_dict['max_tokens'] = num_max_completion_tokens
        if self.model_type == ModelType.GPT_3_5_AZURE or self.model_type==ModelType.GPT_4_32k:
            kwargs['engine'] = os.environ['API_ENGINE']
            # print('API_ENGINE', os.environ['API_ENGINE'])
        else:
            kwargs['model'] = self.model_type.value
        # import pdb; pdb.set_trace()
        response = openai.ChatCompletion.create(*args, **kwargs,
                                                **self.model_config_dict)

        log_and_print_online(
            "**[OpenAI_Usage_Info Receive]**\nprompt_tokens: {}\ncompletion_tokens: {}\ntotal_tokens: {}\n".format(
                response["usage"]["prompt_tokens"], response["usage"]["completion_tokens"],
                response["usage"]["total_tokens"]))
        if not isinstance(response, Dict):
            raise RuntimeError("Unexpected return from OpenAI API")
        return response



class AI4CodeAnthropicVertex(AnthropicVertex):
    def __init__(self, **kwargs):
        self.model_name = kwargs.get("model_name", self.model_name)
        super(AI4CodeAnthropicVertex, self).__init__(
            region=GCLOUD_LOCATION, project_id=GCLOUD_PROJECT_ID, **kwargs
        )

    def _ensure_access_token(self) -> str:
        request = google.auth.transport.requests.Request()
        vertex_credentials = Credentials.from_service_account_info(
            json.loads(open(os.path.join(os.getcwd(), "key.json"), "r").read()),
            scopes=[
                "https://www.googleapis.com/auth/cloud-platform",
                "https://www.googleapis.com/auth/compute",
            ],
        )

        try:
            vertex_credentials.refresh(request=request)
        except google.auth.exceptions.RefreshError:
            logger.error("Error retrieving accesstoken from service account")
        self.access_token = vertex_credentials.token
        if self.access_token:
            logger.info("Successfullt retrieve access token from service account")
            return self.access_token
        return super()._ensure_access_token()

    def generate(self, messages: List[Dict], **kwargs):
        return self.messages.create(
  
            max_tokens=kwargs.get("max_tokens", 1024),
            stop_sequences=kwargs.get("stop_sequences", None),
            temperature=kwargs.get("temperature", 0.2),
            top_k=kwargs.get("top_k", 0),
            model=self.model_name,
            messages=messages,
        )

class AI4CodeHaiku(AI4CodeAnthropicVertex):
    def __init__(self, **kwargs):
        self.model_name = CLAUDE_3_HAIKU
        print('MODEL:', 'CLAUDE HAIKU')
        super().__init__(**kwargs)


class AI4CodeSonnet(AI4CodeAnthropicVertex):
    def __init__(self, **kwargs):
        self.model_name = CLAUDE_3_SONNET
        super().__init__(**kwargs)


class ClaudeAIModel(ModelBackend):
    r"""Claude API in a unified ModelBackend interface."""

    def __init__(self, model_type: ModelType, model_config_dict: Dict) -> None:
        super().__init__()
        self.model_type = model_type
        self.model_config_dict = model_config_dict
            

    def run(self, *args, **kwargs) -> Dict[str, Any]:
        string = "\n".join([message["content"] for message in kwargs["messages"]])
        # encoding = tiktoken.encoding_for_model(self.model_type.value)
        try:
            encoding = tiktoken.encoding_for_model(self.model_type.value)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        num_prompt_tokens = len(encoding.encode(string))
        gap_between_send_receive = 15 * len(kwargs["messages"])
        num_prompt_tokens += gap_between_send_receive

        num_max_token_map = {
            "claude-3-haiku-20240307": 4096,
            "claude-3-opus-20240307": 4096,
            "claude-3-sonneet-20240307": 4096,
            'claude':4096
        }
        kwargs['model'] = 'claude-3-opus-20240229'
        num_max_token = num_max_token_map[self.model_type.value]
        num_max_completion_tokens = num_max_token - num_prompt_tokens
        self.model_config_dict['max_tokens'] = num_max_token_map[self.model_type.value]
        # self.model_config_dict
        # if self.model_type == ModelType.GPT_3_5_CODE_VISTA:
        #     kwargs['engine'] = os.environ['API_ENGINE']
        # else:
        #     raise NotImplementedError
        #     kwargs['model'] = self.model_type.value

        # breakpoint()
        # print('0'*100)
        new_kwargs = {}
        new_kwargs['system'] = kwargs['messages'][0]['content']
        kwargs['messages'][1]['role'] = 'user'
        messages = kwargs['messages'][1:2]
        new_kwargs['model'] ='claude-3-haiku-20240307'
        valid_kwargs = ['system', 'messages', 'model','max_tokens']  
        
        filtered_kwargs = {key: value for key, value in self.model_config_dict.items() if key in valid_kwargs}
        kwargs['max_tokens'] = filtered_kwargs['max_tokens']
        kwargs = new_kwargs
        llm = AI4CodeHaiku()
        # try:
        claude_output = llm.generate(*args, messages=messages,**kwargs)
        # except:
        #     breakpoint()
        response = convert_claude_to_openai(claude_output)

        log_and_print_online(
            "**[CLAUDE_Usage_Info Receive]**\nprompt_tokens: {}\ncompletion_tokens: {}\ntotal_tokens: {}\n".format(
                response["usage"]["prompt_tokens"], response["usage"]["completion_tokens"],
                response["usage"]["total_tokens"]))
        # if not isinstance(response, Dict):
        #     raise RuntimeError("Unexpected return from OpenAI API")
        return response

class AuthropicClaudeAIModel(ModelBackend):
    r"""Claude API in a unified ModelBackend interface."""

    def __init__(self, model_type: ModelType, model_config_dict: Dict) -> None:
        super().__init__()
        self.model_type = model_type
        self.model_config_dict = model_config_dict
        self.client = anthropic.Anthropic(
            api_key = os.environ["ANTHROPIC_API_KEY"],
        )
                    

    def run(self, *args, **kwargs) -> Dict[str, Any]:
        string = "\n".join([message["content"] for message in kwargs["messages"]])
        # encoding = tiktoken.encoding_for_model(self.model_type.value)
        try:
            encoding = tiktoken.encoding_for_model(self.model_type.value)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        num_prompt_tokens = len(encoding.encode(string))
        gap_between_send_receive = 15 * len(kwargs["messages"])
        num_prompt_tokens += gap_between_send_receive

        num_max_token_map = {
            "claude-3-haiku-20240307": 4096,
            "claude-3-opus-20240307": 4096,
            "claude-3-sonneet-20240307": 4096,
            'claude':4096,
            'Authropic_Claude': 4096
        }
        # kwargs['model'] = 'claude-3-opus-20240229'
        # num_max_token = num_max_token_map[self.model_type.value]
        # num_max_completion_tokens = num_max_token - num_prompt_tokens
        self.model_config_dict['max_tokens'] = num_max_token_map[self.model_type.value]
        # self.model_config_dict
        # if self.model_type == ModelType.GPT_3_5_CODE_VISTA:
        #     kwargs['engine'] = os.environ['API_ENGINE']
        # else:
        #     raise NotImplementedError
        #     kwargs['model'] = self.model_type.value

        # breakpoint()
        # print('0'*100)
        new_kwargs = {}
        new_kwargs['system'] = kwargs['messages'][0]['content']
        kwargs['messages'][1]['role'] = 'user'
        messages = kwargs['messages'][1:2]
        new_kwargs['model'] ='claude-3-haiku-20240307'
        valid_kwargs = ['system', 'messages', 'model','max_tokens']  
        
        filtered_kwargs = {key: value for key, value in self.model_config_dict.items() if key in valid_kwargs}
        kwargs['max_tokens'] = filtered_kwargs['max_tokens']
        kwargs = new_kwargs
        # llm = AI4CodeHaiku()
        # # try:
        # claude_output = llm.generate(*args, messages=messages,**kwargs)
        # except:
        #     breakpoint()
    
        kwargs.update({
            'max_tokens': 1024,
            'stop_sequences': None,
            'temperature': 0.2, 
            'top_k': 0
        })
        claude_output = self.client.messages.create(
                messages=messages,
                **kwargs
            )
        response = convert_claude_to_openai(claude_output)

        log_and_print_online(
            "**[CLAUDE_Usage_Info Receive]**\nprompt_tokens: {}\ncompletion_tokens: {}\ntotal_tokens: {}\n".format(
                response["usage"]["prompt_tokens"], response["usage"]["completion_tokens"],
                response["usage"]["total_tokens"]))
        # if not isinstance(response, Dict):
        #     raise RuntimeError("Unexpected return from OpenAI API")
        return response

class StubModel(ModelBackend):
    r"""A dummy model used for unit tests."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()

    def run(self, *args, **kwargs) -> Dict[str, Any]:
        ARBITRARY_STRING = "Lorem Ipsum"

        return dict(
            id="stub_model_id",
            usage=dict(),
            choices=[
                dict(finish_reason="stop",
                     message=dict(content=ARBITRARY_STRING, role="assistant"))
            ],
        )


class ModelFactory:
    r"""Factory of backend models.

    Raises:
        ValueError: in case the provided model type is unknown.
    """

    @staticmethod
    def create(model_type: ModelType, model_config_dict: Dict) -> ModelBackend:
        default_model_type = ModelType.GPT_3_5_TURBO
        if model_type in {
             ModelType.GPT_3_5_TURBO, ModelType.GPT_4, ModelType.GPT_4_32k, ModelType.GPT_3_5_AZURE,
            None
        }:
            model_class = OpenAIModel
        elif model_type in {ModelType.CLAUDE }:
            model_class = ClaudeAIModel
        elif model_type in {ModelType.ANTHROPIC_CLAUDE}:
            model_class = AuthropicClaudeAIModel
        elif model_type == ModelType.STUB:
            model_class = StubModel
        else:
            raise ValueError("Unknown model")

        if model_type is None:
            model_type = default_model_type



        # log_and_print_online("Model Type: {}".format(model_type))
        inst = model_class(model_type, model_config_dict)
        return inst
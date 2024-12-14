import json
import os
from abc import ABC, abstractmethod
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from s3_facade import s3

from logger import configured_logger

load_dotenv()

# Load API key from environment variables
api_key = os.getenv("OPENAI_API_KEY")

from models import FormDataSchema


# Strategy Interface
class ResponseFormatStrategy(ABC):
    @abstractmethod
    def prepare_llm(self, llm: ChatOpenAI):
        """Configure the LLM for the chosen strategy."""
        pass

    @abstractmethod
    def serialize_response(self, response):
        """Serialize the LLM response based on the chosen strategy."""
        pass


# JSON Schema Strategy
class JsonSchemaStrategy(ResponseFormatStrategy):
    def __init__(self, schema_file: str):
        self.schema_file = schema_file

    def prepare_llm(self, llm: ChatOpenAI):
        try:
            # Download schema from S3
            schema_content = s3.download_schema(self.schema_file)

            # Assuming the schema content is JSON, you can load it into a Python object
            json_schema = json.loads(schema_content.decode('utf-8'))  # Decode bytes to string if necessary

            # Configure the LLM with the schema
            return llm.with_structured_output(json_schema)

        except Exception as e:
            # Handle any errors (e.g., downloading the schema, parsing JSON)
            configured_logger.error(f"Error preparing LLM with schema '{self.schema_file}': {e}")
            raise Exception(f"Failed to prepare LLM with schema '{self.schema_file}'.") from e

    def serialize_response(self, response):
        # JSON Schema responses should already be JSON-compatible
        return response


# Pydantic Model Strategy
class PydanticModelStrategy(ResponseFormatStrategy):
    def __init__(self, pydantic_model: BaseModel):
        self.pydantic_model = pydantic_model

    def prepare_llm(self, llm: ChatOpenAI):
        return llm.with_structured_output(self.pydantic_model)

    def serialize_response(self, response):
        # Convert Pydantic models to dicts
        if isinstance(response, BaseModel):
            return response.model_dump()
        elif isinstance(response, dict):
            # Handle nested Pydantic models
            def serialize(obj):
                if isinstance(obj, BaseModel):
                    return obj.dict()
                elif isinstance(obj, list):
                    return [serialize(item) for item in obj]
                elif isinstance(obj, dict):
                    return {key: serialize(value) for key, value in obj.items()}
                return obj

            return serialize(response)
        else:
            raise TypeError("Response type not supported for serialization")


# LLM Client with Strategy Support
class LLMClient:
    def __init__(self, model: str, strategy: ResponseFormatStrategy):
        self.model = model
        self.strategy = strategy
        self.llm = ChatOpenAI(model=model)

    def prepare_llm(self):
        self.llm = self.strategy.prepare_llm(self.llm)

    def invoke(self, messages):
        response = self.llm.invoke(messages)
        return self.strategy.serialize_response(response)


def process_form_data(
    form_schema_key: str = None, use_pydantic: bool = False, input_content: str = None
):
    """
    Process form data using LLM with either Pydantic or JSON Schema strategy.

    :param form_schema_key: String serves as key for schema file in s3
    :param use_pydantic: Boolean to choose between Pydantic and JSON Schema strategy
    :param input_content: Input content for form processing
    :return: Processed form data as a JSON string
    :raises ValueError: If input_content is None
    """
    # Validate input content
    if input_content is None:
        raise ValueError(
            "Input content must be provided. input_content cannot be None."
        )

    # Static Case Details
    static_case_details = {
        "ocdCaseTypeId": "REGISTRATION",
        "ocdCaseSubTypeId": "REGISTRATION_OF_NGO",
        "ocdWorkflowId": "WORKFLOW_4984513156789455123",
        "ocdAssignerId": "usr_5224442c22335w651",
        "ocdAssignedDate": "2024-10-07T00:00:00",
        "ocdAssigneeId": "usr_5224442c223354651",
        "ocdStatusId": "STATUS_4984513156789455123",
        "ocdActionId": "ACTION_4984513156789455123",
        "ocdIsEditable": False,
    }

    # Choose strategy based on input
    if use_pydantic:
        strategy = PydanticModelStrategy(FormDataSchema)
    else:
        strategy = JsonSchemaStrategy(form_schema_key)

    # Initialize LLM client with the chosen strategy
    llm_client = LLMClient(model="gpt-4o-mini", strategy=strategy)

    # Prepare the LLM with the chosen strategy
    llm_client.prepare_llm()

    # Send messages
    response = llm_client.invoke(
        [
            SystemMessage(content="Extract the form data."),
            HumanMessage(content=input_content),
        ]
    )

    # Convert response to JSON string
    return response


# Example usage
# if __name__ == "__main__":
#     # Use Pydantic strategy
#     pydantic_response = process_form_data(use_pydantic=True)
#     print("Pydantic Response:")
#     print(json.dumps(pydantic_response, indent=4))
#
#     # Use JSON Schema strategy
#     json_schema_response = process_form_data(use_pydantic=False)
#     print("\nJSON Schema Response:")
#     print(json.dumps(json_schema_response, indent=4))

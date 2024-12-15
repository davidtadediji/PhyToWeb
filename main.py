import json
import os
from abc import ABC, abstractmethod
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from s3_facade import s3

from datetime import datetime

from logger import configured_logger

load_dotenv()

# Load API key from environment variables
api_key = os.getenv("OPENAI_API_KEY")

from models import FormDataSchema


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, BaseModel):
            return obj.model_dump()
        return super().default(obj)


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
            json_schema = json.loads(
                schema_content.decode("utf-8")
            )  # Decode bytes to string if necessary

            print(schema_content)

            # Configure the LLM with the schema
            return llm.with_structured_output(json_schema)

        except Exception as e:
            # Handle any errors (e.g., downloading the schema, parsing JSON)
            configured_logger.error(
                f"Error preparing LLM with schema '{self.schema_file}': {e}"
            )
            raise Exception(
                f"Failed to prepare LLM with schema '{self.schema_file}'."
            ) from e

    def serialize_response(self, response):
        try:
            # Serialize the response using a custom JSON encoder
            serialized_response = json.dumps(response, cls=CustomJSONEncoder)
            # Optionally load it back into a JSON object (if required)
            return json.loads(serialized_response)
        except TypeError as e:
            # Handle TypeError (e.g., non-serializable objects)
            print(f"Error serializing the response: {e}")
            raise ValueError("The response contains non-serializable data.")
        except json.JSONDecodeError as e:
            # Handle JSON decoding errors
            print(f"Error decoding JSON: {e}")
            raise ValueError("There was an error decoding the JSON response.")
        except Exception as e:
            # Handle any other unexpected errors
            print(f"Unexpected error: {e}")
            raise ValueError("An unexpected error occurred during serialization.")


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


def process_form_data(
    data_schema_key: str = None, use_pydantic: bool = False, input_content: str = None
):
    """
    Process form data using LLM with either Pydantic or JSON Schema strategy.

    :param data_schema_key: String serves as key for schema file in s3
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

    print(input_content)

    # Choose strategy based on input
    if use_pydantic:
        strategy = PydanticModelStrategy(FormDataSchema)
    else:
        strategy = JsonSchemaStrategy(data_schema_key)

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
#     # pydantic_response = process_form_data(use_pydantic=True)
#     # print("Pydantic Response:")
#     # print(json.dumps(pydantic_response, indent=4))
#
#     # Use JSON Schema strategy
#     json_schema_response = process_form_data(
#         data_schema_key="software_launch.json",
#         use_pydantic=False,
#         input_content=(
#             "{'lines': ['Software Product Launch Form', 'Case Details', 'Case Type: SOFTWARE_LAUNCH', 'Sub Type: PRODUCT_RELEASE', 'Workflow ID: WORKFLOW_98543261743928', 'Assigner: usr_2223552837464501', 'Assigned Date: 2024-12-14T00:00:00', 'Assignee: usr_4435784936456202', 'Status: STATUS_37849573201876432', 'Action: ACTION_84297543058673', 'Editable: True', 'Product Details', 'Product Name: CloudPro', 'Version: 1.0.0', 'Type: Software', 'Launch Date: 2025-01-01', 'Category: Cloud Computing', 'Website: https://www.cloudpro.com', 'Description: CloudPro is a next-gen cloud platform designed to streamline business operations.', 'Address Details', 'Address 1: 456 Innovation Road', 'Address 2: Cloud Tech Park', 'Address Type: Headquarters', 'Country: USA', 'Postal Code: 94105', 'Start Date: 2024-12-14T00:00:00', 'End Date: 2025-01-01T00:00:00', 'Contact Details', 'Contact Type: Email', 'Contact Value: support@cloudpro.com', 'Primary: True', 'Contact Type: Phone', 'Contact Value: +1-800-123-4567', 'Primary: False', 'Contact Persons', 'Name: Alice Johnson', 'Role: Product Manager', 'Address: 456 Innovation Road, Cloud Tech Park, USA, 94105', 'Organisation: CloudPro Inc.', 'Name: Bob Miller', 'Role: Marketing Lead', 'Address: 456 Innovation Road, Cloud Tech Park, USA, 94105', 'Organisation: CloudPro Inc.', 'Financial Information', 'Account Type: Marketing Expenses', 'Amount: 200000', 'Address: 456 Innovation Road, Cloud Tech Park, USA, 94105', 'Date From: 2024-12-14', 'Date To: 2025-01-01', 'Account Type: Development Costs', 'Amount: 500000', 'Address: 456 Innovation Road, Cloud Tech Park, USA, 94105', 'Date From: 2024-12-14', 'Date To: 2025-01-01'], 'tables': {}, 'form_fields': {'Address Type:': 'Headquarters', 'Assigner:': 'usr_2223552837464501', 'Status:': 'STATUS_37849573201876432', 'Country:': 'USA', 'Assignee:': 'usr_4435784936456202', 'Category:': 'Cloud Computing', 'Assigned Date:': '2024-12-14T00:00:00', 'Product Name:': 'SELECTED CloudPro', 'Description:': 'SELECTED CloudPro is a next-gen cloud platform designed to streamline business operations.', 'Editable:': 'True', 'Address 2:': 'Cloud Tech Park', 'Address 1:': '456 Innovation Road', 'Sub Type:': 'PRODUCT_RELEASE', 'Workflow ID:': 'WORKFLOW_98543261743928', 'Website:': 'https://www.cloudpro.com', 'Launch Date:': '2025-01-01', 'Version:': '1.0.0', 'Case Type:': 'SOFTWARE_LAUNCH', 'Type:': 'Software', 'Action:': 'ACTION_84297543058673', 'Primary:': 'False', 'Contact Value:': 'support@cloudpro.com', 'End Date:': '2025-01-01T00:00:00', 'Contact Type:': 'Email', 'Postal Code:': '94105', 'Amount:': '500000', 'Organisation:': 'CloudPro Inc.', 'Account Type:': 'Development Costs', 'Address:': '456 Innovation Road, Cloud Tech Park, USA, 94105', 'Role:': 'Marketing Lead', 'Name:': 'Bob Miller', 'Start Date:': '2024-12-14T00:00:00', 'Date From:': '2024-12-14', 'Date To:': '2025-01-01'}}"
#         ),
#     )
#
#     print("\nJSON Schema Response:")
#
#     print(json.dumps(json_schema_response, indent=4))

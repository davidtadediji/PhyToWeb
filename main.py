import json
import os
from abc import ABC, abstractmethod
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

load_dotenv()

# Load API key from environment variables
api_key = os.getenv("OPENAI_API_KEY")

print(api_key)

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
        with open(self.schema_file, "r") as f:
            json_schema = json.load(f)
        return llm.with_structured_output(json_schema)

    def serialize_response(self, response):
        # JSON Schema responses should already be JSON-compatible
        return response


# Pydantic Model Strategy
class PydanticModelStrategy(ResponseFormatStrategy):
    # TODO: Fix bug with pydantic strategy datetime formatting

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


# Static CaseDetails
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

# Choose a strategy: JSON Schema or Pydantic Model

use_pydantic = input("Use pydantic, y/n?")  # Set as False to use JSON schema strategy

if use_pydantic == "y":
    use_pydantic = True
else:
    use_pydantic = False

if use_pydantic:
    strategy = PydanticModelStrategy(FormDataSchema)
else:
    strategy = JsonSchemaStrategy("schema.json")

# Initialize LLM client with the chosen strategy
llm_client = LLMClient(model="gpt-4o-mini", strategy=strategy)

# Prepare the LLM with the chosen strategy
llm_client.prepare_llm()

# Send messages
response = llm_client.invoke(
    [
        SystemMessage(content="Extract the form data."),
        HumanMessage(
            content=(
                "Static Case Details:\n"
                f"{json.dumps(static_case_details, indent=4)}\n\n"
                "Organisation Name: Global Innovations\n"
                "Contact Value: john.doe@company.com\n"
                "Editable: False\n"
                "Mission: To change the world.\n"
                "Case Type: REGISTRATION\n"
                "Account Type: Corporate Expenses\n"
                "Vision: To dominate the future.\n"
                "Contact Type: Email\n"
                "Postal Code: 90210\n"
                "Contact Person: Jane Smith\n"
                "Address 1: Somewhere in the city\n"
                "Amount: 50000\n"
                "Assignee ID: usr_5224442c223354651\n"
                "Identifier: Some ID Number\n"
                "Assigner ID: usr_5224442c22335w651\n"
                "Country: USA\n"
                "Organisation Type: Tech\n"
                "Organisation: Global Innovations\n"
                "Case Sub-Type: REGISTRATION_OF_NGO\n"
                "Role: Main Contact\n"
                "Logo URL: https://www.globalinnovations.com/logo.png\n"
                "Status: STATUS_4984513156789455123\n"
                "Issued By: Government Body\n"
                "Action: ACTION_4984513156789455123\n"
                "Assigned Date: 2024-10-07T00:00:00\n"
                "Acronym: GII\n"
                "Address 2: Street Name\n"
                "Objectives: Leading the market."
            )
        ),
    ]
)


# Print serialized response
print(json.dumps(response, indent=4))

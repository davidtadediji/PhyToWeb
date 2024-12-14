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
                "Organisation: The name could be Global Innovations, or something like that. "
                "Acronym? GII, I think. It's a tech company, that's all I remember. "
                "Mission statement: 'To change the world.' Objectives: Something about leading the market. "
                "Vision: 'To dominate the future.' Not sure about the logo, but it's somewhere on their website. "
                "Address: First address, somewhere in the city. They mentioned a street name, but not clear on the suite number. "
                "Postal Code: 90210. Country: USA. There’s another address, probably a warehouse or office location, but don't recall the details. "
                "Identifier: A bunch of numbers, IDs maybe. A card or identifier might have been issued by some agency, but I don’t recall specifics. "
                "Expiry date? Maybe in two years. The organization that gave it out? I think it was some government body or something. "
                "Contact: Email address: john.doe@company.com. Mobile? Not sure, I think it’s +1-123-456-7890. "
                "Main contact: John Doe, but there might be others. Contact Person: Jane Smith, seems important, not entirely sure what role. "
                "She works with John Doe, but could be managing different departments. Location? Unsure. Just that she’s with the team, I think in an office. "
                "Activity: There was something about a conference last year in the spring, or maybe summer, discussing tech advancements. "
                "The date? Don’t recall. But I remember they spoke about new developments. The activity seems like something for internal stakeholders. "
                "The description wasn’t very clear though. Financial Information: Some financial records from last quarter, maybe? "
                "Amounts? Around $50,000 maybe? Date range: Could be from June to September last year. "
                "Address? Not sure, looks like something related to corporate expenses."
            )
        ),
    ]
)


# Print serialized response
print(json.dumps(response, indent=4))

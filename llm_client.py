import json
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from logger import configured_logger
from s3_facade import s3
from utils import validate_output

load_dotenv()

# Load API key from environment variables
api_key = os.getenv("OPENAI_API_KEY")

from models import FormDataSchema, Resume, Card


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, BaseModel):
            return obj.model_dump()
        return super().default(obj)


class LLMProcessingError(Exception):
    """Custom exception for LLM processing errors"""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


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
            raise Exception(
                f"Error preparing LLM with schema '{self.schema_file}' -> {e}"
            )

    def serialize_response(self, response):
        try:
            # Serialize the response using a custom JSON encoder
            serialized_response = json.dumps(response, cls=CustomJSONEncoder)
            # Optionally load it back into a JSON object (if required)
            return json.loads(serialized_response)
        except (TypeError, json.JSONDecodeError) as e:
            raise e
        except Exception as e:
            # Handle any other unexpected errors
            raise ValueError(
                f"An unexpected error occurred during serialization -> {e}"
            )


# Pydantic Model Strategy
class PydanticModelStrategy(ResponseFormatStrategy):
    def __init__(self, pydantic_model: BaseModel):
        self.pydantic_model = pydantic_model

    def prepare_llm(self, llm: ChatOpenAI):
        return llm.with_structured_output(self.pydantic_model)

    def serialize_response(self, response):
        try:
            # Convert Pydantic models to dicts
            if isinstance(response, BaseModel):
                return response.model_dump()
            elif isinstance(response, dict):
                # Handle nested Pydantic models
                def serialize(obj):
                    if isinstance(obj, BaseModel):
                        return obj.model_dump()
                    elif isinstance(obj, list):
                        return [serialize(item) for item in obj]
                    elif isinstance(obj, dict):
                        return {key: serialize(value) for key, value in obj.items()}
                    return obj

                return serialize(response)
            else:
                raise TypeError("Response type not supported for serialization")

        except TypeError as e:
            # Handle type errors (e.g., unsupported types)
            raise ValueError(
                f"Error during serialization due to unsupported type -> {e}"
            )

        except ValueError as e:
            # Handle value errors (e.g., invalid data)
            raise ValueError(f"Error during serialization due to invalid data -> {e}")

        except Exception as e:
            # Catch any other unforeseen errors
            raise Exception(f"Unexpected error during serialization -> {str(e)}")


# LLM Client with Strategy Support
class LLMClient:
    def __init__(self, model: str, strategy: ResponseFormatStrategy):
        self.model = model
        self.strategy = strategy
        self.llm = ChatOpenAI(model=model)
        self.max_retries = 3
        self.retry_delay = 2

    def prepare_llm(self):
        self.llm = self.strategy.prepare_llm(self.llm)

    def invoke(self, messages):
        for attempt in range(self.max_retries):
            try:
                response = self.llm.invoke(messages)
                serialized = self.strategy.serialize_response(response)

                validate_output(serialized)
                return serialized
            except ValidationError as ve:
                configured_logger.error(f"Validation error: {str(ve)}")
                if attempt == self.max_retries - 1:
                    raise LLMProcessingError("Validation failed for LLM response", ve)
            except Exception as e:
                configured_logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise LLMProcessingError("Max retries exceeded", e)

                time.sleep(self.retry_delay * (attempt + 1))

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

DATA_SCHEMA_MAPPER = {
    'resume': Resume,
    'card': Card,
    'registration_for_ngo_npo': FormDataSchema
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

    try:
        # Validate input content
        if input_content is None:
            raise ValueError(
                "Input content must be provided. input_content cannot be None."
            )

        configured_logger.info(f"Processing form data for schema: {data_schema_key}")
        configured_logger.debug(f"Input content: {input_content[:200]}...")  # Log first 200 chars

        # Choose strategy based on input
        if use_pydantic:
            strategy = PydanticModelStrategy(DATA_SCHEMA_MAPPER[data_schema_key])
        else:
            strategy = JsonSchemaStrategy(f"{data_schema_key}.json")

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

    except LLMProcessingError as lpe:
        configured_logger.error(f"LLM Processing failed: {str(lpe)}")
        if lpe.original_error:
            configured_logger.error(f"Original error: {str(lpe.original_error)}")
        raise

    except ValidationError as ve:
        configured_logger.error(f"Data validation error: {str(ve)}")
        raise LLMProcessingError("Data validation failed", ve)

    except Exception as e:
        configured_logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise LLMProcessingError("Processing failed", e)

# Example usage
if __name__ == "__main__":
    # Use Pydantic strategy
    # pydantic_response = process_form_data(use_pydantic=True)
    # print("Pydantic Response:")
    # print(json.dumps(pydantic_response, indent=4))

    # Use JSON Schema strategy
    json_schema_response = process_form_data(
        data_schema_key="resume",
        use_pydantic=True,
        input_content="""
        Extracted Form Fields:
        - Led: 40%
        - National ID: N/A
        - GPA: 3.85/4.0
        - Personal Identification: NID-2023-SF-987654
        - Professional Summary: Innovative software engineer with 6+ years of experience in full-stack development, specializing in cloud-native applications and machine learning integrations. Proven track record of delivering scalable solutions that drive technological advancement.
        - Stanford University: Sep 2015 - Jun 2019
        - DataStream Inc.: Software Engineer
        - San Francisco, CA 94105
        - Optimized database queries, improving performance by 35%
        - TechInnovate Solutions, Senior Software Engineer: Jan 2021 - Present
        - Jul 2019 - Dec 2020
        - Nov 2020: N/A
        - Jun 2021: N/A
        - Programming Languages: Python, Java, JavaScript, TypeScript
        - Tools: Git, Jenkins, Terraform
        - Spanish: Basic Conversational
        - Frameworks: React, Node.js, Django, Spring Boot
        - Japanese: Professional Working Proficiency
        - Databases: PostgreSQL, MongoDB, Redis
        - Cloud Technologies: AWS, Docker, Kubernetes
        - English: Native
        - Credential ID: N/A
        - Google Cloud Credential ID: GCP-PDE-2021-123456
        - AWS Certified Solutions Architect: N/A
        - Google Cloud Professional Data Engineer: N/A
        - Amazon Web Services: AWS-CSA-2020-987654
        - Mar 2022
        - Sep 2022
        - Portfolio: arianakamura.dev
        - LinkedIn: linkedin.com/in/aria-nakamura
        - GitHub: github.com/arianakamura

        Extracted Tables:

        Extracted Text Lines:
        aria.nakamura@techpro.com
        Aria Nakamura
        +1 (555) 123-4567
        San Francisco, CA 94105

        Professional Summary:
        Innovative software engineer with 6+ years of experience in full-stack development, specializing in cloud-native applications and machine learning integrations. Proven track record of delivering scalable solutions that drive technological advancement.

        Personal Identification:
        National ID: NID-2023-SF-987654

        Education:
        Stanford University (Sep 2015 - Jun 2019)
        Bachelor of Science in Computer Science
        GPA: 3.85/4.0 | Minor in Artificial Intelligence

        Work Experience:
        TechInnovate Solutions, Senior Software Engineer (Jan 2021 - Present)
        - Led development of microservices architecture, reducing system latency by 40%
        - Implemented machine learning pipelines for a predictive analytics platform
        - Mentored junior developers and conducted technical interviews

        DataStream Inc., Software Engineer (Jul 2019 - Dec 2020)
        - Developed RESTful APIs for real-time data processing systems
        - Optimized database queries, improving performance by 35%
        - Collaborated with cross-functional teams to deliver innovative solutions

        Skills:
        - Programming Languages: Python, Java, JavaScript, TypeScript
        - Frameworks: React, Node.js, Django, Spring Boot
        - Cloud Technologies: AWS, Docker, Kubernetes
        - Databases: PostgreSQL, MongoDB, Redis
        - Tools: Git, Jenkins, Terraform

        Projects:
        ML-Powered Customer Churn Predictor (Mar 2022 - Sep 2022)
        - Developed machine learning model with 85% accuracy in predicting customer churn
        - Utilized scikit-learn and TensorFlow for model development
        - Created an interactive dashboard for visualizing predictive insights

        Certifications:
        - AWS Certified Solutions Architect (Nov 2020)
          Amazon Web Services | Credential ID: AWS-CSA-2020-987654
        - Google Cloud Professional Data Engineer (Jun 2021)
          Google Cloud | Credential ID: GCP-PDE-2021-123456

        Languages:
        - English: Native
        - Japanese: Professional Working Proficiency
        - Spanish: Basic Conversational

        Links:
        - LinkedIn: linkedin.com/in/aria-nakamura
        - GitHub: github.com/arianakamura
        - Portfolio: arianakamura.dev
        """
    )

    print("\nJSON Schema Response:")

    print(json.dumps(json_schema_response, default=str, indent=4))
